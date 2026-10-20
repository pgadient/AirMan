"""Install missing helper programs (ffmpeg, Deno) on the first start.

Downloads are pinned to an exact version and SHA-256 hash: if a single byte
differs, nothing is installed. Only the one program file is taken out of the
archive, never anything else. Where a system package is the better choice
(ffmpeg on macOS and Linux), AirMan offers to run the package manager instead.
Nothing happens without asking first.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config, tools_dir

_LOGGER = logging.getLogger(__name__)

CHUNK = 256 * 1024
Progress = Callable[[str, float], None]  # (message, 0..1)


@dataclass(frozen=True)
class Dependency:
    """A program AirMan downloads itself."""
    name: str
    version: str
    url: str
    sha256: str
    size: int  # bytes, for the progress bar and as an upper limit
    member: str  # path of the program inside the zip (suffix match)
    exe: str
    purpose: str

    def size_mb(self) -> int:
        return round(self.size / 1024 / 1024)

    def describe(self) -> str:
        return f"{self.name} {self.version} – {self.purpose} ({self.size_mb()} MB)"


@dataclass(frozen=True)
class Package:
    """A program installed with the system's package manager."""
    name: str
    command: tuple[str, ...]
    purpose: str

    def describe(self) -> str:
        return f"{self.name} – {self.purpose} (runs: {' '.join(self.command)})"


@dataclass(frozen=True)
class Manual:
    """A program the user has to install; AirMan explains how."""
    name: str
    hint: str
    purpose: str

    def describe(self) -> str:
        return f"{self.name} – {self.purpose}: {self.hint}"


FFMPEG_PURPOSE = "decodes audio (required)"
DENO_PURPOSE = "needed for YouTube"

FFMPEG_WINDOWS = Dependency(
    name="ffmpeg",
    version="9.0.2",
    url="https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip",
    sha256="60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba",
    size=114768076,
    member="/bin/ffmpeg.exe",
    exe="ffmpeg.exe",
    purpose=FFMPEG_PURPOSE,
)

# Windows on ARM: a native build from BtbN/FFmpeg-Builds (gyan.dev has none). Pinned
# to a month-end build, which BtbN keeps for a long time (daily ones are removed).
FFMPEG_WINDOWS_ARM64 = Dependency(
    name="ffmpeg",
    version="9.0.2",
    url="https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-30-13-08/"
        "ffmpeg-n9.0.2-17-g2a571b6068-winarm64-gpl-9.0.zip",
    sha256="6dcd0626f9f6d6c7323565e57410e9f37ed14a85946ec9ea9caff294ca32f5c0",
    size=135510041,
    member="/bin/ffmpeg.exe",
    exe="ffmpeg.exe",
    purpose=FFMPEG_PURPOSE,
)

DENO_VERSION = "2.9.7"
# (file on GitHub, size, sha256) per platform, from the official Deno release.
DENO_BUILDS = {
    "windows-x64": ("deno-x86_64-pc-windows-msvc.zip", 42630221,
                    "a0c3101b4158d1dfb7d6a78a7bf0f3de80c96bb423c152beec8beb22786f2238"),
    "windows-arm64": ("deno-aarch64-pc-windows-msvc.zip", 40847024,
                      "c4c4ac8bfdaa37814bda5c05fc9cdf2154904e2ef8277673a30bdceaaa649807"),
    "macos-x64": ("deno-x86_64-apple-darwin.zip", 42295422,
                  "95daaff11c116a52ad54785e7914c8e9c9cdcaba793c5ed929c74ca2d8e6259a"),
    "macos-arm64": ("deno-aarch64-apple-darwin.zip", 38469316,
                    "5cd46d6268f6f78f5d88bdc7159d20bd44cdaa4b3303474839f87ec6fe7ae25c"),
    "linux-x64": ("deno-x86_64-unknown-linux-gnu.zip", 41596794,
                  "c6527f24f4b16031d3ae4fa9f658d5f11534c8d84ce7dc8502420280919c3490"),
    "linux-arm64": ("deno-aarch64-unknown-linux-gnu.zip", 39821318,
                    "c832298b1ad4422481334855f6003e0f54145762c5a134f20a489511d2f65bbf"),
}

# Linux package managers: (program, install command for ffmpeg)
LINUX_PACKAGE_MANAGERS = [
    ("apt-get", ("sudo", "apt-get", "install", "-y", "ffmpeg")),
    ("dnf", ("sudo", "dnf", "install", "-y", "ffmpeg")),
    ("pacman", ("sudo", "pacman", "-S", "--needed", "--noconfirm", "ffmpeg")),
    ("zypper", ("sudo", "zypper", "--non-interactive", "install", "ffmpeg")),
    ("apk", ("sudo", "apk", "add", "ffmpeg")),
]


def platform_key(system: str | None = None, machine: str | None = None) -> str:
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    os_name = {"win32": "windows", "darwin": "macos"}.get(system, "linux")
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    return f"{os_name}-{arch}"


def deno_dependency(key: str | None = None) -> Dependency | None:
    key = key or platform_key()
    build = DENO_BUILDS.get(key)
    if build is None:
        return None
    file, size, sha256 = build
    return Dependency(
        name="Deno", version=DENO_VERSION,
        url=f"https://github.com/denoland/deno/releases/download/v{DENO_VERSION}/{file}",
        sha256=sha256, size=size, member="deno.exe" if key.startswith("windows") else "deno",
        exe="deno.exe" if key.startswith("windows") else "deno", purpose=DENO_PURPOSE)


def _brew() -> str | None:
    for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("brew")


