"""Multiroom groups: one source on several speakers in sync."""

from __future__ import annotations

import asyncio
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pyatv.interface import MediaMetadata

from airman import airplay
from airman.player import Speaker, SpeakerManager
from airman.sources import Track


def _frames(*pairs: tuple[int, int]) -> bytes:
    """Big-endian 16 bit stereo frames."""
    return b"".join(struct.pack(">hh", left, right) for left, right in pairs)


class SplitterTests(unittest.IsolatedAsyncioTestCase):
    async def test_stereo_left_and_right_outputs(self) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(_frames((100, -200), (300, -400)))
        reader.feed_eof()
        source = airplay.PcmSource(reader, MediaMetadata(title="t"))
        splitter = airplay.ChannelSplitter(source, channels=[None, 0, 1])
        stereo, left, right = splitter.sides
        self.assertEqual(await stereo.readframes(2), _frames((100, -200), (300, -400)))
        self.assertEqual(await left.readframes(2), _frames((100, 100), (300, 300)))
        self.assertEqual(await right.readframes(2), _frames((-200, -200), (-400, -400)))
        await source.close()

    async def test_gain_per_output(self) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(_frames((1000, 1000)))
        reader.feed_eof()
        source = airplay.PcmSource(reader, MediaMetadata(title="t"))
        splitter = airplay.ChannelSplitter(source, gains=lambda: [1.0, 0.5],
                                           channels=[None, None])
        full, half = splitter.sides
        self.assertEqual(await full.readframes(1), _frames((1000, 1000)))
        self.assertEqual(await half.readframes(1), _frames((500, 500)))
        await source.close()


class _FakeSession:
    """Stands in for a RAOP session; 'fail' ends with an error right away."""

    instances: list["_FakeSession"] = []

    def __init__(self, atv, name: str) -> None:
        self.name, self.fail, self.stopped = name, atv == "fail", False
        _FakeSession.instances.append(self)

    async def setup(self) -> None:
        pass

    async def play(self, source, volume, start_ts=None) -> None:
        self.start_ts = start_ts
        if self.fail:
            raise ConnectionError("gone")
        while await source.readframes(352):
            await asyncio.sleep(0)

    def stop(self) -> None:
        self.stopped = True

    async def close(self) -> None:
        pass


class StreamMultiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _FakeSession.instances = []
        patcher = mock.patch.object(airplay, "RaopSession", _FakeSession)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _source(self) -> airplay.PcmSource:
        reader = asyncio.StreamReader()
        reader.feed_data(_frames(*[(1, 2)] * 2000))
        reader.feed_eof()
        return airplay.PcmSource(reader, MediaMetadata(title="t"))

    async def test_group_plays_on_when_one_speaker_drops_out(self) -> None:
        outputs = [airplay.Output("ok", "A", None, 30), airplay.Output("fail", "B", None, 30),
                   airplay.Output("ok", "C", None, 30)]
        await airplay.stream_multi(outputs, self._source())  # no exception: A and C played
        starts = {s.start_ts for s in _FakeSession.instances if not s.fail}
        self.assertEqual(len(starts), 1)  # one shared start time: in sync

    async def test_pair_stops_when_one_side_fails(self) -> None:
        outputs = [airplay.Output("ok", "L", 0, 30), airplay.Output("fail", "R", 1, 30)]
        with self.assertRaises(ConnectionError):
            await airplay.stream_multi(outputs, self._source(), stop_all_on_end=True)

    async def test_error_when_every_speaker_fails(self) -> None:
        outputs = [airplay.Output("fail", "A", None, 30), airplay.Output("fail", "B", None, 30)]
        with self.assertRaises(ConnectionError):
            await airplay.stream_multi(outputs, self._source())


class GroupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = SpeakerManager(sources=None, data_dir=Path(self._tmp.name))  # type: ignore[arg-type]
        for ident in ("kids", "bath", "living"):
            speaker = Speaker(self.manager, ident, {"name": ident})
            speaker.online = True
            self.manager.speakers[ident] = speaker
        self.kids, self.bath, self.living = (self.manager.speakers[i]
                                             for i in ("kids", "bath", "living"))

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    def _playing(self, speaker: Speaker) -> None:
        speaker.status = "playing"
        speaker.queue = [Track("youtube", "https://youtu.be/abcdefghijk", "Lullaby")]
        speaker.index = 0

    async def test_groups_and_who_plays(self) -> None:
        await self.manager.set_group(self.kids, 1)
        await self.manager.set_group(self.bath, 1)
        self.assertEqual({s.id for s in self.manager.group_members(self.kids)}, {"kids", "bath"})
        self.assertEqual(self.manager.group_members(self.living), [self.living])
        self.assertIs(self.manager.playback_target(self.bath), self.bath)  # nothing plays yet
        self._playing(self.kids)
        # The bath card controls what the group plays, and shows it.
        self.assertIs(self.manager.playback_target(self.bath), self.kids)
        shown = self.bath.to_dict()
        self.assertEqual((shown["status"], shown["track"]["title"]), ("playing", "Lullaby"))
        self.assertEqual(shown["group_leader"], "kids")
        self.assertEqual(shown["volume"], self.bath.volume)  # its own volume
        self.assertIs(self.manager.playback_target(self.living), self.living)

    async def test_group_numbers_are_limited(self) -> None:
        self.assertEqual(self.manager.group_count(), 3)
        with self.assertRaises(ValueError):
            await self.manager.set_group(self.kids, 4)
        with self.assertRaises(ValueError):
            await self.manager.set_group(self.kids, -1)

    async def test_joining_a_playing_group_restarts_its_song_there(self) -> None:
        await self.manager.set_group(self.kids, 2)
        self._playing(self.kids)
        with mock.patch.object(Speaker, "play", autospec=True) as play:
            await self.manager.set_group(self.bath, 2)
        play.assert_awaited_once()
        self.assertIs(play.await_args.args[0], self.kids)  # the playing speaker restarts

    async def test_volume_goes_to_the_playing_speaker(self) -> None:
        await self.manager.set_group(self.kids, 1)
        await self.manager.set_group(self.bath, 1)
        self._playing(self.kids)
        atv = mock.Mock()
        atv.audio.set_volume = mock.AsyncMock()
        self.kids._outputs = [(atv, self.bath)]
        await self.bath.set_volume(20)
        atv.audio.set_volume.assert_awaited_with(20.0)
        await self.bath.set_muted(True)
        atv.audio.set_volume.assert_awaited_with(0.0)

    async def test_pair_in_a_group_keeps_its_channels(self) -> None:
        pair = Speaker(self.manager, "pair-1", {"kind": "pair", "name": "Bed",
                                                "members": ["l", "r"], "left_id": "r"})
        self.assertEqual(pair.device_outputs(), [("r", 0), ("l", 1)])
        self.assertEqual(self.kids.device_outputs(), [("kids", None)])

    async def test_group_survives_a_restart(self) -> None:
        await self.manager.set_group(self.kids, 3)
        again = SpeakerManager(sources=None, data_dir=Path(self._tmp.name))  # type: ignore[arg-type]
        self.assertEqual(again.speakers["kids"].group, 3)


if __name__ == "__main__":
    unittest.main()
