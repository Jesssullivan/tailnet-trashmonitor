"""Vision sidecar — Phase 1 stub.

Consumes one RTSP stream from MediaMTX, runs cv2.absdiff against the
previous frame, and emits VisionEvent records (see schemas/event.json)
as JSON lines on stdout. A Prometheus /metrics endpoint exposes counters
and the most recent change_score gauge.

No NATS, no bridge wiring yet — stdout is the event bus until the
downstream consumer lands. Real detectors (color, ssim, haar) replace
the absdiff body without changing the schema or the loop.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2  # type: ignore[import-untyped]
import numpy as np
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest


@dataclass(frozen=True)
class Config:
    stream_id: str
    rtsp_url: str
    metrics_port: int
    diff_emit_threshold: float
    log_every_n_frames: int

    @classmethod
    def from_env(cls) -> "Config":
        stream_id = os.environ["VISION_STREAM_ID"]
        rtsp_url = os.environ.get(
            "VISION_RTSP_URL",
            f"rtsp://trashmonitor-rtsp:8554/{stream_id}",
        )
        return cls(
            stream_id=stream_id,
            rtsp_url=rtsp_url,
            metrics_port=int(os.environ.get("VISION_METRICS_PORT", "9100")),
            diff_emit_threshold=float(os.environ.get("VISION_DIFF_THRESHOLD", "5.0")),
            log_every_n_frames=int(os.environ.get("VISION_LOG_EVERY_N", "30")),
        )


frames_read = Counter(
    "trashmonitor_vision_frames_read_total",
    "Frames successfully decoded from the RTSP source.",
    ["stream"],
)
frames_failed = Counter(
    "trashmonitor_vision_frames_failed_total",
    "Frame reads that returned no image (transient or stream-end).",
    ["stream"],
)
events_emitted = Counter(
    "trashmonitor_vision_events_emitted_total",
    "VisionEvent records written to stdout.",
    ["stream", "source"],
)
change_score = Gauge(
    "trashmonitor_vision_change_score",
    "Most recent absdiff mean (0-255) per stream and ROI label.",
    ["stream", "roi"],
)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib API)
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = generate_latest()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def emit_event(
    stream_id: str,
    source: str,
    roi: tuple[int, int, int, int],
    metric_name: str,
    metric_value: float,
    ts_capture_ns: int,
    threshold: float | None = None,
) -> None:
    event = {
        "stream_id": stream_id,
        "ts_capture_ns": ts_capture_ns,
        "ts_detected_ns": time.time_ns(),
        "source": source,
        "roi": {"x": roi[0], "y": roi[1], "w": roi[2], "h": roi[3]},
        "metric": {"name": metric_name, "value": metric_value},
        "signal": "raw",
    }
    if threshold is not None:
        event["metric"]["threshold"] = threshold
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()
    events_emitted.labels(stream=stream_id, source=source).inc()


def start_metrics_server(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), MetricsHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run(config: Config) -> int:
    log = logging.getLogger("vision")
    log.info("connecting to %s for stream %s", config.rtsp_url, config.stream_id)

    cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        log.error("failed to open RTSP source %s", config.rtsp_url)
        return 2

    prev_gray: np.ndarray | None = None
    frame_idx = 0
    stop = threading.Event()

    def handle_signal(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not stop.is_set():
        ok, frame = cap.read()
        if not ok or frame is None:
            frames_failed.labels(stream=config.stream_id).inc()
            time.sleep(0.1)
            continue
        ts_capture_ns = time.time_ns()
        frames_read.labels(stream=config.stream_id).inc()
        frame_idx += 1

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        roi = (0, 0, w, h)

        if prev_gray is not None and prev_gray.shape == gray.shape:
            diff = cv2.absdiff(prev_gray, gray)
            mean_diff = float(diff.mean())
            change_score.labels(stream=config.stream_id, roi="full").set(mean_diff)
            if mean_diff >= config.diff_emit_threshold:
                emit_event(
                    stream_id=config.stream_id,
                    source="diff",
                    roi=roi,
                    metric_name="absdiff_mean",
                    metric_value=mean_diff,
                    ts_capture_ns=ts_capture_ns,
                    threshold=config.diff_emit_threshold,
                )

        prev_gray = gray

        if frame_idx % config.log_every_n_frames == 0:
            log.info("stream=%s frames=%d size=%dx%d", config.stream_id, frame_idx, w, h)

    cap.release()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = Config.from_env()
    start_metrics_server(config.metrics_port)
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
