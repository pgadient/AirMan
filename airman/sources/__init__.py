"""Audio sources. Each one can search and turn a track into playable audio."""

from __future__ import annotations

from pathlib import Path

from .. import __version__
from ..config import Config
from .base import DownloadProgress, PreparedAudio, Source, SourceError, Track, ffmpeg_test_tone
from .local import LocalSource
from .radio import RadioSource
from .youtube import YouTubeSource

__all__ = ["PreparedAudio", "Source", "SourceError", "Track", "Sources"]


class Sources:
    def __init__(self, config: Config, data_dir: Path) -> None:
        ffmpeg = config.ffmpeg()
        self._ffmpeg = ffmpeg
        self.youtube = YouTubeSource(data_dir / "yt-streams", data_dir / "cache", ffmpeg,
                                     config.deno(), config.youtube_cookies_file,
                                     config.offline_max_mb)
        self.local = LocalSource(config.media_dirs, data_dir / "uploads", ffmpeg,
                                 offline=self.youtube.offline_search)
        sources: list[Source] = [
            self.youtube,
            RadioSource(config.radio_api_servers, ffmpeg, f"AirMan/{__version__}"),
            self.local,
        ]
        self._by_name = {s.name: s for s in sources}

    def all(self) -> list[Source]:
        return list(self._by_name.values())

    def get(self, name: str) -> Source:
        try:
            return self._by_name[name]
        except KeyError:
            raise ValueError(f"Unknown source: {name}") from None

    def track_from_dict(self, data: object) -> Track:
        track = Track.from_dict(data)
        self.get(track.source).validate(track)
        return track

    async def prepare(self, track: Track, start: float = 0,
                      progress: DownloadProgress | None = None) -> PreparedAudio:
        return await self.get(track.source).prepare(track, start=start, progress=progress)

    async def test_tone(self) -> PreparedAudio:
        if not self._ffmpeg:
            raise SourceError("ffmpeg is missing")
        return await ffmpeg_test_tone(self._ffmpeg)
