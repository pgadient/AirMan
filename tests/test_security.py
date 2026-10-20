"""Tests for the security-relevant parts. Run: python -m unittest discover -s tests"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import AioHTTPTestCase

from airman.auth import AuthStore, LoginLimiter, hash_password, verify_password
from airman.config import Config
from airman.sources.base import Track
from airman.sources.local import LocalSource
from airman.web import APP_KEY_CONFIG, SESSION_COOKIE, create_app

PASSWORD = "unit-test-password"


class PasswordTests(unittest.TestCase):
    def test_hash_roundtrip(self) -> None:
        stored = hash_password(PASSWORD)
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(verify_password(PASSWORD, stored))
        self.assertFalse(verify_password("wrong", stored))
        self.assertFalse(verify_password(PASSWORD, "garbage"))

    def test_sessions_stored_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auth = AuthStore(Path(tmp))
            auth.set_password(PASSWORD)
            token = auth.create_session()
            self.assertTrue(auth.validate_session(token))
            self.assertNotIn(token, (Path(tmp) / "sessions.json").read_text())
            auth.set_password(PASSWORD + "2")  # new password logs everyone out
            self.assertFalse(auth.validate_session(token))

    def test_limiter_locks_out(self) -> None:
        limiter = LoginLimiter()
        for _ in range(LoginLimiter.FREE_ATTEMPTS):
            limiter.failed("1.2.3.4")
        self.assertGreater(limiter.retry_after("1.2.3.4"), 0)
        self.assertEqual(limiter.retry_after("5.6.7.8"), 0)


class TrackTests(unittest.TestCase):
    def test_rejects_bad_input(self) -> None:
        for bad in (None, "x", {}, {"source": "youtube", "ref": "", "title": "t"},
                    {"source": "youtube", "ref": "x" * 5000, "title": "t"}):
            with self.assertRaises(ValueError):
                Track.from_dict(bad)


class LocalSourceTests(unittest.TestCase):
    def test_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp, "media")
            media.mkdir()
            (media / "song.mp3").write_bytes(b"")
            Path(tmp, "secret.mp3").write_bytes(b"")
            source = LocalSource([str(media)], Path(tmp, "uploads"), ffmpeg=None)
            source.validate(Track("local", "0:song.mp3", "song"))
            for ref in ("0:../secret.mp3", "0:..\\secret.mp3", "1:song.mp3", "x:song.mp3",
                        "0:song.txt", "u:../secret.mp3", "u:..\\media\\song.mp3"):
                with self.assertRaises(ValueError, msg=ref):
                    source.validate(Track("local", ref, "x"))

    def test_upload_names_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            uploads = Path(tmp, "uploads")
            source = LocalSource([], uploads, ffmpeg=None)
            for name in ("../../evil.mp3", "C:\\Windows\\evil.mp3", "a<b>:c?.mp3", "CON.mp3"):
                target = source.upload_target(name)
                self.assertEqual(target.parent, uploads.resolve(), name)
            target = source.upload_target("song.mp3")
            target.write_bytes(b"x")
            self.assertEqual(source.upload_target("song.mp3").name, "song (2).mp3")
            for bad in ("script.exe", "page.html", "noextension"):
                with self.assertRaises(ValueError, msg=bad):
                    source.upload_target(bad)
            source.delete_upload("u:song.mp3")
            self.assertFalse(target.exists())
            with self.assertRaises(ValueError):
                source.delete_upload("0:song.mp3")


class _FakeSpeakers:
    last_speaker = None
    speakers: dict = {}

    def preferred_speaker(self) -> None:
        return None

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def to_list(self) -> list:
        return []

    def group_count(self) -> int:
        return 1


class _FakeSources:
    def all(self) -> list:
        return []


class WebTests(AioHTTPTestCase):
    async def get_application(self):
        self._tmp = tempfile.TemporaryDirectory()
        auth = AuthStore(Path(self._tmp.name))
        auth.set_password(PASSWORD)
        from airman.thumbs import ThumbnailCache
        thumbs = ThumbnailCache(Path(self._tmp.name) / "thumbs", "test")
        return create_app(Config(https=False), auth, _FakeSpeakers(), _FakeSources(), thumbs=thumbs)

    async def asyncTearDown(self) -> None:
        await super().asyncTearDown()
        self._tmp.cleanup()

    async def _login(self) -> None:
        resp = await self.client.post("/api/login", json={"password": PASSWORD})
        self.assertEqual(resp.status, 200)
        self.assertIn(SESSION_COOKIE, resp.cookies)

    async def test_api_requires_login(self) -> None:
        resp = await self.client.get("/api/state")
        self.assertEqual(resp.status, 401)
        await self._login()
        resp = await self.client.get("/api/state")
        self.assertEqual(resp.status, 200)

    async def test_wrong_password(self) -> None:
        resp = await self.client.post("/api/login", json={"password": "nope"})
        self.assertEqual(resp.status, 401)

    async def test_security_headers(self) -> None:
        resp = await self.client.get("/")
        self.assertEqual(resp.status, 200)
        self.assertIn("default-src 'self'", resp.headers["Content-Security-Policy"])
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")

    async def test_cross_site_posts_rejected(self) -> None:
        await self._login()
        resp = await self.client.post("/api/rescan", data="{}",
                                      headers={"Content-Type": "text/plain"})
        self.assertEqual(resp.status, 415)
        resp = await self.client.post("/api/rescan", json={},
                                      headers={"Origin": "http://evil.example"})
        self.assertEqual(resp.status, 403)
        resp = await self.client.post("/api/rescan", json={},
                                      headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(resp.status, 403)

    async def test_thumbnails_need_login_and_valid_id(self) -> None:
        resp = await self.client.get("/thumbs/dQw4w9WgXcQ.jpg")
        self.assertEqual(resp.status, 401)
        await self._login()
        for bad in ("short", "dQw4w9WgXcQ..", "..%2F..%2Fauth"):
            resp = await self.client.get(f"/thumbs/{bad}.jpg")
            self.assertEqual(resp.status, 404, bad)

    async def test_upload_needs_own_header(self) -> None:
        await self._login()
        resp = await self.client.post("/api/upload", data={"file": b"x"})
        self.assertEqual(resp.status, 403)

    async def test_foreign_network_blocked(self) -> None:
        self.app[APP_KEY_CONFIG].allowed_networks = ["10.99.0.0/16"]
        resp = await self.client.get("/")
        self.assertEqual(resp.status, 403)


if __name__ == "__main__":
    unittest.main()
