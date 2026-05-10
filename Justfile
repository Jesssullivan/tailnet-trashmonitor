# tailnet-trashmonitor — root task runner
# Bazel is the primary build surface (RPMs + OCI image). The SvelteKit
# SPA build runs out-of-band via pnpm + vite; Bazel packages the
# prebuilt static bundle.
#
# Environment variables (with placeholder defaults; override via .env
# at the repo root, gitignored):
#   GHCR_REPO       ghcr.io/<your-org>/tailnet-trashmonitor
#   GHCR_EMAIL      <your-email>
#   TS_TAILNET      <your-tailnet>.ts.net
#   TS_HOSTNAME     trashmonitor              (tailnet hostname of the LB)
#   DNS_ZONE        <your-zone>
#   DNS_HOSTNAME    trashmonitor.<your-zone>
#   CF_API_TOKEN    ...                       (cloudflare token w/ dns:write)
#   TS_API_KEY      ...                       (tailscale api key w/ dns:write)

set shell := ["bash", "-uc"]
set dotenv-load
set positional-arguments

root := justfile_directory()
ghcr_repo := env_var_or_default("GHCR_REPO", "ghcr.io/<your-org>/tailnet-trashmonitor")
ghcr_email := env_var_or_default("GHCR_EMAIL", "<your-email>")
ts_tailnet := env_var_or_default("TS_TAILNET", "<your-tailnet>.ts.net")
ts_hostname := env_var_or_default("TS_HOSTNAME", "trashmonitor")

# ─────────────────────────────────────────────
# Default
# ─────────────────────────────────────────────

[doc("List all available recipes")]
_default:
    @just --list --unsorted

# ─────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────

[doc("First-time setup: install SPA deps via pnpm")]
setup:
    cd {{ root }}/spa && pnpm install

[doc("Start the SPA dev server (proxy /api → VITE_MEDIAMTX_URL)")]
spa-dev:
    cd {{ root }}/spa && pnpm run dev

[doc("Type-check the SPA")]
spa-check:
    cd {{ root }}/spa && pnpm run check

[doc("Lint + prettier-check the SPA")]
spa-lint:
    cd {{ root }}/spa && pnpm run lint

[doc("Format the SPA in place")]
spa-fmt:
    cd {{ root }}/spa && pnpm run format

# ─────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────

[doc("Build the SPA static bundle (writes spa/build/)")]
spa-build:
    cd {{ root }}/spa && pnpm run build

[doc("Build the cross-platform Bazel targets (skips //capture, which needs rpmbuild)")]
build:
    bazel build //server/... //spa/...

[doc("Run all Bazel tests (cross-platform targets only). No-op if no test targets exist.")]
test:
    #!/usr/bin/env bash
    set -u
    code=0
    bazel test //server/... //spa/... || code=$?
    # Exit code 4 = "no tests found", treat as success.
    if [ $code -eq 0 ] || [ $code -eq 4 ]; then exit 0; fi
    exit $code

# ─────────────────────────────────────────────
# Package
# ─────────────────────────────────────────────

[doc("Build the trashcam capture-host RPM")]
rpm:
    bazel build //capture:trashcam-rpm

[doc("Build the cluster OCI image (Caddy + MediaMTX + SPA)")]
image: spa-build
    bazel build //server:image

[doc("Push the image to GHCR_REPO via crane (TAG=0.0.x, defaults to dev)")]
image-push tag="dev": image
    #!/usr/bin/env bash
    set -euo pipefail
    nix shell nixpkgs#crane -c crane push \
        bazel-bin/server/image \
        {{ ghcr_repo }}:{{ tag }}
    # Why crane and not `bazel run //server:image-push`: the bazel runner
    # script picks aspect_bazel_lib's target-platform jq (linux/amd64,
    # matching our --platforms) and can't exec on darwin hosts. On linux
    # CI runners `just bazel-image-push` works.

[doc("Push the image via Bazel oci_push (linux CI only, fails on darwin)")]
bazel-image-push: image
    bazel run //server:image-push

[doc("Load the cluster image into the local docker daemon")]
image-load: spa-build
    bazel run //server:image-load

# ─────────────────────────────────────────────
# Provision capture hosts (over tailnet via ansible)
# ─────────────────────────────────────────────

[doc("Provision a single host (HOST=<inventory-name>); reads sudo pw from -K prompt")]
provision-host host:
    cd {{ root }}/ansible && \
    ansible-playbook playbooks/trashcam.yml --limit {{ host }} -K

[doc("Dry-run the trashcam playbook against a single host (--check --diff)")]
provision-check host:
    cd {{ root }}/ansible && \
    ansible-playbook playbooks/trashcam.yml --limit {{ host }} --check --diff -K

# ─────────────────────────────────────────────
# Deploy (cluster)
# ─────────────────────────────────────────────

[doc("Show what kustomize would apply to the cluster")]
deploy-diff:
    kubectl kustomize {{ root }}/server/k8s | kubectl diff -f - || true

[doc("Apply the cluster manifests (kustomize)")]
deploy:
    kubectl apply -k {{ root }}/server/k8s

[doc("Apply the Prometheus alert rules (lives outside kustomize root)")]
deploy-rules:
    kubectl apply -f {{ root }}/otel/alert-rules.yaml

# ─────────────────────────────────────────────
# Validate
# ─────────────────────────────────────────────

[doc("Reconcile CF DNS + Tailscale split-DNS so DNS_HOSTNAME resolves")]
dns:
    python3 {{ root }}/scripts/dns-bootstrap.py

[doc("Reconcile the ghcr image-pull secret in the trashmonitor namespace")]
ghcr-secret:
    #!/usr/bin/env bash
    set -euo pipefail
    TOKEN="$(gh auth token)"
    USER="$(gh api /user --jq .login)"
    kubectl -n trashmonitor create secret docker-registry ghcr-pull \
        --docker-server=ghcr.io \
        --docker-username="$USER" \
        --docker-password="$TOKEN" \
        --docker-email="{{ ghcr_email }}" \
        --dry-run=client -o yaml \
      | kubectl apply -f -

[doc("Full bootstrap: ghcr secret + image push + k8s apply + DNS")]
bootstrap tag="0.0.1": ghcr-secret (image-push tag) deploy dns
    @echo "bootstrap complete; verify via: just health"

[doc("Live health check: cluster API + every configured stream should be ready")]
health host=("" + ts_hostname + "." + ts_tailnet):
    #!/usr/bin/env bash
    set -euo pipefail
    curl -fsS "http://{{ host }}/api/v3/paths/list" \
      | python3 {{ root }}/scripts/health.py

[doc("Validate Kubernetes manifests with kubeconform")]
k8s-lint:
    kubectl kustomize {{ root }}/server/k8s | kubeconform -strict -summary

[doc("Validate the trashcam RPM with rpmlint")]
rpm-lint: rpm
    rpmlint bazel-bin/capture/trashcam-*.rpm

[doc("Scan for secrets / PII regressions before pushing")]
gitleaks:
    gitleaks detect --no-git --config {{ root }}/.gitleaks.toml --redact --verbose

[doc("Run full local CI (check + lint + build + test + gitleaks)")]
ci: spa-check spa-lint spa-build build test gitleaks