def ffmpeg_installer(key: str | None = None) -> Dependency | Package | Manual:
    key = key or platform_key()
    if key == "windows-arm64":
        return FFMPEG_WINDOWS_ARM64
    if key.startswith("windows"):
        return FFMPEG_WINDOWS
    if key.startswith("macos"):
        brew = _brew()
        if brew:
            return Package("ffmpeg", (brew, "install", "ffmpeg"), FFMPEG_PURPOSE)
        return Manual("ffmpeg", "install Homebrew from https://brew.sh, then run "
                                "'brew install ffmpeg'", FFMPEG_PURPOSE)
    for program, command in LINUX_PACKAGE_MANAGERS:
        if shutil.which(program):
            return Package("ffmpeg", command, FFMPEG_PURPOSE)
    return Manual("ffmpeg", "install it with your system's package manager", FFMPEG_PURPOSE)


def supported() -> bool:
    """Whether AirMan can offer to install anything here (frozen program or source)."""
    return True


def bin_dir() -> Path:
    return tools_dir()


def missing(config: Config) -> list[Dependency | Package | Manual]:
    """What AirMan needs but can not find, with how to get it."""
    items: list[Dependency | Package | Manual] = []
    if not config.ffmpeg():
        items.append(ffmpeg_installer())
    if not config.deno():
        deno = deno_dependency()
        if deno is not None:
            items.append(deno)
    return items


def install_any(item: Dependency | Package | Manual, progress: Progress | None = None,
                interactive: bool = False) -> None:
    """Install one missing item. Manual items can not be installed: ValueError."""
    if isinstance(item, Dependency):
        install(item, bin_dir(), progress)
    elif isinstance(item, Package):
        run_package_manager(item, progress, interactive)
    else:
        raise ValueError(f"{item.name}: {item.hint}")


def run_package_manager(package: Package, progress: Progress | None = None,
                        interactive: bool = False) -> None:
    """Run the package manager. interactive: in a terminal, so sudo can ask for the
    password there; otherwise (from a window) without input."""
    report = progress or (lambda message, fraction: None)
    report(f"{package.name}: {' '.join(package.command)}", 0.0)
    _LOGGER.info("Installing %s: %s", package.name, " ".join(package.command))
    if interactive:
        result = subprocess.run(list(package.command), check=False)  # noqa: S603
    else:
        result = subprocess.run(list(package.command), check=False,  # noqa: S603
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=1800)
    if result.returncode != 0:
        raise ValueError(f"{package.name}: '{' '.join(package.command)}' failed "
                         f"(exit code {result.returncode})")
    report(f"{package.name}: installed", 1.0)


def install(dep: Dependency, target_dir: Path, progress: Progress | None = None,
            opener: Callable = urllib.request.urlopen) -> Path:
    """Download, verify and unpack one dependency. Returns the installed program."""
    target_dir.mkdir(parents=True, exist_ok=True)
    download = target_dir / f".{dep.exe}.download"
    report = progress or (lambda message, fraction: None)
    try:
        _download(dep, download, report, opener)
        report(f"{dep.name}: unpacking", 1.0)
        target = target_dir / dep.exe
        _extract(download, dep.member, target)
        if os.name != "nt":
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        _LOGGER.info("Installed %s %s to %s", dep.name, dep.version, target)
        return target
    finally:
        download.unlink(missing_ok=True)


def _download(dep: Dependency, path: Path, report: Progress, opener: Callable) -> None:
    _LOGGER.info("Downloading %s %s from %s", dep.name, dep.version, dep.url)
    request = urllib.request.Request(dep.url, headers={"User-Agent": "AirMan"})
    digest = hashlib.sha256()
    done = 0
    limit = int(dep.size * 1.05) + 1024
    with opener(request, timeout=60) as response, open(path, "wb") as out:
        while chunk := response.read(CHUNK):
            done += len(chunk)
            if done > limit:
                raise ValueError(f"{dep.name}: download is larger than expected")
            digest.update(chunk)
            out.write(chunk)
            report(f"{dep.name} {dep.version}: {done // (1024 * 1024)} / {dep.size_mb()} MB",
                   min(1.0, done / dep.size))
    actual = digest.hexdigest()
    if actual != dep.sha256:
        raise ValueError(f"{dep.name}: checksum mismatch (got {actual[:12]}…), not installed")


def _extract(archive: Path, member: str, target: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if n == member or n.endswith(member)]
        if len(names) != 1:
            raise ValueError(f"{member} not found in the archive")
        tmp = target.with_suffix(target.suffix + ".tmp")
        with zf.open(names[0]) as src, open(tmp, "wb") as dst:
            while chunk := src.read(CHUNK):
                dst.write(chunk)
        os.replace(tmp, target)


def ask_in_terminal(config_file: Path) -> None:
    """Linux/terminal start: offer to install what is missing (only if someone can answer)."""
    if not (sys.stdin and sys.stdin.isatty()):
        return
    config = Config.load(config_file)
    items = missing(config)
    if not items or not config.offer_downloads:
        return
    print("\nAirMan needs a few free helper programs:")
    for item in items:
        print(f"  • {item.describe()}")
    installable = [i for i in items if not isinstance(i, Manual)]
    if not installable:
        print()
        return
    try:
        answer = input("Install them now? [Y/n] ").strip().lower()
    except EOFError:
        return
    if answer not in ("", "y", "yes", "j", "ja"):
        config.offer_downloads = False  # do not ask on every start
        config.save(config_file)
        print("OK. Install them yourself, or delete 'offer_downloads' in config.json to be "
              "asked again.\n")
        return

    def show(message: str, fraction: float) -> None:
        print(f"\r  {message:<60}", end="", flush=True)

    for item in installable:
        try:
            install_any(item, show, interactive=True)
            print(f"\r  {item.name}: installed{' ' * 50}")
        except Exception as ex:  # noqa: BLE001 - report and go on with the next one
            print(f"\r  {item.name}: {ex}")
    print()
