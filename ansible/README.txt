trashcam ansible
================

Provisioning for the capture hosts over the tailnet.


Layout
------

    inventory/hosts.yml                       Tailnet-resolved hosts in group `trashcam_hosts`
    inventory/host_vars/capture-host-a.yml    Example per-host inventory (camera list, ffmpeg knobs)
    roles/trashcam/                           Install ffmpeg, drop the wrapper + units, render envs
    playbooks/trashcam.yml                    Top-level play


Usage
-----

From the repo root:

    just rpm                              # build the trashcam RPM via Bazel (optional)
    just provision-host HOST=<host>       # apply role to a single inventory host
    just provision-check HOST=<host>      # --check --diff against a single host

`-K` is passed implicitly by the just recipes — each host needs an
interactive sudo password. To skip the prompt, set
`ansible_become_password` per-host (env var or sops vault).


Cluster RTSP target
-------------------

Each camera publishes to its own per-stream RTSP tailnet hostname,
`rtsp://<id>-rtsp.<your-tailnet>.ts.net:8554/<id>` (e.g. cam-a publishes
to cam-a-rtsp:8554/cam-a). The matching `<id>-rtsp` Service is declared
in `server/k8s/stream-<id>.yaml`. The cluster must be deployed
(`just deploy`) before capture hosts can publish frames.

To override the derived hostname for a specific camera (e.g. while
migrating), set `push_host` on that camera in the inventory's
`trashcam_cameras` list.
