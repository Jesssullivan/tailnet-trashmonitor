// WHEP (WebRTC-HTTP Egress Protocol, RFC 9725) client for MediaMTX.
//
// The negotiation is two HTTP calls: POST our SDP offer, receive the
// SDP answer in the response body plus a Location header pointing at
// the session resource. On teardown we DELETE the session URL so
// MediaMTX can free the peer connection promptly.
//
// Media flows over UDP (or TCP fallback) directly to the host
// advertised in MediaMTX's webrtcAdditionalHosts (see server's
// entrypoint.sh: per-stream pods set this to <id>-webrtc.<tailnet>.ts.net).
// Signaling is same-origin via Caddy (server/Caddyfile proxies
// /<stream>/whep to 127.0.0.1:8889).

export type WhepSession = {
	pc: RTCPeerConnection;
	close: () => Promise<void>;
};

export type WhepOptions = {
	whepUrl: string;
	video: HTMLVideoElement;
	// Optional hook: called with the negotiated session's PeerConnection
	// so callers can subscribe to stats (RTT, jitter) for the feedback
	// loop (issues #3 + #4).
	onConnected?: (pc: RTCPeerConnection) => void;
};

export async function negotiateWhep(opts: WhepOptions): Promise<WhepSession> {
	const pc = new RTCPeerConnection({ bundlePolicy: 'max-bundle' });
	pc.addTransceiver('video', { direction: 'recvonly' });
	pc.addTransceiver('audio', { direction: 'recvonly' });

	const stream = new MediaStream();
	pc.ontrack = (ev) => {
		stream.addTrack(ev.track);
		opts.video.srcObject = stream;
	};

	const offer = await pc.createOffer();
	await pc.setLocalDescription(offer);
	await waitForIceGathering(pc);

	const resp = await fetch(opts.whepUrl, {
		method: 'POST',
		headers: { 'Content-Type': 'application/sdp' },
		body: pc.localDescription?.sdp ?? '',
	});
	if (!resp.ok) {
		pc.close();
		throw new Error(`WHEP negotiation failed: HTTP ${resp.status}`);
	}
	const answerSdp = await resp.text();
	await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

	// RFC 9725 §4.1: WHEP server returns Location header with the
	// session resource. Absolute URLs supersede; relative resolve
	// against the WHEP endpoint.
	const locationHeader = resp.headers.get('Location');
	const sessionUrl = locationHeader ? new URL(locationHeader, opts.whepUrl).toString() : null;

	pc.addEventListener('connectionstatechange', () => {
		if (pc.connectionState === 'connected') {
			opts.onConnected?.(pc);
		}
	});

	return {
		pc,
		close: async () => {
			if (sessionUrl) {
				try {
					await fetch(sessionUrl, { method: 'DELETE' });
				} catch {
					// Best-effort. MediaMTX times out idle sessions on its own.
				}
			}
			pc.close();
		},
	};
}

function waitForIceGathering(pc: RTCPeerConnection): Promise<void> {
	if (pc.iceGatheringState === 'complete') return Promise.resolve();
	return new Promise((resolve) => {
		const onChange = () => {
			if (pc.iceGatheringState === 'complete') {
				pc.removeEventListener('icegatheringstatechange', onChange);
				resolve();
			}
		};
		pc.addEventListener('icegatheringstatechange', onChange);
		// Trickle ICE is supported by MediaMTX but we send the full SDP
		// once ICE is gathered. 2s is enough for tailnet host candidates.
		setTimeout(() => {
			pc.removeEventListener('icegatheringstatechange', onChange);
			resolve();
		}, 2000);
	});
}
