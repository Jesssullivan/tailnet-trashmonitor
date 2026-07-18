// RTT probe: samples RTCPeerConnection.getStats() and emits per-second
// RTT / jitter / framesDropped readings. Today the readings are logged
// to console only; the next step (vision/buffer_tuner.py consumer) is
// to POST these to a feedback endpoint so the capture-host ffmpeg can
// adapt its encoder targets in response.
//
// See plan §A4 (issues #3 + #4 — roundtrip TTL + buffer-bound feedback).

export type RttSample = {
	streamId: string;
	rttSeconds: number | null;
	jitterSeconds: number | null;
	framesDropped: number;
	framesDecoded: number;
	ts: number;
};

export function startRttProbe(
	pc: RTCPeerConnection,
	streamId: string,
	onSample: (s: RttSample) => void,
	intervalMs = 1000,
): () => void {
	const tick = async () => {
		const stats = await pc.getStats();
		let rtt: number | null = null;
		let jitter: number | null = null;
		let dropped = 0;
		let decoded = 0;
		stats.forEach((report) => {
			if (report.type === 'candidate-pair' && report.state === 'succeeded' && report.nominated) {
				if (typeof report.currentRoundTripTime === 'number') rtt = report.currentRoundTripTime;
			}
			if (report.type === 'inbound-rtp' && report.kind === 'video') {
				if (typeof report.jitter === 'number') jitter = report.jitter;
				if (typeof report.framesDropped === 'number') dropped = report.framesDropped;
				if (typeof report.framesDecoded === 'number') decoded = report.framesDecoded;
			}
		});
		onSample({
			streamId,
			rttSeconds: rtt,
			jitterSeconds: jitter,
			framesDropped: dropped,
			framesDecoded: decoded,
			ts: Date.now(),
		});
	};

	const id = setInterval(tick, intervalMs);
	return () => clearInterval(id);
}

// Default sink: logs structured JSON to the console. Once a feedback
// endpoint exists, swap this for a POST to /api/feedback (or a WS).
export function consoleSink(s: RttSample): void {
	if (s.rttSeconds === null && s.jitterSeconds === null) return;
	console.log('[rtt]', JSON.stringify(s));
}
