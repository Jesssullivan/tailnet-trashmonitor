#!/bin/sh
# Boot Caddy + MediaMTX inside one container. Both binaries live at
# /usr/local/bin (root-owned, mode 0755) so they exec cleanly under
# readOnlyRootFilesystem + drop:ALL.
#
# Per-stream mode (PR3): when TRASHMON_STREAM_ID is set, render a
# stream-scoped mediamtx config to /tmp/mediamtx.yml and tell MediaMTX
# to advertise this stream's tailnet hostname as the WebRTC ICE host
# candidate. The image's bundled /etc/mediamtx.yml is the multi-stream
# fallback used only when TRASHMON_STREAM_ID is unset.

set -eu

config=/etc/mediamtx.yml

if [ -n "${TRASHMON_STREAM_ID:-}" ]; then
    config=/tmp/mediamtx.yml
    : "${TRASHMON_TAILNET:?TRASHMON_TAILNET must be set when TRASHMON_STREAM_ID is set}"
    webrtc_host="${TRASHMON_STREAM_ID}-webrtc.${TRASHMON_TAILNET}"

    # Render: replace the paths block with a single entry for this
    # stream, and replace webrtcAdditionalHosts with this pod's
    # per-stream WebRTC hostname. awk is used over sed because the
    # paths block is multi-line and sed's portability across BSD/GNU
    # for multi-line edits is painful.
    awk -v sid="$TRASHMON_STREAM_ID" -v host="$webrtc_host" '
        BEGIN { in_paths = 0; in_hosts = 0 }
        /^paths:/                  { print "paths:"; print "  " sid ":"; in_paths = 1; next }
        in_paths && /^[^ ]/        { in_paths = 0 }
        in_paths                   { next }
        /^webrtcAdditionalHosts:/  { print "webrtcAdditionalHosts:"; print "  - " host; in_hosts = 1; next }
        in_hosts && /^[^ -]/       { in_hosts = 0 }
        in_hosts                   { next }
        { print }
    ' /etc/mediamtx.yml > "$config"
fi

mediamtx "$config" &
mtx_pid=$!

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
caddy_pid=$!

wait -n "$mtx_pid" "$caddy_pid"
exit $?
