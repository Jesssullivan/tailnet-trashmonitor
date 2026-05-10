tailnet-trashmonitor
====================

Tailnet-only webcam streaming. Capture hosts (any Linux box with a
V4L2 webcam) push H.264-over-RTSP into a small MediaMTX + Caddy + SPA
bundle that runs in Kubernetes and is exposed to the tailnet via the
Tailscale Kubernetes operator.

The repo is intentionally small. It is a working example of a
single-tenant, tailnet-scoped streaming surface, not a product.


Architecture
------------

    capture-host-a (ffmpeg, libx264, RTSP push) ─┐
                                                 ├─► MediaMTX (cluster) ─► HLS ─► hls.js ─► SPA tile
    capture-host-b (ffmpeg, libx264, RTSP push) ─┘                                         (tailnet HTTPS via
                                                                                            tailscale-operator)

- Capture hosts are provisioned with the ansible role under
  `ansible/roles/trashcam`. A systemd template unit
  `trashcam@<id>.service` wraps an `ffmpeg` invocation that reads
  `/dev/video*`, transcodes to H.264 (libx264, ultrafast / zerolatency),
  and publishes via RTSP to the cluster's MediaMTX.

- The server is a single OCI image (Caddy + SPA static bundle + MediaMTX)
  exposed to the tailnet via the `tailscale-operator` LoadBalancer
  pattern.

- The SPA is SvelteKit with Runes + `adapter-static`. It polls
  `/api/v3/paths/list` and renders one `<video>` per ready stream
  via `hls.js`.


Repo layout
-----------

    spa/        SvelteKit SPA (Runes, static)
    capture/    Capture-host artifacts: systemd unit, RPM spec, ffmpeg wrapper
    server/     MediaMTX + Caddy OCI image + k8s manifests
    otel/       Grafana dashboard + Prometheus alert rules
    ansible/    Provisioning over the tailnet
    scripts/    Health probe + DNS reconciler
    flake.nix   Dev shell (bazel + just + pnpm + node + ansible + ffmpeg + kube tools)


Quick start
-----------

    nix develop                # enter dev shell
    just setup                 # pnpm install in spa/

    # Cluster (one-shot bootstrap; idempotent re-runs)
    just bootstrap 0.0.1       # ghcr-secret + image build/push + kustomize apply + DNS

    # Capture hosts (over tailnet)
    just provision-host HOST=<inventory-host>

    # Granular pieces if you don't want the bootstrap
    just image-push 0.0.1      # build + crane push the cluster OCI image
    just deploy                # kubectl apply -k server/k8s
    just dns                   # reconcile public-zone A record + tailnet split-DNS
    just ghcr-secret           # reconcile the in-namespace ghcr pull secret


Configuration
-------------

The Justfile reads the following environment variables; defaults are
placeholders that you must override:

    GHCR_REPO        ghcr.io/<your-org>/tailnet-trashmonitor
    GHCR_EMAIL       <your-email>                     (only for the ghcr docker-registry secret)
    TS_TAILNET       <your-tailnet>.ts.net            (tailnet name for the API)
    DNS_ZONE         <your-zone>                      (Cloudflare zone, e.g. example.com)
    DNS_HOSTNAME     trashmonitor.<your-zone>         (FQDN to publish)
    TS_HOSTNAME      trashmonitor                     (tailnet hostname of the LB)
    CF_API_TOKEN     ...                              (Cloudflare API token with zone:dns:write)
    TS_API_KEY       ...                              (Tailscale API key with dns:write)

Drop these into a `.env` next to the Justfile (gitignored).


Cluster image
-------------

There is no top-level Dockerfile. The cluster image is assembled by
Bazel (`server/BUILD.bazel`) layering Caddy + MediaMTX + the prebuilt
SPA bundle. The SPA build itself is driven by pnpm + vite out-of-band
(see `just spa-build`); Bazel just packages the static output.


Observability
-------------

MediaMTX exposes Prometheus metrics on `:9998/metrics` inside the pod
and via the `trashmonitor-metrics` ClusterIP service. The `otel/`
manifests are written for the prometheus-operator pattern:

    server/k8s/servicemonitor.yaml    apply when the cluster has prometheus-operator CRDs
    otel/alert-rules.yaml             same

If your cluster has no in-cluster Prometheus, expose the
`trashmonitor-metrics` service to the tailnet (LoadBalancer with the
operator pattern) and scrape it from an external Prometheus.


DNS / tailnet alias
-------------------

A Cloudflare A record can give the workload a friendly hostname that
still only resolves on-tailnet:

    trashmonitor.<your-zone>   A   <tailnet IP>     (a CGNAT 100.64.0.0/10 address)

The record is DNS-only (grey cloud). The CGNAT IP is publicly
resolvable but only routable from tailnet-connected devices. A
CNAME into Tailscale MagicDNS (.ts.net) does not work because public
resolvers can't follow CNAMEs into MagicDNS.

For tailnet clients to resolve the alias, the tailnet's DNS config
needs a split-DNS rule for your zone (`<your-zone> -> 1.1.1.1`).
`scripts/dns-bootstrap.py` reconciles both the CF A record and the
Tailscale split-DNS map, idempotently.

HTTPS is served directly by Caddy with a Let's Encrypt cert
provisioned by cert-manager via DNS-01 (see `server/k8s/cert.yaml`).


See also
--------

- `AGENTS.md`            operator boundaries and resilience notes
- `capture/rpm/`         RPM-only bring-up path (no ansible)
