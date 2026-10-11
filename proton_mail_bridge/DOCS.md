# Home Assistant Add-on: Proton Mail Bridge

Proton Mail Bridge runs headlessly inside Home Assistant, exposing local IMAP (port 1143) and SMTP (port 1025) endpoints for Home Assistant automations, IMAP integrations, and email notifications.

## Features

- **Headless Proton Mail Bridge**: Encrypted local IMAP and SMTP relay for your Proton Mail account.
- **Web Terminal Management**: Interactive Ingress terminal accessible directly in Home Assistant sidebar to log in, handle 2FA, and inspect bridge passwords.
- **Persistent Keystore**: Headless `pass` and GnuPG key management persisted across container restarts under `/data`.
- **TLS Certificate Export**: Automatically exports the Bridge TLS certificate to `/ssl/proton-bridge-cert.pem` so clients and Home Assistant integrations can verify the connection.
- **Configurable Ports**: Flexible port mapping via `socat` forwarders.

## Getting Started

1. Start the **Proton Mail Bridge** add-on.
2. Click on **Proton Bridge** in the Home Assistant sidebar to open the Ingress Web Terminal.
3. Select option **1) Log In (Add Proton Account)**.
4. Type `login` at the `>>>` prompt and follow the on-screen instructions to enter your username, password, and two-factor authentication code.
5. Once logged in, type `exit` to return to the manager menu.
6. Select option **2) View Credentials & Connection Info** to view your Bridge application-specific password and connection parameters.
7. Note down your generated password.

## Integrating with Home Assistant

### IMAP Integration (Incoming Email Sensors)
Add the built-in [IMAP integration](https://www.home-assistant.io/integrations/imap/) in Home Assistant:
- **Server**: `127.0.0.1` (or your Home Assistant IP/hostname)
- **Port**: `1143`
- **Username**: Your Proton Mail address
- **Password**: The Bridge-generated password shown in the manager
- **SSL/TLS**: Enable SSL/TLS or STARTTLS (custom certificate available at `/ssl/proton-bridge-cert.pem`)

### SMTP Integration (Outgoing Notifications)
Configure SMTP notifications in your `configuration.yaml`:
```yaml
notify:
  - name: proton_mail
    platform: smtp
    server: "127.0.0.1"
    port: 1025
    sender: "your-email@proton.me"
    username: "your-email@proton.me"
    password: "YOUR_GENERATED_BRIDGE_PASSWORD"
    starttls: true
```

## Configuration Options

| Option | Type | Default | Description |
|---|---|---|---|
| `imap_port` | port | `1143` | Port for the IMAP server |
| `smtp_port` | port | `1025` | Port for the SMTP server |
| `log_level` | list | `info` | Bridge log verbosity (`debug`, `info`, `warning`, `error`) |
| `auto_start_daemon` | bool | `true` | Start bridge daemon automatically on add-on boot |
| `copy_cert_to_ssl` | bool | `true` | Export certificate to `/ssl/proton-bridge-cert.pem` |
