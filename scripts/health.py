#!/usr/bin/env python3
"""Live health check for the trashmonitor cluster.

Reads a MediaMTX /api/v3/paths/list JSON document from stdin and prints
a one-line-per-path status table. Exits non-zero if any non-parked path
is not ready, so it can be used as a CI gate.

Parked paths: anything listed in $TRASHMON_PARKED (comma-separated) is
allowed to be offline without affecting the exit code — useful when a
host is intentionally down (kernel work, hardware swap) but the slot
is still declared in mediamtx.yml.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

PARKED = {s.strip() for s in os.environ.get("TRASHMON_PARKED", "").split(",") if s.strip()}


def main() -> int:
	data: dict[str, Any] = json.load(sys.stdin)
	bad: list[str] = []
	for p in data["items"]:
		name = p["name"]
		ready = bool(p["ready"])
		bytes_recv = int(p["bytesReceived"])
		codec = ""
		tracks2 = p.get("tracks2") or []
		if tracks2:
			t = tracks2[0]
			cp = t.get("codecProps") or {}
			w = cp.get("width", "?")
			h = cp.get("height", "?")
			codec = f"{t['codec']} {w}x{h}"
		if ready:
			marker = "ok"
		elif name in PARKED:
			marker = "..."
		else:
			marker = "FAIL"
			bad.append(name)
		print(f"  {marker:4} {name:14} {codec:20} {bytes_recv:>12,} bytes")
	if bad:
		print(f"\nUNHEALTHY: {bad}", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
