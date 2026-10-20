"""Entry point for the packaged program.

Windows and macOS start with a tray (menu bar) icon. Linux runs as a server in
the terminal or as a service, configured through data/config.json.
"""

import sys

from airman.__main__ import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if sys.platform != "linux" and not any(
            a in args for a in ("--tray", "--scan", "--set-password", "--help", "-h",
                                "--version", "--check-gui")):
        args = ["--tray", *args]
    sys.exit(main(args))
