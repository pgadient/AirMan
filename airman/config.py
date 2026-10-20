"""Configuration, data directory and small file helpers."""

from __future__ import annotations

import dataclasses
import ipaddress
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8770

# Only clients from these networks may talk to the web server at all.
PRIVATE_NETWORKS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

RADIO_API_SERVERS = [
    "https://de1.api.radio-browser.info",
    "https://de2.api.radio-browser.info",
    "https://fi1.api.radio-browser.info",
]


def app_dir() -> Path:
    """Directory the program lives in (next to the .exe when packaged)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    env = os.environ.get("AIRMAN_DATA")
    if env:
        return Path(env).expanduser()
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        # The macOS app is a signed bundle: nothing may be written inside it.
        return Path.home() / "Library" / "Application Support" / "AirMan"
    return app_dir() / "data"


def tools_dir() -> Path:
    """Where AirMan puts helper programs it downloads (ffmpeg, Deno)."""
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        return default_data_dir() / "bin"  # the app bundle itself is read-only
    return app_dir() / "bin"


def restrict_to_user(path: Path) -> None:
    """Only the current user may read this file (passwords, keys, sessions)."""
    if os.name != "nt":
        os.chmod(path, 0o600)
        return
    user = os.environ.get("USERNAME")
    if not user:
        return
    try:
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                       check=False, capture_output=True, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        _LOGGER.debug("Could not restrict access to %s", path)


def write_json_atomic(path: Path, data: Any, private: bool = False) -> None:
    """Write JSON so that a crash never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if private:
        restrict_to_user(tmp)
    os.replace(tmp, path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as ex:
        _LOGGER.warning("Could not read %s (%s), using defaults", path, ex)
        return default


def _find_tool(name: str, configured: str) -> str | None:
    if configured:
        return configured if Path(configured).is_file() else None
    exe = name + (".exe" if os.name == "nt" else "")
    # A copy shipped next to the program wins, so portable installs are self-contained.
    for candidate in (app_dir() / exe, app_dir() / "bin" / exe, tools_dir() / exe):
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "darwin":
        # Apps started from the Finder do not get Homebrew's PATH.
        for folder in ("/opt/homebrew/bin", "/usr/local/bin"):
            if Path(folder, name).is_file():
                return str(Path(folder, name))
    if os.name == "nt":
        # winget installs here; the PATH entry only appears in new shells.
        links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / exe
        if links.is_file():
            return str(links)
    return None


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    https: bool = True
    # Optional plain-HTTP port for old devices that can not use the HTTPS page
    # (0 = off). The same password protects it, but it is not encrypted.
    http_port: int = 0
    tls_cert_file: str = ""
    tls_key_file: str = ""
    allowed_networks: list[str] = field(default_factory=lambda: list(PRIVATE_NETWORKS))
    media_dirs: list[str] = field(default_factory=list)
    youtube_cookies_file: str = ""
    ffmpeg_path: str = ""
    deno_path: str = ""
    cache_max_mb: int = 2000  # old cache folder (only read for songs not moved yet)
    # Size limit of the offline YouTube library (data/yt-streams); 0 = never delete songs.
    offline_max_mb: int = 20000
    support_email: str = "debug@pcproblem.ch"  # where "Report bug" mails go
    auto_update: bool = True  # standalone Windows program: look for updates once a day
    offer_downloads: bool = True  # first start: offer to install missing ffmpeg/Deno
    radio_api_servers: list[str] = field(default_factory=lambda: list(RADIO_API_SERVERS))

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in dataclasses.fields(cls)}
        for key in set(raw) - known:
            _LOGGER.warning("Unknown config key ignored: %s", key)
        cfg = cls(**{k: v for k, v in raw.items() if k in known})
        cfg.validate()
        return cfg

    def save(self, path: Path) -> None:
        write_json_atomic(path, dataclasses.asdict(self))

    def validate(self) -> None:
        if not 1 <= int(self.port) <= 65535:
            raise ValueError(f"Invalid port: {self.port}")
        if self.http_port and not 1 <= int(self.http_port) <= 65535:
            raise ValueError(f"Invalid HTTP port: {self.http_port}")
        if self.http_port and self.http_port == self.port:
            raise ValueError("The HTTP port must differ from the main port")
        self.networks()  # raises on invalid entries
        if bool(self.tls_cert_file) != bool(self.tls_key_file):
            raise ValueError("Set both tls_cert_file and tls_key_file, or neither")
        if self.support_email and not re.fullmatch(r"[^@\s<>\"]+@[^@\s<>\"]+\.[^@\s<>\"]+",
                                                   self.support_email):
            raise ValueError(f"Invalid support_email: {self.support_email}")
        if self.cache_max_mb < 100:
            raise ValueError("cache_max_mb must be at least 100")
        if self.offline_max_mb != 0 and self.offline_max_mb < 100:
            raise ValueError("offline_max_mb must be 0 (keep everything) or at least 100")

    def networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [ipaddress.ip_network(n, strict=False) for n in self.allowed_networks]

    def ffmpeg(self) -> str | None:
        return _find_tool("ffmpeg", self.ffmpeg_path)

    def deno(self) -> str | None:
        return _find_tool("deno", self.deno_path)
