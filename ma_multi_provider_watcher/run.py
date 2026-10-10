#!/usr/bin/env python3
"""Music Assistant Multi-Provider Watcher Daemon.

Watches the Music Assistant container in Home Assistant OS, downloads and maintains
custom providers from multiple GitHub repositories or local directories, and
re-injects them whenever the container is recreated or updated.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

OPTIONS_FILE = Path("/data/options.json")
CACHE_DIR = Path("/data/cache")
STATE_FILE = Path("/data/installed_state.json")
DEFAULT_PROVIDERS = ["https://github.com/sproft/ytmusic-free-provider"]
MA_NAME_RE = r"^(addon|app)_[0-9a-f]+_music_assistant(_beta|_nightly|_dev)?$"


def log(msg: str, level: str = "INFO") -> None:
    """Print timestamped log line."""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}")
    sys.stdout.flush()


def run_cmd(
    cmd: list[str],
    cwd: str | Path | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command returning stdout/stderr as strings."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def wait_for_docker() -> None:
    """Ensure Docker socket is accessible."""
    while True:
        try:
            res = run_cmd(["docker", "info"], check=False)
            if res.returncode == 0:
                log("Docker daemon connection verified.")
                return
        except Exception:
            pass

        log(
            "Cannot connect to Docker daemon! Verify 'Protection mode' is turned OFF in the add-on Info tab.",
            level="ERROR",
        )
        time.sleep(15)


def find_ma_container() -> tuple[str, str] | None:
    """Find running Music Assistant container name and ID."""
    try:
        # Check running containers
        res = run_cmd(["docker", "ps", "--format", "{{.Names}} {{.ID}}"], check=False)
        if res.returncode != 0:
            return None

        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        # First priority: matches standard MA container naming
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                name, cid = parts[0], parts[1]
                if re.match(MA_NAME_RE, name):
                    return name, cid

        # Second priority: contains music_assistant in name
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                name, cid = parts[0], parts[1]
                if "music_assistant" in name:
                    return name, cid
    except Exception as exc:
        log(f"Error querying Docker containers: {exc}", level="WARNING")

    return None


def get_ma_python_path(container_name: str) -> str | None:
    """Inspect container to locate site-packages/music_assistant/providers."""
    try:
        res = run_cmd(
            ["docker", "exec", container_name, "sh", "-c", "ls /app/venv/lib/ 2>/dev/null"],
            check=False,
        )
        if res.returncode == 0:
            for item in res.stdout.split():
                if re.match(r"^python3\.\d+$", item):
                    return f"/app/venv/lib/{item}/site-packages/music_assistant/providers"
    except Exception as exc:
        log(f"Failed to detect Python version in {container_name}: {exc}", level="WARNING")

    # Fallback to python3.14 then python3.13
    return "/app/venv/lib/python3.14/site-packages/music_assistant/providers"


def load_options() -> dict[str, Any]:
    """Read options from Home Assistant options.json."""
    if OPTIONS_FILE.exists():
        try:
            with open(OPTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log(f"Failed to read {OPTIONS_FILE}: {exc}", level="WARNING")

    return {
        "providers": DEFAULT_PROVIDERS,
        "auto_update": False,
        "update_interval_hours": 24,
    }


def parse_source(entry: str) -> dict[str, Any]:
    """Parse a provider source string into components.
    
    Supported formats:
      - https://github.com/sproft/ytmusic-free-provider
      - https://github.com/sproft/ytmusic-free-provider@v1.2.0
      - https://github.com/sproft/ytmusic-free-provider#main
      - https://github.com/user/server:discord_presence
      - https://github.com/user/server@dev:discord_presence
      - https://github.com/user/server//music_assistant/providers/discord_presence
      - /share/custom_providers/discord_presence
    """
    entry = entry.strip()
    if not entry:
        return {}

    target_provider = None
    subpath = None
    ref = None

    # Check for target provider suffix :<name> (e.g. :discord_presence)
    match_colon = re.search(r":([a-zA-Z0-9_-]+)$", entry)
    if match_colon:
        colon_pos = match_colon.start()
        # Verify not part of protocol (e.g. https://)
        if not (entry.startswith("http://") and colon_pos == 4) and not (
            entry.startswith("https://") and colon_pos == 5
        ):
            target_provider = match_colon.group(1)
            entry = entry[:colon_pos]

    # Check for subpath //sub/path
    if "://" in entry:
        scheme_idx = entry.find("://")
        rest = entry[scheme_idx + 3:]
        if "//" in rest:
            base, sub = rest.split("//", 1)
            entry = entry[: scheme_idx + 3] + base
            subpath = sub.strip("/")
    elif "//" in entry:
        base, sub = entry.split("//", 1)
        entry = base
        subpath = sub.strip("/")

    # Check for @ref or #ref
    if "@" in entry and ("/" in entry or not entry.startswith("@")):
        parts = entry.rsplit("@", 1)
        entry = parts[0]
        ref = parts[1]
    elif "#" in entry:
        parts = entry.rsplit("#", 1)
        entry = parts[0]
        ref = parts[1]

    is_url = bool(re.match(r"^(https?://|git@|git://|ssh://)", entry))
    return {
        "raw": entry,
        "is_url": is_url,
        "location": entry,
        "ref": ref,
        "target_provider": target_provider,
        "subpath": subpath,
    }


def compute_dir_hash(directory: Path) -> str:
    """Calculate recursive SHA-256 hash of directory file contents."""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(directory)):
        for f in sorted(files):
            if f.endswith((".pyc", ".pyo")) or f == ".git":
                continue
            fp = Path(root) / f
            try:
                rel = fp.relative_to(directory)
                h.update(str(rel).encode("utf-8"))
                with open(fp, "rb") as fh:
                    while chunk := fh.read(65536):
                        h.update(chunk)
            except Exception:
                continue
    return h.hexdigest()


def sync_git_repo(url: str, ref: str | None, dest: Path, auto_update: bool = False) -> bool:
    """Clone or fetch Git repository. Return True if updated or newly cloned."""
    if not dest.exists():
        log(f"Cloning {url} (ref: {ref or 'default'}) into cache...")
        dest.parent.mkdir(parents=True, exist_ok=True)
        clone_cmd = ["git", "clone", "--depth", "1"]
        if ref:
            clone_cmd.extend(["--branch", ref])
        clone_cmd.extend([url, str(dest)])

        res = run_cmd(clone_cmd, check=False)
        if res.returncode != 0:
            # If shallow branch clone failed (e.g. ref is commit SHA), clone full and checkout
            log(f"Shallow clone failed, attempting full fetch: {res.stderr.strip()}", level="WARNING")
            res_full = run_cmd(["git", "clone", url, str(dest)], check=False)
            if res_full.returncode != 0:
                log(f"Failed to clone {url}: {res_full.stderr.strip()}", level="ERROR")
                return False
            if ref:
                run_cmd(["git", "checkout", ref], cwd=dest, check=False)
        return True

    if auto_update:
        log(f"Checking for updates in {dest.name} ({url})...")
        try:
            # Fetch latest
            fetch_cmd = ["git", "fetch", "--depth", "1", "origin"]
            if ref:
                fetch_cmd.append(ref)
            run_cmd(fetch_cmd, cwd=dest, check=False)

            # Get current SHA before update
            before_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()
            target_ref = ref if ref else "FETCH_HEAD"
            run_cmd(["git", "reset", "--hard", target_ref], cwd=dest, check=False)
            after_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()

            if before_sha != after_sha:
                log(f"Updated {dest.name} from {before_sha[:8]} to {after_sha[:8]}")
                return True
        except Exception as exc:
            log(f"Failed checking updates for {url}: {exc}", level="WARNING")

    return False


def discover_providers(
    root_dir: Path, target_domain: str | None = None, subpath: str | None = None
) -> list[dict[str, Any]]:
    """Scan directory for valid Music Assistant provider folders containing manifest.json."""
    search_root = root_dir
    if subpath:
        search_root = root_dir / subpath
        if not search_root.exists():
            log(f"Subpath '{subpath}' not found in {root_dir}", level="WARNING")
            return []

    candidates: list[Path] = []
    if (search_root / "manifest.json").is_file():
        candidates.append(search_root)
    else:
        for p in search_root.rglob("manifest.json"):
            parts = p.parts
            # Skip hidden, virtualenvs, tests
            if any(x.startswith(".") or x in ("venv", ".venv", "tests", "docs") for x in parts):
                continue
            candidates.append(p.parent)

    found: list[dict[str, Any]] = []
    for provider_dir in candidates:
        manifest_file = provider_dir / "manifest.json"
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            domain = data.get("domain")
            if not domain:
                continue

            # If user targeted a specific provider, filter
            if target_domain and domain != target_domain:
                continue

            # If user gave a full server repo without specifying domain, avoid overwriting
            # built-in core providers
            if not target_domain and data.get("builtin") is True and len(candidates) > 10:
                continue

            found.append({
                "domain": domain,
                "name": data.get("name", domain),
                "path": provider_dir,
                "version": data.get("version", "unknown"),
                "requirements": data.get("requirements", []),
            })
        except Exception as exc:
            log(f"Error parsing {manifest_file}: {exc}", level="WARNING")

    return found


def install_providers_into_ma(
    container_name: str, ma_dest: str, providers: list[dict[str, Any]]
) -> bool:
    """Copy provider directories into the Music Assistant container."""
    any_installed = False

    for prov in providers:
        domain = prov["domain"]
        src_path = prov["path"]
        name = prov["name"]
        ver = prov["version"]

        log(f"Injecting provider '{name}' ({domain} v{ver}) into {container_name}:{ma_dest}/{domain}...")

        # 1. Clean existing in container to avoid stale residual files
        run_cmd(
            ["docker", "exec", container_name, "rm", "-rf", f"{ma_dest}/{domain}"],
            check=False,
        )

        # 2. Copy folder into container
        res = run_cmd(
            ["docker", "cp", str(src_path), f"{container_name}:{ma_dest}/{domain}"],
            check=False,
        )
        if res.returncode != 0:
            log(f"Failed to copy {domain} into container: {res.stderr.strip()}", level="ERROR")
            continue

        log(f"Successfully installed provider '{domain}' ({name}).")
        any_installed = True

    return any_installed


def restart_ma(container_name: str) -> bool:
    """Restart Music Assistant container to load new providers."""
    log(f"Restarting Music Assistant container '{container_name}'...")
    res = run_cmd(["docker", "restart", container_name], check=False)
    if res.returncode == 0:
        log("Music Assistant restarted successfully.")
        return True

    log(f"Failed to restart Music Assistant: {res.stderr.strip()}", level="ERROR")
    return False


def process_all_providers(
    container_name: str, ma_dest: str, auto_update: bool = False
) -> list[dict[str, Any]]:
    """Process all configured providers and install into Music Assistant."""
    options = load_options()
    sources = options.get("providers", DEFAULT_PROVIDERS)
    if not sources:
        log("No provider sources configured.", level="WARNING")
        return []

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_discovered: list[dict[str, Any]] = []

    for entry in sources:
        parsed = parse_source(entry)
        if not parsed:
            continue

        loc = parsed["location"]
        target = parsed["target_provider"]
        subpath = parsed["subpath"]
        ref = parsed["ref"]

        if parsed["is_url"]:
            # Create safe cache folder name
            clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", loc.split("/")[-1])
            repo_cache = CACHE_DIR / clean_name
            sync_git_repo(loc, ref, repo_cache, auto_update=auto_update)
            discovered = discover_providers(repo_cache, target, subpath)
        else:
            local_path = Path(loc)
            if not local_path.exists():
                log(f"Local provider path does not exist: {loc}", level="WARNING")
                continue
            discovered = discover_providers(local_path, target, subpath)

        all_discovered.extend(discovered)

    if all_discovered:
        install_providers_into_ma(container_name, ma_dest, all_discovered)
    else:
        log("No providers found to install across configured sources.", level="WARNING")

    return all_discovered


def main() -> None:
    """Daemon entrypoint."""
    log("Music Assistant Multi-Provider Watcher starting up...")
    wait_for_docker()

    # Track container & update timers
    last_container_id: str | None = None
    last_container_name: str | None = None
    last_update_check: float = time.time()

    while True:
        ma_info = find_ma_container()
        if not ma_info:
            log("Music Assistant container not running; waiting 10s...", level="INFO")
            last_container_id = None
            time.sleep(10)
            continue

        container_name, container_id = ma_info
        ma_dest = get_ma_python_path(container_name)
        if not ma_dest:
            log("Could not resolve providers path in Music Assistant container; retrying in 10s...", level="WARNING")
            time.sleep(10)
            continue

        # Check if container was recreated or watcher just started
        if container_id != last_container_id:
            if last_container_id is None:
                log(f"Music Assistant found ({container_name}, id: {container_id[:12]}). Performing initial install...")
            else:
                log(
                    f"Music Assistant container recreation detected! (old: {last_container_id[:12]}, new: {container_id[:12]}). Reinstalling providers...",
                    level="INFO",
                )

            installed = process_all_providers(container_name, ma_dest, auto_update=False)
            if installed:
                restart_ma(container_name)

            last_container_id = container_id
            last_container_name = container_name

        # Check for auto-updates if enabled
        options = load_options()
        auto_update = options.get("auto_update", False)
        interval_hours = max(1, int(options.get("update_interval_hours", 24)))
        interval_seconds = interval_hours * 3600

        now = time.time()
        if auto_update and (now - last_update_check) >= interval_seconds:
            log("Scheduled auto-update interval reached. Checking for provider updates...")
            installed = process_all_providers(container_name, ma_dest, auto_update=True)
            if installed:
                restart_ma(container_name)
            last_update_check = now

        time.sleep(10)


if __name__ == "__main__":
    main()
