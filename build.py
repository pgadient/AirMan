"""Build the standalone AirMan program with PyInstaller.

    python -m pip install --require-hashes -r requirements-build.txt
    python build.py

Results in dist/:
- Windows: AirMan.exe, one file with a tray icon.
- macOS:   AirMan.app with a menu bar icon.
- Linux:   AirMan, one file that runs as a server (terminal or systemd).

ffmpeg and Deno are not bundled; AirMan finds them on the PATH or in a bin/
folder next to the program (Windows can download them with one click).
"""

import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "airman" / "__init__.py"


def bump_patch_version() -> str:
    """0.1.1 -> 0.1.2: every delivered update gets a new number."""
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', text)
    if not match:
        raise SystemExit("No __version__ found")
    major, minor, patch = (int(n) for n in match.groups())
    new = f"{major}.{minor}.{patch + 1}"
    VERSION_FILE.write_text(text.replace(match.group(0), f'__version__ = "{new}"'),
                            encoding="utf-8")
    return new


args = sys.argv[1:]
if "--bump" in args:
    args.remove("--bump")
    print("Version", bump_patch_version())

WINDOWS, MACOS = sys.platform == "win32", sys.platform == "darwin"
ICON = ROOT / "airman-icons" / "default" / ("favicon.ico" if WINDOWS else "icon-512.png")

from PyInstaller.utils.hooks.tcl_tk import tcltk_info  # noqa: E402

GUI = []
if WINDOWS or MACOS:
    # The dialogs (settings, password, downloads) load tkinter only when opened;
    # name it so the Tcl/Tk runtime is bundled too.
    GUI = ["--windowed",  # no console window; logs go to data/logs
           "--hidden-import", "tkinter", "--hidden-import", "tkinter.ttk",
           "--hidden-import", "tkinter.filedialog", "--hidden-import", "tkinter.messagebox",
           "--hidden-import", "tkinter.simpledialog"]
    if tcltk_info.available:
        # PyInstaller's hook does not pick up the Tcl/Tk script folders here, so add them
        # where its run-time hook looks for them.
        GUI += ["--add-data", f"{tcltk_info.tcl_data_dir}{os.pathsep}_tcl_data",
                "--add-data", f"{tcltk_info.tk_data_dir}{os.pathsep}_tk_data"]
else:
    # Linux: a server without tray icon or dialogs.
    GUI = ["--console", "--exclude-module", "tkinter", "--exclude-module", "pystray",
           "--exclude-module", "PIL"]

PLATFORM = []
if MACOS:
    # A .app bundle is a folder already; one-file mode makes no sense there.
    PLATFORM = ["--onedir", "--osx-bundle-identifier", "io.github.pgadient.airman"]
else:
    PLATFORM = ["--onefile"]

PyInstaller.__main__.run([
    str(ROOT / "airman_app.py"),
    "--name", "AirMan",
    *PLATFORM,
    "--noconfirm",
    "--clean",
    "--icon", str(ICON),
    "--add-data", f"{ROOT / 'airman' / 'static'}{os.pathsep}airman/static",
    # Loaded dynamically, so PyInstaller can not see them by itself.
    "--collect-submodules", "pyatv",
    "--collect-data", "pyatv",
    "--collect-data", "yt_dlp_ejs",
    *GUI,
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
    *args,
])

if MACOS:
    # Since macOS 15 an app may only search the local network (Bonjour) for the
    # services it names, after asking the user once.
    app = ROOT / "dist" / "AirMan.app"
    info_file = app / "Contents" / "Info.plist"
    with info_file.open("rb") as f:
        info = plistlib.load(f)
    info["NSLocalNetworkUsageDescription"] = (
        "AirMan finds and plays music on the AirPlay speakers in your network.")
    info["NSBonjourServices"] = [  # what pyatv's scan asks for
        "_airplay._tcp", "_raop._tcp", "_airport._tcp", "_companion-link._tcp",
        "_mediaremotetv._tcp", "_touch-able._tcp", "_touch-remote._tcp", "_appletv-v2._tcp",
        "_hscp._tcp", "_device-info._tcp", "_sleep-proxy._udp"]
    with info_file.open("wb") as f:
        plistlib.dump(info, f)
    # Changing Info.plist breaks PyInstaller's ad-hoc signature: sign again.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
