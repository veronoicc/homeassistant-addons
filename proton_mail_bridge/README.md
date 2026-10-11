# Home Assistant Add-on: Proton Mail Bridge

Run Proton Mail Bridge headlessly on Home Assistant to connect local IMAP and SMTP clients to your Proton Mail account.

## Overview

This add-on compiles and packages the official Proton Mail Bridge CLI into an S6-Overlay v3 container. An interactive terminal menu provided via Home Assistant Ingress allows you to authenticate your Proton account, manage two-factor authentication, and retrieve generated mail passwords.

## Architecture

- **Supervisor Init**: S6-Overlay v3 with Bashio integration.
- **Key Storage**: `pass` + GnuPG RSA 2048 key store persisted in `/data`.
- **Bridge Daemon**: Headless background daemon `proton-bridge --noninteractive`.
- **Web Terminal**: `ttyd` running `bridge-manager` accessed through Nginx Ingress proxy.
- **Network Relays**: `socat` forwarding local host connections on ports 1143 and 1025.

See [DOCS.md](DOCS.md) for setup and configuration details.
