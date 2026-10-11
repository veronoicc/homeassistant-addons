# Changelog

## 1.0.0

- Initial release of Proton Mail Bridge for Home Assistant.
- Multi-stage build compiling Proton Mail Bridge CLI (`build-nogui`).
- Process supervision via S6-Overlay v3.
- Ingress web terminal powered by `ttyd` and Nginx for interactive login and credential retrieval.
- Headless keychain management using `pass` and GnuPG under `/data`.
- Automated export of TLS certificate to `/ssl/proton-bridge-cert.pem`.
- Configurable IMAP and SMTP ports via `socat` proxying.
- Custom AppArmor security profile.
