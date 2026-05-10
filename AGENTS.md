# tailnet-trashmonitor — agent guide

## Boundaries

- Owns: capture-host RPM artifacts, the SvelteKit SPA, the cluster
  OCI image (MediaMTX + Caddy + SPA), and the kustomize deployment
  manifests for the `trashmonitor` workload.
- Does not own: tailnet ACLs, cluster-wide Tailscale operator config,
  on-host network configuration, or RouterOS surface. These live
  outside this repo.

## Working rules

- The SPA is static (`adapter-static`). Do not introduce SSR or a
  Node runtime in the cluster image.
- The capture daemon is bare `ffmpeg` under systemd. Do not introduce
  a wrapper daemon without explicit operator sign-off.
- Streaming server is **MediaMTX**, not go2rtc. go2rtc 1.9.7 had an
  unfixable codec-typing bug for the RTP payloads this repo produces
  (`codec_type: ""` empty, every consumer endpoint 500'd). Do not
  switch back without re-validating that bug is fixed upstream.
- Capture hosts use the **full ffmpeg** package (e.g. from
  rpmfusion-free on EL10) for `libx264`. `ffmpeg-free` has no x264
  and stock distro replacements (`noopenh264`) are stubs. MediaMTX
  HLS only outputs H.264 / H.265.

## Resilience

Capture-side `ffmpeg + RTSP-TCP + systemd Restart=on-failure
RestartSec=5s` recovers cleanly from cluster outages on its own.
Spot-checked behavior:

| Outage                                  | Streams green again |
| --------------------------------------- | ------------------- |
| `kubectl delete pod` (rolling)          | ~3s                 |
| `scale --replicas=0` for 37s, then 1    | ~8s after rollout   |

No operator intervention needed during either. The units stay
`active` the whole time; restart counters increment but no journal
errors. If you tune the unit, keep `Restart=on-failure` and a small
`RestartSec`; longer waits make recovery feel sluggish without
buying anything.

## Validation

For SPA changes:

```bash
just spa-check && just spa-lint && just spa-build
```

For RPM changes:

```bash
just rpm && just rpm-lint
```

For k8s changes:

```bash
just k8s-lint && just deploy-diff
```

For secret / PII regressions before pushing:

```bash
just gitleaks
```
