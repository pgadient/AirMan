"""Self-update for the standalone Windows program from GitHub releases.

The newest release of the project must contain the program for this computer
(AirMan-windows-x64.exe or AirMan-windows-arm64.exe). Files are only taken from
GitHub over HTTPS (also after redirects), must match the SHA-256 checksum GitHub
lists for the file and must be a complete Windows program.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__

_LOGGER = logging.getLogger(__name__)

REPO = "pgadient/AirMan"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
MIN_SIZE = 1024 * 1024  # anything smaller is an error page or a broken download
MAX_SIZE = 200 * 1024 * 1024
ALLOWED_HOSTS = ("github.com", "api.github.com")
ALLOWED_HOST_SUFFIXES = (".githubusercontent.com",)


def asset_name(machine: str | None = None) -> str:
    """The release file for this computer: Windows on Intel/AMD or on ARM."""
    machine = (machine or platform.machine()).lower()
    return "AirMan-windows-arm64.exe" if machine in ("arm64", "aarch64") else "AirMan-windows-x64.exe"


@dataclass(frozen=True)
class Update:
    version: str
    exe_url: str
    sha256: str  # from GitHub's asset list, empty if GitHub did not provide it
    notes_url: str


def parse_version(text: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in numbers[:3]) or (0,)


def can_update() -> bool:
    """Only the packaged Windows program updates itself (source installs use git)."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def from_github(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host in ALLOWED_HOSTS
                                        or host.endswith(ALLOWED_HOST_SUFFIXES))


def _get(url: str, opener: Callable, accept: str = "application/octet-stream",
         limit: int = 1024 * 1024) -> bytes:
    if not from_github(url):
        raise ValueError(f"Not a GitHub address: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": f"AirMan/{__version__}",
                                                   "Accept": accept})
    with opener(request, timeout=30) as response:
        final = response.geturl() if hasattr(response, "geturl") else url
        if not from_github(final):  # a redirect must not lead away from GitHub
            raise ValueError(f"Redirected away from GitHub: {final}")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response too large")
    return data


def check(opener: Callable = urllib.request.urlopen, current: str = __version__,
          machine: str | None = None) -> Update | None:
    """The newer release, if there is one."""
    release = json.loads(_get(LATEST_URL, opener, "application/vnd.github+json"))
    version = str(release.get("tag_name") or "")
    if release.get("draft") or release.get("prerelease"):
        return None
    if parse_version(version) <= parse_version(current):
        return None
    name = asset_name(machine)
    asset = next((a for a in release.get("assets", []) if a.get("name") == name), None)
    url = str((asset or {}).get("browser_download_url") or "")
    if not (url and from_github(url)):
        _LOGGER.info("Release %s has no %s on GitHub", version, name)
        return None
    digest = str(asset.get("digest") or "")
    sha256 = digest[len("sha256:"):].lower() if digest.startswith("sha256:") else ""
    return Update(version.lstrip("v"), url, sha256, str(release.get("html_url") or ""))


def download(update: Update, opener: Callable = urllib.request.urlopen) -> bytes:
    """The new program, only if it is complete and matches GitHub's checksum."""
    data = _get(update.exe_url, opener, limit=MAX_SIZE)
    if len(data) < MIN_SIZE or not data.startswith(b"MZ"):
        raise ValueError(f"Update {update.version}: download is not a complete program")
    if update.sha256 and hashlib.sha256(data).hexdigest() != update.sha256:
        raise ValueError(f"Update {update.version}: checksum does not match, not installed")
    return data


def install(data: bytes, exe: Path | None = None) -> Path:
    """Replace the running program. Windows allows renaming a running .exe."""
    exe = exe or Path(sys.executable)
    new = exe.with_name(exe.name + ".new")
    old = exe.with_name(exe.name + ".old")
    new.write_bytes(data)
    old.unlink(missing_ok=True)
    os.replace(exe, old)
    try:
        os.replace(new, exe)
    except OSError:
        os.replace(old, exe)  # put the old program back
        raise
    _LOGGER.info("Installed update into %s", exe)
    return exe


def cleanup(exe: Path | None = None) -> None:
    """Remove the previous program after a successful update."""
    exe = exe or Path(sys.executable)
    for leftover in (exe.with_name(exe.name + ".old"), exe.with_name(exe.name + ".new")):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass
