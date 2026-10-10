# Music Assistant Multi-Provider Watcher

Home Assistant OS add-on to automatically install, persist, and auto-update multiple custom [Music Assistant](https://music-assistant.io) providers across container restarts and Home Assistant upgrades.

## Why this exists

When Music Assistant runs on Home Assistant OS, the server container is recreated from its vanilla Docker image on every reboot or update. Any custom providers placed directly inside the container filesystem are wiped.

This add-on runs in the background, watches the Music Assistant container, and automatically re-injects all configured providers into `/app/venv/lib/python3.X/site-packages/music_assistant/providers/`.

Unlike single-purpose watchers, this add-on allows you to configure **any number of providers** from GitHub repositories or local directories.

---

## Installation

### Method 1: Add as Custom Repository in Home Assistant (Recommended)

1. Push this repository to GitHub (or use your existing fork/URL).
2. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
3. Click the three dots (top right) → **Repositories**.
4. Add the URL of your repository:
   ```
   https://github.com/veronoicc/homeassistant-addons
   ```
5. Click **Add**, then reload the store.
6. Find **Music Assistant Multi-Provider Watcher** under your repository section and click **Install**.
7. **Important:** Go to the add-on's **Info** tab and switch **Protection mode OFF**. (The add-on requires Docker API access to manage providers inside the Music Assistant container).
8. Go to the **Configuration** tab, enter your providers, and click **Start**.

### Method 2: Manual / Local Add-on Install (HAOS Shell / Samba)

Copy the `ma_multi_provider_watcher` folder directly into your local add-ons directory:
- **Inside SSH & Web Terminal add-on / Samba:** `/addons/ma_multi_provider_watcher`
- **HAOS 18+ host path:** `/mnt/data/supervisor/apps/local/ma_multi_provider_watcher`
- **Older HAOS host path:** `/mnt/data/supervisor/addons/local/ma_multi_provider_watcher`

Then:
1. Go to **Settings → Add-ons → Add-on Store → Check for updates**.
2. Install **Music Assistant Multi-Provider Watcher** from **Local add-ons**.
3. Turn **Protection mode OFF** on the Info tab.
4. Configure and Start.

---

## Configuration

In the add-on's **Configuration** tab in Home Assistant:

```yaml
providers:
  # 1. YouTube Music Free provider
  - "https://github.com/sproft/ytmusic-free-provider"

  # 2. Discord Rich Presence provider (or any custom repo)
  - "https://github.com/your-username/discord-presence-provider"

  # 3. Target specific provider in a monorepo / fork
  - "https://github.com/your-username/server@dev:discord_presence"

  # 4. Local path (placed in HA /share or /config via Samba/SFTP)
  - "/share/custom_providers/discord_presence"

auto_update: false
update_interval_hours: 24
```

### Supported Source Formats

| Format | Example | Description |
|---|---|---|
| **Standard Git URL** | `https://github.com/sproft/ytmusic-free-provider` | Clones latest default branch |
| **Pinned Branch / Tag / SHA** | `https://github.com/sproft/ytmusic-free-provider@v1.2.0` | Clones specific tag, branch (`#main` also supported) |
| **Target Provider Domain** | `https://github.com/user/server:discord_presence` | Targets provider `discord_presence` inside a repo |
| **Subpath in Repo** | `https://github.com/user/server//music_assistant/providers/discord_presence` | Points to exact subfolder |
| **Local Folder** | `/share/custom_providers/discord_presence` | Uses folder from HA `/share` or `/config` volume |

---

## How It Works

1. On startup, verifies Docker daemon connectivity.
2. Auto-detects the running Music Assistant container (`app_*_music_assistant` or `addon_*_music_assistant`).
3. Auto-detects the Python environment inside the container (`python3.14`, `python3.13`, etc.).
4. For each configured source:
   - Git URLs are shallow-cloned to `/data/cache/`.
   - Locates `manifest.json` and parses provider domain.
   - Cleans old copy in Music Assistant container and copies fresh provider directory.
5. Restarts Music Assistant container once to load manifests.
6. Music Assistant automatically resolves and installs any external dependencies listed in `manifest.json["requirements"]` (such as `pkce`, `ytmusicapi`, `yt-dlp`).
7. Continuously polls every 10 seconds. When the Music Assistant container is recreated (new container ID), it re-injects all providers automatically.
8. If `auto_update` is enabled, checks Git remotes periodically and pulls new commits without manual intervention.

---

## Troubleshooting

- **Error: "Cannot connect to Docker daemon":** Ensure **Protection mode** is switched **OFF** on the add-on Info tab. Docker API access is mandatory for copying files into the Music Assistant container.
- **Provider does not show in Music Assistant:** Check add-on logs to verify that `manifest.json` was detected and copied. Then check Music Assistant logs under **Settings → Apps → Add** to verify provider initialization.
