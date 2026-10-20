"""Small preview images for YouTube results, fetched by the server.

The phone never contacts YouTube itself (no IP address or cookies leak to Google,
and the page keeps its strict "same origin only" policy). Only YouTube's image
host is ever contacted, and only for a strictly validated video id.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiohttp

from .sources.base import VIDEO_ID

_LOGGER = logging.getLogger(__name__)

THUMB_URL = "https://i.ytimg.com/vi/{id}/mqdefault.jpg"  # 320 x 180
MAX_BYTES = 300 * 1024
MAX_FILES = 2000


class ThumbnailCache:
    def __init__(self, cache_dir: Path, user_agent: str) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._user_agent = user_agent
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, video_id: str) -> Path | None:
        """Path of the cached JPEG for a YouTube video id, fetching it if needed."""
        if not VIDEO_ID.match(video_id):
            return None
        path = self._dir / f"{video_id}.jpg"
        try:
            async with self._locks.setdefault(video_id, asyncio.Lock()):
                if path.is_file():
                    return path
                data = await self._fetch(video_id)
                if data is None:
                    return None
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(path)
        finally:
            self._locks.pop(video_id, None)
        await asyncio.to_thread(self._trim)
        return path

    async def _fetch(self, video_id: str) -> bytes | None:
        timeout = aiohttp.ClientTimeout(total=6)
        headers = {"User-Agent": self._user_agent}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(THUMB_URL.format(id=video_id),
                                       allow_redirects=False) as resp:
                    if resp.status != 200 or resp.content_type != "image/jpeg":
                        _LOGGER.debug("Thumbnail %s: HTTP %s %s", video_id, resp.status,
                                      resp.content_type)
                        return None
                    # read(n) returns whatever has arrived so far, so loop until the end.
                    data = b""
                    while chunk := await resp.content.read(64 * 1024):
                        data += chunk
                        if len(data) > MAX_BYTES:
                            break
        except (aiohttp.ClientError, TimeoutError) as ex:
            _LOGGER.debug("Thumbnail %s failed: %s", video_id, ex)
            return None
        # A complete JPEG starts with FFD8 and ends with FFD9; never cache half an image.
        if (len(data) > MAX_BYTES or not data.startswith(b"\xff\xd8")
                or not data.rstrip(b"\x00").endswith(b"\xff\xd9")):
            _LOGGER.info("Thumbnail %s rejected (size or format)", video_id)
            return None
        return data

    def _trim(self) -> None:
        files = sorted(self._dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
        for path in files[:max(0, len(files) - MAX_FILES)]:
            try:
                path.unlink()
            except OSError:
                pass
