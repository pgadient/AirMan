"""Internet radio via the free radio-browser.info directory."""

from __future__ import annotations

import logging

import aiohttp

from .base import NETWORK_PROTOCOLS, DownloadProgress, PreparedAudio, Source, SourceError, Track
from .base import ffmpeg_pipe, is_http_url, is_public_http_url

_LOGGER = logging.getLogger(__name__)

SEARCH_RESULTS = 25


class RadioSource(Source):
    name = "radio"
    label = "Radio"

    def __init__(self, servers: list[str], ffmpeg: str | None, user_agent: str) -> None:
        self._servers = [s.rstrip("/") for s in servers if is_http_url(s)]
        self._ffmpeg = ffmpeg
        self._user_agent = user_agent

    async def search(self, query: str) -> list[Track]:
        params = {
            "name": query,
            "limit": str(SEARCH_RESULTS),
            "hidebroken": "true",
            "order": "clickcount",
            "reverse": "true",
        }
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"User-Agent": self._user_agent}
        last_error: Exception | None = None
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for server in self._servers:
                try:
                    async with session.get(f"{server}/json/stations/search", params=params) as resp:
                        resp.raise_for_status()
                        stations = await resp.json(content_type=None)
                    tracks = self._to_tracks(stations)
                    _LOGGER.debug("Radio search %r on %s: %d stations", query, server, len(tracks))
                    return tracks
                except (aiohttp.ClientError, TimeoutError, ValueError) as ex:
                    _LOGGER.info("Radio server %s failed: %s", server, ex)
                    last_error = ex
        raise SourceError(f"Radio directory not reachable ({last_error})")

    def _to_tracks(self, stations: object) -> list[Track]:
        tracks = []
        for st in stations if isinstance(stations, list) else []:
            if not isinstance(st, dict):
                continue
            url = st.get("url_resolved") or st.get("url") or ""
            name = str(st.get("name") or "").strip()
            if not name or not isinstance(url, str) or not is_http_url(url):
                continue
            details = [str(st.get("countrycode") or ""), str(st.get("tags") or "")[:60]]
            tracks.append(Track(
                source=self.name,
                ref=url,
                title=name[:300],
                subtitle=" · ".join(d for d in details if d),
                live=True,
            ))
        return tracks

    def validate(self, track: Track) -> None:
        if not is_public_http_url(track.ref):
            raise ValueError("Only streams from the internet are allowed")

    async def prepare(self, track: Track, start: float = 0,
                      progress: DownloadProgress | None = None) -> PreparedAudio:
        if not self._ffmpeg:
            raise SourceError("ffmpeg is missing")
        return await ffmpeg_pipe(self._ffmpeg, track.ref, NETWORK_PROTOCOLS, network=True)
