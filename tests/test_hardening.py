"""Tests for the protections added after the security review."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import AioHTTPTestCase
from cryptography import x509

from airman import tls
from airman.auth import AuthStore, LoginLimiter
from airman.config import Config
from airman.sources.base import Track, is_public_http_url
from airman.sources.radio import RadioSource
from airman.sources.youtube import YouTubeSource
from airman.web import SESSION_COOKIE, SESSION_COOKIE_PLAIN, create_app

PASSWORD = "unit-test-password"


class LimiterTests(unittest.TestCase):
    def test_attempts_count_before_the_check(self) -> None:
        limiter = LoginLimiter()
        for _ in range(LoginLimiter.FREE_ATTEMPTS):
            limiter.attempt("10.0.0.7")
        self.assertGreater(limiter.retry_after("10.0.0.7"), 0)

    def test_ipv6_clients_share_their_64(self) -> None:
        limiter = LoginLimiter()
        for i in range(LoginLimiter.FREE_ATTEMPTS):
            limiter.attempt(f"fd00:1:2:3::{i + 1}")  # a new address each time
        self.assertGreater(limiter.retry_after("fd00:1:2:3::99"), 0)

    def test_global_budget(self) -> None:
        limiter = LoginLimiter()
        for i in range(LoginLimiter.GLOBAL_LIMIT):
            limiter.attempt(f"10.0.{i}.1")  # spread over many addresses
        self.assertGreater(limiter.retry_after("10.9.9.9"), 0)


class DestinationTests(unittest.TestCase):
    def test_no_requests_into_the_home_network(self) -> None:
        for url in ("http://127.0.0.1:42042/api/state", "http://192.168.1.1/", "http://10.0.0.2/",
                    "http://localhost/", "http://[::1]/", "http://169.254.1.1/", "ftp://x.org/",
                    "file:///C:/Windows/win.ini"):
            self.assertFalse(is_public_http_url(url), url)
        self.assertTrue(is_public_http_url("https://www.youtube.com/watch?v=abcdefghijk"))

    def test_sources_refuse_local_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            youtube = YouTubeSource(Path(tmp, "lib"), Path(tmp, "cache"), None, None, "", 0)
            radio = RadioSource([], None, "test")
            for source, name in ((youtube, "youtube"), (radio, "radio")):
                with self.assertRaises(ValueError):
                    source.validate(Track(name, "http://192.168.1.1/admin", "x"))

    def test_invalid_numbers_are_dropped(self) -> None:
        track = Track.from_dict({"source": "youtube", "ref": "https://x.org/a", "title": "t",
                                 "duration": float("nan")})
        self.assertIsNone(track.duration)


class LibraryTests(unittest.TestCase):
    def test_same_title_and_id_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib = YouTubeSource(Path(tmp, "lib"), Path(tmp, "cache"), None, None, "", 0)
            names = []
            for ref, content in (("https://youtu.be/abcdefghijk", b"one"),
                                 ("https://www.youtube.com/watch?v=abcdefghijk", b"two")):
                track = Track("youtube", ref, "Song", thumb="abcdefghijk")
                file = Path(tmp, f"{len(names)}.webm")
                file.write_bytes(content)
                names.append(lib._add_to_library(YouTubeSource._key(track), track, file))
            self.assertNotEqual(names[0], names[1])
            self.assertEqual((names[0].read_bytes(), names[1].read_bytes()), (b"one", b"two"))


class CertificateTests(unittest.TestCase):
    def test_ca_is_only_for_web_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, ca_file = tls.ensure_certificates(Path(tmp))
            ca = x509.load_pem_x509_certificate(ca_file.read_bytes())
            usage = ca.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            self.assertEqual([u.dotted_string for u in usage], ["1.3.6.1.5.5.7.3.1"])
            constraints = ca.extensions.get_extension_for_class(x509.NameConstraints).value
            dns = [n.value for n in constraints.permitted_subtrees if isinstance(n, x509.DNSName)]
            self.assertTrue(all(n == "localhost" or n.endswith(".local") for n in dns), dns)


class _FakeSpeakers:
    last_speaker = None
    speakers: dict = {}

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def to_list(self) -> list:
        return []

    def group_count(self) -> int:
        return 1

    def preferred_speaker(self) -> None:
        return None


class _FakeSources:
    def all(self) -> list:
        return []


class WebHardeningTests(AioHTTPTestCase):
    async def get_application(self):
        self._tmp = tempfile.TemporaryDirectory()
        auth = AuthStore(Path(self._tmp.name))
        auth.set_password(PASSWORD)
        return create_app(Config(), auth, _FakeSpeakers(), _FakeSources())

    async def asyncTearDown(self) -> None:
        await super().asyncTearDown()
        self._tmp.cleanup()

    async def test_foreign_host_name_is_refused(self) -> None:
        resp = await self.client.get("/", headers={"Host": "evil.example.com"})
        self.assertEqual(resp.status, 403)
        resp = await self.client.get("/", headers={"Host": "localhost"})
        self.assertEqual(resp.status, 200)

    async def test_nan_in_json_is_refused(self) -> None:
        resp = await self.client.post("/api/login", data='{"password": NaN}',
                                      headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status, 400)

    async def test_plain_http_port_has_its_own_cookie(self) -> None:
        # HTTPS is on, but this request comes in without TLS: the optional extra port.
        resp = await self.client.post("/api/login", json={"password": PASSWORD})
        self.assertEqual(resp.status, 200)
        self.assertIn(SESSION_COOKIE_PLAIN, resp.cookies)
        self.assertNotIn(SESSION_COOKIE, resp.cookies)
        token = resp.cookies[SESSION_COOKIE_PLAIN].value
        self.client.session.cookie_jar.clear()
        # The HTTPS cookie name is not accepted on the plain port.
        resp = await self.client.get("/api/state", cookies={SESSION_COOKIE: token})
        self.assertEqual(resp.status, 401)

    async def test_parallel_wrong_passwords_get_locked(self) -> None:
        requests = [self.client.post("/api/login", json={"password": f"wrong-{i}"})
                    for i in range(12)]
        statuses = [r.status for r in await asyncio.gather(*requests)]
        self.assertIn(429, statuses)  # not all twelve were allowed to try
        self.assertLessEqual(statuses.count(401), LoginLimiter.FREE_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
