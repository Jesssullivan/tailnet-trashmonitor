%global _trashcam_libexec %{_libexecdir}/trashcam

Name:           trashcam
Version:        0.0.1
Release:        1%{?dist}
Summary:        Tailnet webcam capture daemon (ffmpeg + systemd)
License:        MIT
URL:            https://github.com/<your-org>/tailnet-trashmonitor
BuildArch:      noarch

Requires:       ffmpeg
Requires:       systemd
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd

%description
trashcam reads a V4L2 device (typically /dev/videoN) and publishes
H.264-in-RTSP to a central MediaMTX on the tailnet. It is a thin shell
wrapper around ffmpeg, supervised by systemd via the trashcam@.service
template. Configuration lives in /etc/trashcam/<id>.env and is loaded
through EnvironmentFile.

%prep
# No source extraction — Bazel pkg_rpm seeds the build root directly.

%install
install -d %{buildroot}%{_trashcam_libexec}
install -m 0755 trashcam-ffmpeg %{buildroot}%{_trashcam_libexec}/trashcam-ffmpeg

install -d %{buildroot}%{_unitdir}
install -m 0644 trashcam@.service %{buildroot}%{_unitdir}/trashcam@.service
install -m 0644 trashcam.target %{buildroot}%{_unitdir}/trashcam.target

install -d %{buildroot}%{_sysconfdir}/trashcam
install -m 0640 trashcam.env.example %{buildroot}%{_sysconfdir}/trashcam/trashcam.env.example

%files
%{_trashcam_libexec}/trashcam-ffmpeg
%{_unitdir}/trashcam@.service
%{_unitdir}/trashcam.target
%dir %{_sysconfdir}/trashcam
%config(noreplace) %{_sysconfdir}/trashcam/trashcam.env.example

%post
%systemd_post trashcam.target

%preun
%systemd_preun trashcam.target

%postun
%systemd_postun_with_restart trashcam.target

%changelog
* Sat May 10 2026 trashcam maintainers - 0.0.1-1
- Initial package.
