"""YouTube (and other yt-dlp supported sites) via yt-dlp.

Every song is downloaded once, in its original format, into the offline library
(data/yt-streams) with a readable file name, and decoded by ffmpeg while
playing. Played songs therefore work without internet the next time, and the
"Files" tab lists them. index.json in that folder keeps title, channel etc.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import yt_dlp

from .base import FILE_PROTOCOLS, NETWORK_PROTOCOLS, PreparedAudio, Source, SourceError, Track
from .base import VIDEO_ID, DownloadProgress, ffmpeg_pipe, is_http_url, is_public_http_url
from .base import safe_filename

_LOGGER = logging.getLogger(__name__)

SEARCH_RESULTS = 15
MAX_PLAYLIST = 200
MAX_DURATION = 12 * 3600
MAX_FILE_BYTES = 3 * 1024 ** 3  # 12 h of the best YouTube audio is about 1 GB
PARTIAL_MAX_AGE = 3600  # unfinished downloads older than this are leftovers


class _QuietLogger:
    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        _LOGGER.debug("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        _LOGGER.info("yt-dlp: %s", msg)


class YouTubeSource(Source):
    name = "youtube"
    label = "YouTube"

    def __init__(self, offline_dir: Path, legacy_cache: Path, ffmpeg: str | None,
                 deno: str | None, cookies_file: str, max_mb: int,
                 partial_dir: Path | None = None) -> None:
        self._dir = offline_dir
        # Unfinished downloads: outside the library, which only ever holds whole songs.
        self._partial = partial_dir or offline_dir.parent / "incomplete" / "yt-streams"
        self._legacy = legacy_cache  # hashed file names from versions before the library
        self._ffmpeg = ffmpeg
        self._deno = deno
        self._cookies = cookies_file
        self._max_bytes = max_mb * 1024 * 1024
        self._locks: dict[str, asyncio.Lock] = {}
        # Songs being saved in the background while they already play from the internet.
        self._saving: dict[str, asyncio.Task] = {}
        self._in_use: set[Path] = set()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "index.json"
        self._index: dict[str, dict[str, Any]] = self._load_index()
        self._remove_leftovers()
        _LOGGER.debug("YouTube source: deno=%s ffmpeg=%s cookies=%s, %d song(s) offline",
                      deno, ffmpeg, "yes" if cookies_file else "no", len(self._index))

    def _options(self, **extra: Any) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _QuietLogger(),
            # Never fetch extra code from the internet at runtime.
            "remote_components": [],
        }
        if self._deno:
            opts["js_runtimes"] = {"deno": {"path": self._deno}}
        if self._ffmpeg:
            opts["ffmpeg_location"] = self._ffmpeg
        if self._cookies:
            opts["cookiefile"] = self._cookies
        opts.update(extra)
        return opts

    def _extract(self, target: str, **extra: Any) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(self._options(**extra)) as ydl:
            return ydl.extract_info(target, download=False)

    async def search(self, query: str) -> list[Track]:
        if is_http_url(query) and not await asyncio.to_thread(is_public_http_url, query):
            raise SourceError("Only links to the internet are allowed")
        target = query if is_http_url(query) else f"ytsearch{SEARCH_RESULTS}:{query}"
        try:
            info = await asyncio.to_thread(
                self._extract, target, extract_flat="in_playlist", noplaylist=False,
                playlistend=MAX_PLAYLIST,
            )
        except yt_dlp.utils.DownloadError as ex:
            _LOGGER.warning("YouTube search %r failed: %s", query, ex)
            # No internet or YouTube unreachable: offer what is stored offline.
            offline = self.offline_search(query)
            if offline:
                _LOGGER.info("Offering %d offline song(s) for %r", len(offline), query)
                return offline
            raise SourceError(_clean_error(ex)) from ex
        entries = info.get("entries") if info.get("_type") == "playlist" else [info]
        tracks = []
        for entry in entries or []:
            if not entry:
                continue
            url = entry.get("webpage_url") or entry.get("url")
            if not url or not is_http_url(url):
                continue
            tracks.append(Track(
                source=self.name,
                ref=url,
                title=entry.get("title") or url,
                subtitle=entry.get("channel") or entry.get("uploader") or "",
                duration=entry.get("duration"),
                live=bool(entry.get("is_live") or entry.get("live_status") == "is_live"),
                thumb=_youtube_id(entry, url),
            ))
        return tracks

    def validate(self, track: Track) -> None:
        if not is_public_http_url(track.ref):
            raise ValueError("Only links to the internet are allowed")

    # ----- offline library ---------------------------------------------------

    def _load_index(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self._index_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items()
                if isinstance(v, dict) and isinstance(v.get("file"), str)
                and (self._dir / Path(v["file"]).name).is_file()}

    def _save_index(self) -> None:
        tmp = self._index_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._index, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._index_file)

    @staticmethod
    def _key(track: Track) -> str:
        return hashlib.sha256(track.ref.encode("utf-8")).hexdigest()[:24]

    def _offline_path(self, key: str) -> Path | None:
        entry = self._index.get(key)
        if entry:
            path = self._dir / Path(entry["file"]).name
            if path.is_file():
                return path
        return None

    def _add_to_library(self, key: str, track: Track, downloaded: Path) -> Path:
        """Give a downloaded file its readable name and remember its details."""
        tag = track.thumb or key[:12]
        name = safe_filename(f"{track.title} [{tag}]", 150) + downloaded.suffix
        target = self._dir / name
        if target.exists() and self._index.get(key, {}).get("file") != name:
            # Same title and id but another link: never overwrite a different song.
            name = safe_filename(f"{track.title} [{tag}-{key[:8]}]", 150) + downloaded.suffix
            target = self._dir / name
        if downloaded != target:
            os.replace(downloaded, target)
        self._index[key] = {
            "file": name, "ref": track.ref, "title": track.title, "subtitle": track.subtitle,
            "duration": track.duration, "thumb": track.thumb, "saved": time.time(),
        }
        self._save_index()
        return target

    def adopt(self, tracks: list[Track]) -> None:
        """Move songs from the old hashed cache into the library, using known titles."""
        if not self._legacy.is_dir():
            return
        moved = 0
        for track in tracks:
            if track.source != self.name or track.live:
                continue
            key = self._key(track)
            if key in self._index:
                continue
            old = self._legacy_file(key)
            if old is not None:
                self._add_to_library(key, track, old)
                moved += 1
        if moved:
            _LOGGER.info("Moved %d song(s) from the old cache into the offline library", moved)

    def _legacy_file(self, key: str) -> Path | None:
        if not self._legacy.is_dir():
            return None
        for path in self._legacy.glob(key + ".*"):
            if path.suffix not in (".part", ".ytdl", ".tmp") and path.stat().st_size > 0:
                return path
        return None

    def offline_search(self, query: str) -> list[Track]:
        """Songs in the offline library; an empty query lists them all, newest first."""
        words = query.lower().split()
        entries = sorted(self._index.values(), key=lambda e: e.get("saved") or 0, reverse=True)
        tracks = []
        for entry in entries:
            text = f"{entry.get('title', '')} {entry.get('subtitle', '')}".lower()
            if words and not all(w in text for w in words):
                continue
            try:
                track = Track.from_dict({**entry, "source": self.name})
            except ValueError:
                continue
            track.offline = True
            track.size = _file_size(self._dir / Path(str(entry.get("file") or "")).name)
            tracks.append(track)
        return tracks

    async def prepare(self, track: Track, start: float = 0,
                      progress: DownloadProgress | None = None) -> PreparedAudio:
        if not self._ffmpeg:
            raise SourceError("ffmpeg is missing")
        if track.live:
            return await self._prepare_live(track)
        key = self._key(track)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            path = self._offline_path(key)
            if path is None and (old := self._legacy_file(key)) is not None:
                path = self._add_to_library(key, track, old)
            if path is None:
                streaming = await self._stream_while_saving(track, key, start)
                if streaming is not None:
                    return streaming
                if key in self._saving:  # streaming failed, but a download is under way
                    await asyncio.shield(self._saving[key])
                    path = self._offline_path(key)
                if path is None:
                    path = await self._download(track, key, progress)
            else:
                _LOGGER.debug("Offline copy %s for %s", path.name, track.ref)
        os.utime(path)  # most recently played songs stay longest
        prepared = await ffmpeg_pipe(self._ffmpeg, "file:" + str(path), FILE_PROTOCOLS,
                                     network=False, start=start)
        self._in_use.add(path)
        prepared.on_close = lambda: self._in_use.discard(path)
        return prepared

    async def _stream_while_saving(self, track: Track, key: str,
                                   start: float) -> PreparedAudio | None:
        """Play straight from YouTube and save the song in the background.

        Returns None if the direct stream can not be set up; the caller then
        downloads first, as before.
        """
        try:
            info = await asyncio.to_thread(self._extract, track.ref, format="bestaudio/best",
                                           noplaylist=True)
        except yt_dlp.utils.DownloadError as ex:
            _LOGGER.info("Direct stream of %s not possible: %s", track.ref, ex)
            return None
        if _duration_filter(info):
            raise SourceError("Longer than 12 hours")
        url = info.get("url")
        if not url or not is_http_url(url):
            return None
        headers = {k: str(v) for k, v in (info.get("http_headers") or {}).items()}
        if key not in self._saving:
            task = asyncio.create_task(self._save_in_background(track, key))
            self._saving[key] = task
        _LOGGER.info("Streaming %s while saving it (from %.0fs)", track.ref, start)
        return await ffmpeg_pipe(self._ffmpeg, url, NETWORK_PROTOCOLS, network=True,
                                 start=start, headers=headers)

    async def _save_in_background(self, track: Track, key: str) -> None:
        try:
            if self._offline_path(key) is None:
                await self._download(track, key)
        except Exception as ex:  # noqa: BLE001 - the song keeps playing from the internet
            _LOGGER.warning("Saving %s in the background failed: %s", track.ref, ex)
        finally:
            self._saving.pop(key, None)

    async def _prepare_live(self, track: Track) -> PreparedAudio:
        try:
            info = await asyncio.to_thread(self._extract, track.ref, format="bestaudio/best",
                                           noplaylist=True)
        except yt_dlp.utils.DownloadError as ex:
            raise SourceError(_clean_error(ex)) from ex
        url = info.get("url")
        if not url or not is_http_url(url):
            raise SourceError("No playable stream found")
        _LOGGER.debug("Live stream resolved for %s", track.ref)
        return await ffmpeg_pipe(self._ffmpeg, url, NETWORK_PROTOCOLS, network=True)

    async def _download(self, track: Track, key: str,
                        progress: DownloadProgress | None = None) -> Path:
        partial_dir = self._partial
        partial_dir.mkdir(parents=True, exist_ok=True)

        def hook(status: dict[str, Any]) -> None:
            if progress is None or status.get("status") != "downloading":
                return
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            done = status.get("downloaded_bytes")
            fraction = min(1.0, done / total) if total and done is not None else None
            progress(fraction, status.get("eta"))

        def run() -> None:
            opts = self._options(
                progress_hooks=[hook],
                format="bestaudio/best",
                outtmpl=str(partial_dir / (key + ".%(ext)s")),
                noplaylist=True,
                max_filesize=MAX_FILE_BYTES,  # also when a site does not tell the length
                match_filter=_duration_filter,
                overwrites=True,
            )
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([track.ref])

        started = time.monotonic()
        _LOGGER.info("Downloading %s", track.ref)
        try:
            await asyncio.to_thread(run)
        except yt_dlp.utils.DownloadError as ex:
            _LOGGER.warning("Download of %s failed: %s", track.ref, ex)
            raise SourceError(_clean_error(ex)) from ex
        done = [p for p in partial_dir.glob(key + ".*")
                if p.suffix not in (".part", ".ytdl", ".tmp") and p.stat().st_size > 0]
        if not done:
            raise SourceError("Download failed")
        path = self._add_to_library(key, track, done[0])
        _LOGGER.info("Saved %s in %.1fs (%d kB)", path.name, time.monotonic() - started,
                     path.stat().st_size // 1024)
        await asyncio.to_thread(self._trim)
        return path

    def _remove_leftovers(self) -> None:
        """Delete unfinished downloads (e.g. interrupted); finished songs are never touched."""
        partial_dir = self._partial
        if not partial_dir.is_dir():
            return
        now = time.time()
        for path in partial_dir.iterdir():
            try:
                if path.is_file() and now - path.stat().st_mtime > PARTIAL_MAX_AGE:
                    path.unlink()
                    _LOGGER.info("Removed unfinished download %s", path.name)
            except OSError:
                pass

    def _trim(self) -> None:
        """Keep the library below its size limit, dropping the least recently played.

        A limit of 0 keeps every finished song forever.
        """
        self._remove_leftovers()
        if self._max_bytes <= 0:
            return
        entries = []
        for key, entry in self._index.items():
            path = self._dir / Path(entry["file"]).name
            try:
                entries.append((path.stat().st_mtime, path.stat().st_size, key, path))
            except OSError:
                continue
        total = sum(size for _, size, _, _ in entries)
        removed = False
        for _, size, key, path in sorted(entries):
            if total <= self._max_bytes:
                break
            if path in self._in_use:
                continue
            try:
                path.unlink()
            except OSError:
                continue
            total -= size
            self._index.pop(key, None)
            removed = True
            _LOGGER.info("Offline library full: removed %s", path.name)
        if removed:
            self._save_index()


def _youtube_id(entry: dict[str, Any], url: str) -> str:
    """Video id if this is a YouTube video (only those get a preview image)."""
    video_id = entry.get("id") or ""
    is_youtube = (entry.get("ie_key") == "Youtube" or entry.get("extractor_key") == "Youtube"
                  or "youtube.com/" in url or "youtu.be/" in url)
    return video_id if is_youtube and VIDEO_ID.match(video_id) else ""


def _duration_filter(info: dict[str, Any], *, incomplete: bool = False) -> str | None:
    duration = info.get("duration")
    if duration and duration > MAX_DURATION:
        return "Longer than 12 hours"
    return None


def _clean_error(ex: Exception) -> str:
    msg = str(ex).replace("ERROR: ", "")
    # Strip the "[youtube] <id>: " prefix and keep it short.
    if "]" in msg[:20]:
        msg = msg.split(":", 1)[-1].strip()
    return msg[:200]


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None
