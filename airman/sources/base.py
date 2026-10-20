"""Common types for audio sources."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import math
import os
import re
import socket
import subprocess
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_TEXT = 300
MAX_REF = 2000


# (fraction 0..1 or None if unknown, seconds left or None); may be called from a thread.
DownloadProgress = Callable[[float | None, float | None], None]


class SourceError(Exception):
    """Something the user should see, e.g. 'video not available'."""


@dataclass
class Track:
    source: str
    ref: str
    title: str
    subtitle: str = ""
    duration: float | None = None
    live: bool = False
    thumb: str = ""  # YouTube video id for the preview image, or empty
    offline: bool = False  # stored on this computer (shown with a badge)
    size: int | None = None  # bytes of a file on this computer (shown in the list only)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "Track":
        """Build a track from untrusted input (browser or state file)."""
        if not isinstance(data, dict):
            raise ValueError("track must be an object")
        source, ref, title = data.get("source"), data.get("ref"), data.get("title")
        if not all(isinstance(v, str) and v for v in (source, ref, title)):
            raise ValueError("track needs source, ref and title")
        if len(ref) > MAX_REF:
            raise ValueError("track ref too long")
        subtitle = data.get("subtitle") or ""
        thumb = data.get("thumb") if isinstance(data.get("thumb"), str) else ""
        duration = data.get("duration")
        return cls(
            source=source[:40],
            ref=ref,
            title=title[:MAX_TEXT],
            subtitle=str(subtitle)[:MAX_TEXT],
            duration=float(duration) if isinstance(duration, (int, float))
            and math.isfinite(duration) and duration >= 0 else None,
            live=bool(data.get("live", False)),
            thumb=thumb if VIDEO_ID.match(thumb) else "",
        )


@dataclass
class PreparedAudio:
    """An ffmpeg process writing raw PCM (s16be, 44.1 kHz, stereo) to stdout."""

    process: asyncio.subprocess.Process
    on_close: Callable[[], None] | None = None
    stderr_task: asyncio.Task | None = None

    @property
    def stdout(self) -> asyncio.StreamReader:
        assert self.process.stdout is not None
        return self.process.stdout

    @property
    def running(self) -> bool:
        return self.process.returncode is None

    async def close(self) -> None:
        if self.on_close:
            self.on_close()
            self.on_close = None
        if self.process.returncode is None:
            self.process.kill()
        # asyncio only reports the exit once stdout reached EOF, so drain what is left.
        try:
            await asyncio.wait_for(self._drain_and_wait(), timeout=5)
        except asyncio.TimeoutError:
            _LOGGER.warning("ffmpeg (pid %s) did not exit in time", self.process.pid)
        if self.stderr_task:
            self.stderr_task.cancel()
        _LOGGER.debug("ffmpeg (pid %s) closed, exit code %s", self.process.pid,
                      self.process.returncode)

    async def _drain_and_wait(self) -> None:
        while await self.stdout.read(65536):
            pass
        await self.process.wait()


class Source:
    name = ""
    label = ""

    async def search(self, query: str) -> list[Track]:
        raise NotImplementedError

    def validate(self, track: Track) -> None:
        """Raise ValueError if the track can not come from this source."""
        raise NotImplementedError

    async def prepare(self, track: Track, start: float = 0,
                      progress: "DownloadProgress | None" = None) -> PreparedAudio:
        """Start decoding, optionally `start` seconds into the track.

        Sources that download first report how far they are through `progress`.
        """
        raise NotImplementedError


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_filename(name: str, max_length: int = 120) -> str:
    """A file name without folders or characters Windows/macOS/Linux reject."""
    name = _UNSAFE_CHARS.sub("_", name).strip(" ._")
    if name.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                                     *(f"LPT{i}" for i in range(10))}:
        name = "_" + name
    return name[:max_length].rstrip(" .") or "file"


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
                 "youtu.be", "www.youtu.be"}


def is_public_http_url(value: str) -> bool:
    """An http(s) link to the internet, never to this computer or the home network.

    Stops logged-in users from making AirMan (or ffmpeg/yt-dlp) fetch pages from
    devices in the local network. Needs a DNS lookup for unknown hosts.
    """
    if not is_http_url(value):
        return False
    host = (urllib.parse.urlsplit(value).hostname or "").lower()
    if not host:
        return False
    if host in YOUTUBE_HOSTS:
        return True
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except (OSError, UnicodeError):
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            return False
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return False
    return bool(addresses)


def is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://")) and len(value) <= MAX_REF


NETWORK_PROTOCOLS = "http,https,tcp,tls,crypto"
FILE_PROTOCOLS = "file"


# Test signal for stereo pairs: low tone on the left, then high tone on the right, twice.
TEST_TONE = ("aevalsrc=exprs='if(lt(mod(t,4),1.2),0.4*sin(2*PI*330*t),0)|"
             "if(between(mod(t,4),2,3.2),0.4*sin(2*PI*880*t),0)':s=44100:d=8")


async def ffmpeg_pipe(ffmpeg: str, src: str, protocols: str, network: bool,
                      start: float = 0, headers: dict[str, str] | None = None) -> PreparedAudio:
    """Decode anything ffmpeg understands into raw PCM on stdout.

    AirPlay wants big-endian 16 bit samples at 44.1 kHz stereo; ffmpeg delivers
    exactly that. The reader only buffers a few seconds, so ffmpeg is paced by
    the speaker through the pipe.

    The protocol whitelist stops a crafted URL from making ffmpeg read other
    local files or speak unexpected protocols.
    """
    args = ["-protocol_whitelist", protocols]
    if network:
        args += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10"]
        if headers:
            # Some services (YouTube) only serve the stream with the headers yt-dlp used.
            safe = {k: v for k, v in headers.items()
                    if "\r" not in k + v and "\n" not in k + v}
            args += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in safe.items())]
        else:
            args += ["-user_agent", "AirMan"]
    if start > 0:
        args += ["-ss", f"{start:.2f}"]  # before -i: fast seek in the input
    args += ["-i", src]
    return await _run_ffmpeg(ffmpeg, args)


async def ffmpeg_test_tone(ffmpeg: str) -> PreparedAudio:
    return await _run_ffmpeg(ffmpeg, ["-f", "lavfi", "-i", TEST_TONE])


async def _run_ffmpeg(ffmpeg: str, input_args: list[str]) -> PreparedAudio:
    args = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "warning", *input_args, "-vn"]
    args += ["-ac", "2", "-ar", "44100", "-f", "s16be", "pipe:1"]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=flags,
    )
    _LOGGER.debug("ffmpeg (pid %s) started: %s", proc.pid, " ".join(args[1:]))
    task = asyncio.create_task(_log_stderr(proc))
    return PreparedAudio(process=proc, stderr_task=task)


async def _log_stderr(proc: asyncio.subprocess.Process) -> None:
    assert proc.stderr is not None
    while line := await proc.stderr.readline():
        _LOGGER.info("ffmpeg (pid %s): %s", proc.pid,
                     line.decode("utf-8", "replace").rstrip()[:500])
