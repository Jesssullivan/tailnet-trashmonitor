Capture host bring-up (RPM-only path)
=====================================

If you don't want to use the ansible role, the trashcam RPM can be
installed by hand:

    sudo dnf install ./trashcam-*.rpm
    sudo cp /etc/trashcam/trashcam.env.example /etc/trashcam/<id>.env
    sudo $EDITOR /etc/trashcam/<id>.env       # set PUSH_URL etc.
    sudo systemctl enable --now trashcam@<id>.service
    journalctl -u trashcam@<id>.service -f

`<id>` is the camera identifier you want this stream to show up as in
the cluster (it becomes the MediaMTX path name). Each camera gets its
own `/etc/trashcam/<id>.env` and its own `trashcam@<id>.service`
instance.

ffmpeg requires libx264 (MediaMTX HLS only outputs H.264 / H.265). On
EL10 this means installing the `ffmpeg` package from rpmfusion-free —
the stock `ffmpeg-free` package has no x264, and the `noopenh264`
package is a stub.


Troubleshooting
---------------

    symptom                              check
    -----------------------------------  ------------------------------------
    Cannot open '/dev/videoN'            DynamicUser group `video` membership;
                                         usermod -aG video <user> won't help —
                                         the unit declares video already
    RTSP push hangs                      tailscale ping <hostname>; firewall
