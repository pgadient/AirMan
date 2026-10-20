"""Logging setup: console, rotating files and an in-memory ring buffer.

The ring buffer feeds the "send logs" button in the web page. Everything that
leaves the program through it is redacted first.
"""

from __future__ import annotations

import collections
import logging
import logging.handlers
import platform
import re
import sys
import threading
from pathlib import Path

RING_SIZE = 5000
FILE_SIZE = 1024 * 1024
FILE_COUNT = 3
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

# Query strings of stream URLs can contain access tokens.
_URL_QUERY = re.compile(r"(https?://[^\s?#\"'<>]+)\?[^\s\"'<>]*")
_SECRET_WORDS = re.compile(r"(?i)(password|passwd|token|session|secret)"
                           r"((?:\s+is)?\s*[=:]\s*)\S+")
# Whole header values: "Cookie: a=1; b=2", "Authorization: Bearer xyz".
_SECRET_HEADERS = re.compile(r"(?im)(cookie|set-cookie|authorization)(\s*[=:]\s*)[^\r\n]+")


def redact(text: str) -> str:
    text = _URL_QUERY.sub(r"\1?…", text)
    text = _SECRET_HEADERS.sub(r"\1\2[hidden]", text)
    return _SECRET_WORDS.sub(r"\1\2[hidden]", text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class RingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = RING_SIZE) -> None:
        super().__init__()
        self._lines: collections.deque[str] = collections.deque(maxlen=capacity)
        self._lock_lines = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001 - logging must never crash the program
            return
        with self._lock_lines:
            self._lines.append(line)

    def text(self) -> str:
        with self._lock_lines:
            return "\n".join(self._lines)


RING = RingBufferHandler()


def setup_logging(verbose: bool, log_dir: Path | None) -> None:
    formatter = RedactingFormatter(FORMAT)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # A windowed program (AirMan.exe) has no console at all.
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG if verbose else logging.INFO)
        console.setFormatter(formatter)
        root.addHandler(console)

    RING.setLevel(logging.DEBUG)
    RING.setFormatter(formatter)
    root.addHandler(RING)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        files = logging.handlers.RotatingFileHandler(
            log_dir / "airman.log", maxBytes=FILE_SIZE, backupCount=FILE_COUNT, encoding="utf-8")
        files.setLevel(logging.DEBUG)
        files.setFormatter(formatter)
        root.addHandler(files)

    # Third-party libraries: useful context, but their debug output is far too chatty.
    levels = {"pyatv": logging.INFO, "zeroconf": logging.WARNING,
              "aiohttp.access": logging.WARNING, "asyncio": logging.WARNING,
              "PIL": logging.WARNING}
    for name, level in levels.items():
        logging.getLogger(name).setLevel(logging.DEBUG if verbose and name == "pyatv" else level)


def system_summary(version: str) -> str:
    try:
        import pyatv.const
        pyatv_version = pyatv.const.__version__
    except Exception:  # noqa: BLE001
        pyatv_version = "?"
    try:
        import yt_dlp.version
        ytdlp_version = yt_dlp.version.__version__
    except Exception:  # noqa: BLE001
        ytdlp_version = "?"
    return (f"AirMan {version} | Python {sys.version.split()[0]} | "
            f"{platform.system()} {platform.release()} ({platform.machine()}) | "
            f"pyatv {pyatv_version} | yt-dlp {ytdlp_version}")
