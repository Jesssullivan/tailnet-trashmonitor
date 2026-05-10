{
  description = "tailnet-trashmonitor — webcam streaming dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          name = "trashmonitor";
          packages = with pkgs; [
            # build surface
            bazelisk
            just
            git

            # SPA toolchain
            nodejs_22
            pnpm

            # capture / streaming sanity
            ffmpeg-headless

            # ops
            kubectl
            kubernetes-helm
            kustomize
            kubeconform
            sops
            age
            ansible
            python3Packages.passlib

            # repo hygiene
            gitleaks
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            # Linux-only tooling: RPM build + lint, V4L2 probing. On
            # macOS, use a linux container or CI runner for RPM builds.
            rpm
            rpmlint
            v4l-utils
          ];

          shellHook = ''
            # bazelisk ships as `bazelisk`; expose it as `bazel` so the
            # Justfile + house recipes work unmodified. corepack shims
            # land here too so the SPA picks up the package.json-pinned
            # pnpm + node version rather than nix's bundled pnpm@9.
            export SHIM_BIN_DIR="$PWD/.bazelisk-bin"
            mkdir -p "$SHIM_BIN_DIR"
            ln -sf "$(command -v bazelisk)" "$SHIM_BIN_DIR/bazel"
            corepack enable --install-directory "$SHIM_BIN_DIR" >/dev/null 2>&1 || true
            export PATH="$SHIM_BIN_DIR:$PATH"

            echo "trashmonitor dev shell"
            echo "  just --list  → recipes"
            echo "  bazel info   → bazel sanity"
          '';
        };
      });
}
