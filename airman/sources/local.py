"""Music files: uploads (data/uploads) and folders listed in the config (media_dirs).

The "Files" tab also lists the songs of the offline YouTube library, so
everything that plays without internet is in one place.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Callable

from .base import FILE_PROTOCOLS, PreparedAudio, Source, SourceError, Track, ffmpeg_pipe
from .base import DownloadProgress, safe_filename

_LOGGER = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma",
                    ".aiff", ".aif", ".alac", ".mp4", ".webm", ".mka"}
INDEX_TTL = 60.0
MAX_FILES = 50_000
MAX_RESULTS = 200
UPLOADS = "u"  # ref prefix of uploaded files; media folders use their number


class LocalSource(Source):
    name = "local"
    label = "Files"

    def __init__(self, media_dirs: list[str], uploads_dir: Path, ffmpeg: str | None,
                 offline: Callable[[str], list[Track]] | None = None) -> None:
        self._roots = [Path(d).expanduser().resolve() for d in media_dirs]
        self._uploads = uploads_dir.resolve()
        self._uploads.mkdir(parents=True, exist_ok=True)
        # Files being uploaded; only complete files are moved into uploads/.
        self._incoming = uploads_dir.parent / "incomplete" / "uploads"
        self._incoming.mkdir(parents=True, exist_ok=True)
        for leftover in self._incoming.iterdir():  # interrupted uploads
            leftover.unlink(missing_ok=True)
        self._ffmpeg = ffmpeg
        self._offline = offline
        self._index: list[tuple[int, str]] = []
        self._index_time = 0.0

    # ----- listing / search ---------------------------------------------------

    def _build_index(self) -> list[tuple[int, str]]:
        index = []
        for i, root in enumerate(self._roots):
            for dirpath, _dirs, files in os.walk(root, followlinks=False):
                for name in files:
                    if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                        rel = Path(dirpath, name).relative_to(root).as_posix()
                        index.append((i, rel))
                        if len(index) >= MAX_FILES:
                            return index
        index.sort(key=lambda item: item[1].lower())
        return index

    def _uploads_list(self) -> list[Path]:
        files = [p for p in self._uploads.iterdir()
                 if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    async def search(self, query: str) -> list[Track]:
        """Uploads first, then offline YouTube songs, then the media folders.

        An empty query lists everything (newest uploads first).
        """
        words = query.lower().split()

        def matches(text: str) -> bool:
            return all(w in text.lower() for w in words)

        results: list[Track] = []
        for path in await asyncio.to_thread(self._uploads_list):
            if matches(path.name):
                results.append(Track(source=self.name, ref=f"{UPLOADS}:{path.name}",
                                     title=path.stem, subtitle="Upload", offline=True,
                                     size=_size(path)))
        if self._offline:
            results.extend(self._offline(query))
        if self._roots:
            if time.monotonic() - self._index_time > INDEX_TTL:
                self._index = await asyncio.to_thread(self._build_index)
                self._index_time = time.monotonic()
                _LOGGER.debug("Indexed %d local files", len(self._index))
            for root_idx, rel in self._index:
                if len(results) >= MAX_RESULTS:
                    break
                if matches(rel):
                    path = Path(rel)
                    results.append(Track(
                        source=self.name,
                        ref=f"{root_idx}:{rel}",
                        title=path.stem,
                        subtitle=path.parent.as_posix() if path.parent != Path(".") else "",
                        offline=True,
                        size=_size(self._roots[root_idx] / rel),
                    ))
        return results[:MAX_RESULTS]

    # ----- files ------------------------------------------------------------------

    def _resolve(self, ref: str) -> Path:
        prefix, _, rel = ref.partition(":")
        if not rel:
            raise ValueError("Invalid file reference")
        if prefix == UPLOADS:
            root = self._uploads
        elif prefix.isdigit() and int(prefix) < len(self._roots):
            root = self._roots[int(prefix)]
        else:
            raise ValueError("Unknown media folder")
        path = (root / rel).resolve()
        # Blocks ../ tricks and links pointing out of the media folder.
        if not path.is_relative_to(root):
            raise ValueError("File outside media folder")
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError("Not an audio file")
        return path

    def validate(self, track: Track) -> None:
        self._resolve(track.ref)

    def upload_target(self, filename: str) -> Path:
        """A free, safe path in the uploads folder for a file with this name."""
        original = Path(filename.replace("\\", "/")).name  # never keep folders
        suffix = Path(original).suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise ValueError("Only audio files can be uploaded")
        stem = safe_filename(Path(original).stem, 120)
        target = self._uploads / f"{stem}{suffix}"
        counter = 2
        while target.exists():
            target = self._uploads / f"{stem} ({counter}){suffix}"
            counter += 1
        return target

    def incoming_path(self, target: Path) -> Path:
        """Where an upload is written until it is complete."""
        return self._incoming / (target.name + ".part")

    def delete_upload(self, ref: str) -> None:
        if not ref.startswith(f"{UPLOADS}:"):
            raise ValueError("Only uploaded files can be deleted")
        path = self._resolve(ref)
        path.unlink(missing_ok=True)
        _LOGGER.info("Deleted upload %s", path.name)

    async def prepare(self, track: Track, start: float = 0,
                      progress: DownloadProgress | None = None) -> PreparedAudio:
        path = self._resolve(track.ref)
        if not path.is_file():
            raise SourceError("File not found")
        if not self._ffmpeg:
            raise SourceError("ffmpeg is missing")
        return await ffmpeg_pipe(self._ffmpeg, "file:" + str(path), FILE_PROTOCOLS, network=False,
                                 start=start)


def _size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None
