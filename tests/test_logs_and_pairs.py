"""Tests for log redaction and stereo pair detection."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from airman.logbuffer import RingBufferHandler, redact
from airman.player import SpeakerManager

GID = "0F1E2D3C-4B5A-4968-8776-655443322110+0+00112233"


class RedactTests(unittest.TestCase):
    def test_url_query_removed(self) -> None:
        text = redact("stream https://radio.example/live.mp3?token=abc123&x=1 failed")
        self.assertNotIn("abc123", text)
        self.assertIn("https://radio.example/live.mp3?…", text)

    def test_secret_words(self) -> None:
        for line in ("password=hunter2", "Cookie: airman_session=xyz", "token: 123"):
            self.assertNotIn(line.split()[-1].split("=")[-1], redact(line), line)

    def test_ring_buffer_keeps_latest(self) -> None:
        ring = RingBufferHandler(capacity=3)
        ring.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test.ring")
        logger.addHandler(ring)
        logger.propagate = False
        for i in range(5):
            logger.warning("line %d", i)
        self.assertEqual(ring.text().splitlines(), ["line 2", "line 3", "line 4"])


def _conf(name: str, ident: str, address: str, props: dict) -> SimpleNamespace:
    service = SimpleNamespace(identifier=ident)
    return SimpleNamespace(name=name, identifier=ident.lower(), address=address,
                           get_service=lambda protocol: service)


class PairTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = SpeakerManager(sources=None, data_dir=Path(self._tmp.name))  # type: ignore[arg-type]
        from airman.player import Speaker
        for ident, name in (("A", "Left Speaker"), ("B", "Right Speaker")):
            self.manager.speakers[ident] = Speaker(self.manager, ident, {"name": name})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _members(self, model: str = "AudioAccessory5,1"):
        base = {"gid": GID, "gpn": "Bedroom", "tsid": "0F1E2D3C", "model": model}
        return [
            (_conf("Left Speaker", "A", "192.168.1.20", {}), {**base, "igl": "0"}),
            (_conf("Right Speaker", "B", "192.168.1.21", {}), {**base, "igl": "1"}),
        ]

    def test_pair_created_with_leader(self) -> None:
        seen: set = set()
        self.manager._update_pair("0F1E2D3C", self._members(), seen)
        pair = self.manager.speakers["pair-0F1E2D3C"]
        self.assertEqual(pair.name, "Bedroom")
        self.assertEqual(pair.target_id, "B")
        self.assertEqual(pair.address, "192.168.1.21")
        self.assertEqual(sorted(pair.members), ["A", "B"])
        self.assertIn(pair.left_id, ("A", "B"))
        # Members are hidden while the pair is used as a pair, shown when split.
        visible = {s.id for s in self.manager._visible()}
        self.assertEqual(visible, {"pair-0F1E2D3C"})
        pair.split = True
        visible = {s.id for s in self.manager._visible()}
        self.assertEqual(visible, {"A", "B"})

    def test_balance_gain_per_device(self) -> None:
        self.manager._update_pair("0F1E2D3C", self._members(), set())
        pair = self.manager.speakers["pair-0F1E2D3C"]
        pair.left_id = "A"
        self.assertEqual((pair.device_gain("A"), pair.device_gain("B")), (1.0, 1.0))
        pair.balance = -0.4  # towards the left: the right one gets quieter
        self.assertEqual(pair.device_gain("A"), 1.0)
        self.assertAlmostEqual(pair.device_gain("B"), 0.6)
        pair.balance = 1.0
        self.assertEqual((pair.device_gain("A"), pair.device_gain("B")), (0.0, 1.0))

    def test_apply_gain(self) -> None:
        import struct
        from airman.airplay import _apply_gain
        data = struct.pack(">4h", 1000, -1000, 32767, -32768)
        self.assertEqual(struct.unpack(">4h", _apply_gain(data, 0.5)), (500, -500, 16383, -16384))
        self.assertEqual(_apply_gain(data, 1.0), data)

    def test_last_speaker_maps_to_pair(self) -> None:
        self.manager._update_pair("0F1E2D3C", self._members(), set())
        self.manager.last_speaker = "A"
        self.assertEqual(self.manager.preferred_speaker(), "pair-0F1E2D3C")

    def test_non_homepod_group_ignored(self) -> None:
        self.manager._update_pair("0F1E2D3C", self._members(model="AppleTV11,1"), set())
        self.assertNotIn("pair-0F1E2D3C", self.manager.speakers)


class ContinueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        from airman.player import Speaker
        from airman.sources.base import Track
        self.manager = SpeakerManager(sources=None, data_dir=Path(self._tmp.name))  # type: ignore[arg-type]
        self.speaker = Speaker(self.manager, "S", {"name": "Test"})
        self.calls: list = []

        async def fake_play(tracks, index=0, start=0):
            self.calls.append((tracks[0].title, start))

        self.speaker.play = fake_play  # type: ignore[method-assign]
        self.song = Track("youtube", "https://x/1", "Song", duration=600)
        self.radio = Track("radio", "https://x/r", "Radio", live=True)

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    async def test_continue_at_saved_position(self) -> None:
        self.speaker.resume, self.speaker.resume_position = self.song, 123.0
        await self.speaker.continue_playing()
        self.assertEqual(self.calls, [("Song", 123.0)])

    async def test_continue_near_end_starts_over(self) -> None:
        self.speaker.resume, self.speaker.resume_position = self.song, 598.0
        await self.speaker.continue_playing()
        self.assertEqual(self.calls, [("Song", 0.0)])

    async def test_continue_live_starts_fresh(self) -> None:
        self.speaker.resume, self.speaker.resume_position = self.radio, 50.0
        await self.speaker.continue_playing()
        self.assertEqual(self.calls, [("Radio", 0.0)])

    async def test_continue_without_resume_uses_history(self) -> None:
        self.speaker.history = [self.song]
        await self.speaker.continue_playing()
        self.assertEqual(self.calls, [("Song", 0.0)])

    async def test_pause_keeps_position_stop_forgets_it(self) -> None:
        self.speaker.resume, self.speaker.resume_position = self.song, 77.0
        await self.speaker.pause()
        self.assertEqual(self.speaker.resume_position, 77.0)
        await self.speaker.stop_and_forget()
        self.assertEqual((self.speaker.resume.title, self.speaker.resume_position), ("Song", 0.0))

    def test_resume_survives_restart(self) -> None:
        from airman.player import Speaker
        self.speaker.resume, self.speaker.resume_position = self.song, 42.0
        again = Speaker(self.manager, "S", self.speaker.to_saved())
        self.assertEqual((again.resume.title, again.resume_position), ("Song", 42.0))


class PlaylistTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        from airman.player import Speaker
        from airman.sources.base import Track
        self.manager = SpeakerManager(sources=None, data_dir=Path(self._tmp.name))  # type: ignore[arg-type]
        self.speaker = Speaker(self.manager, "S", {"name": "Test"})
        self.plays: list = []

        async def fake_play(tracks, index=0, start=0):
            self.speaker.queue, self.speaker.index = list(tracks), index
            self.speaker.status = "playing"
            self.plays.append(tracks[index].title)

        self.speaker.play = fake_play  # type: ignore[method-assign]
        self.t = {n: Track("youtube", f"https://x/{n}", n) for n in "ABCD"}

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    def titles(self) -> list:
        return [t.title for t in self.speaker.queue]

    async def test_enqueue_starts_when_idle_then_appends(self) -> None:
        await self.speaker.enqueue([self.t["A"]])
        await self.speaker.enqueue([self.t["B"], self.t["C"]])
        self.assertEqual(self.titles(), ["A", "B", "C"])
        self.assertEqual(self.plays, ["A"])  # second add did not interrupt

    async def test_move_keeps_current_song(self) -> None:
        await self.speaker.enqueue([self.t[n] for n in "ABCD"])
        self.speaker.index = 1  # B is playing
        await self.speaker.queue_move(1, 3)
        self.assertEqual(self.titles(), ["A", "C", "D", "B"])
        self.assertEqual(self.speaker.queue[self.speaker.index].title, "B")
        await self.speaker.queue_move(0, 3)  # A moves behind the current song
        self.assertEqual(self.speaker.queue[self.speaker.index].title, "B")

    async def test_remove(self) -> None:
        await self.speaker.enqueue([self.t[n] for n in "ABCD"])
        self.speaker.index = 2  # C is playing
        await self.speaker.queue_remove(0)
        self.assertEqual(self.speaker.queue[self.speaker.index].title, "C")
        await self.speaker.queue_remove(self.speaker.index)  # remove the playing song
        self.assertEqual(self.titles(), ["B", "D"])
        self.assertEqual(self.plays[-1], "D")  # continues with the next one

    def test_playlist_survives_restart(self) -> None:
        from airman.player import Speaker
        self.speaker.queue, self.speaker.index = [self.t["A"], self.t["B"]], 1
        again = Speaker(self.manager, "S", self.speaker.to_saved())
        self.assertEqual(([t.title for t in again.queue], again.index), (["A", "B"], 1))


class OfflineLibraryTests(unittest.TestCase):
    def test_adopt_and_search(self) -> None:
        from airman.sources.base import Track
        from airman.sources.youtube import YouTubeSource
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp, "cache")
            legacy.mkdir()
            song = Track("youtube", "https://www.youtube.com/watch?v=abcdefghijk",
                         "Mozart: Wiegenlied?", "Spieluhr", 18, thumb="abcdefghijk")
            key = YouTubeSource._key(song)
            Path(legacy, key + ".webm").write_bytes(b"audio")
            lib = YouTubeSource(Path(tmp, "yt-streams"), legacy, None, None, "", 100)
            lib.adopt([song])
            files = [p.name for p in Path(tmp, "yt-streams").iterdir() if p.suffix == ".webm"]
            self.assertEqual(files, ["Mozart_ Wiegenlied_ [abcdefghijk].webm"])
            found = lib.offline_search("wiegenlied")
            self.assertEqual([(t.title, t.offline) for t in found], [("Mozart: Wiegenlied?", True)])
            self.assertEqual(lib.offline_search("nothing"), [])
            again = YouTubeSource(Path(tmp, "yt-streams"), legacy, None, None, "", 100)
            self.assertEqual(len(again.offline_search("")), 1)  # index survives a restart

    def test_keep_forever_and_leftovers(self) -> None:
        import os
        import time
        from airman.sources.base import Track
        from airman.sources.youtube import YouTubeSource
        with tempfile.TemporaryDirectory() as tmp:
            lib_dir = Path(tmp, "yt-streams")
            lib = YouTubeSource(lib_dir, Path(tmp, "cache"), None, None, "", 0)  # keep forever
            for i in range(3):
                song = Track("youtube", f"https://x/{i}", f"Song {i}")
                download = Path(tmp, f"{i}.webm")
                download.write_bytes(b"x" * 1024 * 1024)
                lib._add_to_library(YouTubeSource._key(song), song, download)
            partial = Path(tmp, "incomplete", "yt-streams")
            partial.mkdir(parents=True)
            old_part = partial / "abc.webm.part"
            old_part.write_bytes(b"half")
            os.utime(old_part, (time.time() - 7200, time.time() - 7200))
            fresh_part = partial / "def.webm.part"  # a download in progress right now
            fresh_part.write_bytes(b"half")
            lib._trim()
            self.assertEqual(len(lib.offline_search("")), 3)  # nothing finished was deleted
            self.assertFalse(old_part.exists())
            self.assertTrue(fresh_part.exists())


if __name__ == "__main__":
    unittest.main()
