"""Tests for the one-click component install and the self-update."""

from __future__ import annotations

import hashlib
import io
import os
import json
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import mock

from airman import deps, updater


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(responses: dict[str, bytes]):
    def opener(request, timeout=None):
        return _Response(responses[request.full_url])
    return opener


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


class DepsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.archive = _zip({"ffmpeg-x/bin/ffmpeg.exe": b"MZ fake ffmpeg",
                             "ffmpeg-x/doc/readme.txt": b"docs",
                             "../evil.exe": b"must never be written"})
        self.dep = replace(deps.FFMPEG_WINDOWS, url="https://example.test/ffmpeg.zip",
                           sha256=hashlib.sha256(self.archive).hexdigest(),
                           size=len(self.archive))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_installs_only_the_program(self) -> None:
        target = deps.install(self.dep, self.dir, opener=_opener({self.dep.url: self.archive}))
        self.assertEqual(target.read_bytes(), b"MZ fake ffmpeg")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["ffmpeg.exe"])
        self.assertFalse((self.dir.parent / "evil.exe").exists())

    def test_wrong_checksum_installs_nothing(self) -> None:
        tampered = self.archive + b"x"
        bad = replace(self.dep, size=len(tampered))
        with self.assertRaises(ValueError):
            deps.install(bad, self.dir, opener=_opener({bad.url: tampered}))
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_pinned_downloads_are_https(self) -> None:
        downloads = [deps.FFMPEG_WINDOWS, deps.FFMPEG_WINDOWS_ARM64] + [
            deps.deno_dependency(k) for k in deps.DENO_BUILDS]
        for dep in downloads:
            self.assertTrue(dep.url.startswith("https://"), dep.url)
            self.assertEqual(len(dep.sha256), 64, dep.url)

    def test_every_platform_gets_its_own_deno(self) -> None:
        for key in ("windows-x64", "windows-arm64", "macos-x64", "macos-arm64",
                    "linux-x64", "linux-arm64"):
            dep = deps.deno_dependency(key)
            self.assertIsNotNone(dep, key)
        self.assertTrue(deps.deno_dependency("linux-arm64").url.endswith(
            "aarch64-unknown-linux-gnu.zip"))
        self.assertEqual(deps.deno_dependency("macos-x64").exe, "deno")
        self.assertEqual(deps.deno_dependency("windows-arm64").exe, "deno.exe")

    def test_platform_names(self) -> None:
        self.assertEqual(deps.platform_key("win32", "AMD64"), "windows-x64")
        self.assertEqual(deps.platform_key("win32", "ARM64"), "windows-arm64")
        self.assertEqual(deps.platform_key("darwin", "arm64"), "macos-arm64")
        self.assertEqual(deps.platform_key("darwin", "x86_64"), "macos-x64")
        self.assertEqual(deps.platform_key("linux", "aarch64"), "linux-arm64")

    def test_ffmpeg_comes_from_the_system_package_manager_on_linux(self) -> None:
        with mock.patch.object(deps.shutil, "which",
                               lambda name: "/usr/bin/dnf" if name == "dnf" else None):
            item = deps.ffmpeg_installer("linux-x64")
        self.assertIsInstance(item, deps.Package)
        self.assertEqual(item.command[:3], ("sudo", "dnf", "install"))
        with mock.patch.object(deps.shutil, "which", lambda name: None):
            self.assertIsInstance(deps.ffmpeg_installer("linux-arm64"), deps.Manual)
        self.assertIs(deps.ffmpeg_installer("windows-x64"), deps.FFMPEG_WINDOWS)
        self.assertIs(deps.ffmpeg_installer("windows-arm64"), deps.FFMPEG_WINDOWS_ARM64)

    def test_unix_programs_are_made_executable(self) -> None:
        archive = _zip({"deno": b"ELF fake"})
        dep = replace(deps.deno_dependency("linux-x64"), url="https://example.test/deno.zip",
                      sha256=hashlib.sha256(archive).hexdigest(), size=len(archive))
        target = deps.install(dep, self.dir, opener=_opener({dep.url: archive}))
        self.assertEqual(target.name, "deno")
        if os.name != "nt":
            self.assertTrue(os.access(target, os.X_OK))


class UpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = b"MZ" + b"\0" * (updater.MIN_SIZE + 10)
        base = "https://github.com/pgadient/AirMan/releases/download/v9.9.9/"
        self.exe_url = base + "AirMan-windows-x64.exe"
        self.release = {
            "tag_name": "v9.9.9", "html_url": "https://github.com/x",
            "assets": [
                {"name": "AirMan-windows-x64.exe", "browser_download_url": self.exe_url,
                 "digest": "sha256:" + hashlib.sha256(self.exe).hexdigest()},
                {"name": "AirMan-windows-arm64.exe", "browser_download_url": base + "arm.exe"},
            ],
        }

    def test_versions(self) -> None:
        self.assertGreater(updater.parse_version("v0.10.0"), updater.parse_version("0.9.9"))
        self.assertEqual(updater.parse_version("v1.2.3-beta"), (1, 2, 3))

    def test_asset_per_architecture(self) -> None:
        self.assertEqual(updater.asset_name("AMD64"), "AirMan-windows-x64.exe")
        self.assertEqual(updater.asset_name("ARM64"), "AirMan-windows-arm64.exe")

    def test_check_finds_newer_release_for_this_computer(self) -> None:
        opener = _opener({updater.LATEST_URL: json.dumps(self.release).encode()})
        update = updater.check(opener, current="0.1.0", machine="AMD64")
        self.assertEqual((update.version, update.exe_url), ("9.9.9", self.exe_url))
        self.assertEqual(update.sha256, hashlib.sha256(self.exe).hexdigest())
        arm = updater.check(opener, current="0.1.0", machine="ARM64")
        self.assertTrue(arm.exe_url.endswith("arm.exe"))
        self.assertEqual(arm.sha256, "")  # GitHub gave no checksum: only the other checks
        self.assertIsNone(updater.check(opener, current="9.9.9", machine="AMD64"))
        missing = {**self.release, "assets": self.release["assets"][1:]}
        opener = _opener({updater.LATEST_URL: json.dumps(missing).encode()})
        self.assertIsNone(updater.check(opener, current="0.1.0", machine="AMD64"))

    def test_draft_and_foreign_links_are_ignored(self) -> None:
        draft = {**self.release, "draft": True}
        opener = _opener({updater.LATEST_URL: json.dumps(draft).encode()})
        self.assertIsNone(updater.check(opener, current="0.1.0", machine="AMD64"))
        foreign = {**self.release, "assets": [{**self.release["assets"][0],
                                               "browser_download_url": "https://evil.test/a.exe"}]}
        opener = _opener({updater.LATEST_URL: json.dumps(foreign).encode()})
        self.assertIsNone(updater.check(opener, current="0.1.0", machine="AMD64"))

    def test_only_github(self) -> None:
        self.assertTrue(updater.from_github(self.exe_url))
        self.assertTrue(updater.from_github("https://objects.githubusercontent.com/x"))
        for bad in ("http://github.com/x", "https://github.com.evil.test/x",
                    "https://evil.test/github.com/x", "https://githubusercontent.com.evil.test/x"):
            self.assertFalse(updater.from_github(bad), bad)

    def test_download_checks_program_and_checksum(self) -> None:
        good_sum = hashlib.sha256(self.exe).hexdigest()
        update = updater.Update("9.9.9", self.exe_url, good_sum, "")
        self.assertEqual(updater.download(update, _opener({self.exe_url: self.exe})), self.exe)
        altered = self.exe + b"x"
        with self.assertRaises(ValueError):
            updater.download(update, _opener({self.exe_url: altered}))
        broken = updater.Update("9.9.9", self.exe_url, "", "")
        with self.assertRaises(ValueError):
            updater.download(broken, _opener({self.exe_url: b"<html>Not found</html>"}))

    def test_install_swaps_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp, "AirMan.exe")
            exe.write_bytes(b"old")
            updater.install(b"new", exe)
            self.assertEqual(exe.read_bytes(), b"new")
            updater.cleanup(exe)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["AirMan.exe"])


if __name__ == "__main__":
    unittest.main()
