#!/bin/sh
# Boot Caddy + MediaMTX inside one container. Both binaries live at
# /usr/local/bin (root-owned, mode 0755) so they exec cleanly under
# readOnlyRootFilesystem + drop:ALL.

set -eu

mediamtx /etc/mediamtx.yml &
mtx_pid=$!

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
caddy_pid=$!

wait -n "$mtx_pid" "$caddy_pid"
exit $?
