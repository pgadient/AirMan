"""Pairing with Apple TVs that require it (PIN shown on the TV)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pyatv.exceptions

from airman import player
from airman.player import Speaker, SpeakerManager


class _FakeHandler:
    def __init__(self, correct_pin: str = "1234") -> None:
        self.correct_pin = correct_pin
        self.service = SimpleNamespace(credentials=None)
        self.has_paired = False
        self.closed = False
        self._pin = ""

    async def begin(self) -> None:
        pass

    def pin(self, pin: int) -> None:
        self._pin = str(pin).zfill(4)

    async def finish(self) -> None:
        if self._pin != self.correct_pin:
            raise pyatv.exceptions.PairingError("wrong pin")
        self.service.credentials = "secret-credentials"
        self.has_paired = True

    async def close(self) -> None:
        self.closed = True


class PairingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name)
        self.manager = SpeakerManager(sources=None, data_dir=self.data)  # type: ignore[arg-type]
        self.tv = Speaker(self.manager, "TV1", {"name": "Living room"})
        self.tv.needs_pairing = True
        self.tv.config = mock.Mock()
        self.manager.speakers["TV1"] = self.tv
        self.handler = _FakeHandler()
        patcher = mock.patch.object(player.pyatv, "pair", mock.AsyncMock(return_value=self.handler))
        self.pair = patcher.start()
        self.addCleanup(patcher.stop)

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    async def test_right_pin_stores_credentials_privately(self) -> None:
        await self.manager.pair_start("TV1")
        with mock.patch.object(player, "write_json_atomic") as write:
            await self.manager.pair_finish("TV1", "1234")
        calls = {c.args[0].name: c for c in write.call_args_list}
        self.assertEqual(calls["pairings.json"].args[1], {"TV1": "secret-credentials"})
        self.assertTrue(calls["pairings.json"].kwargs.get("private"))
        # The ordinary state file never contains the credentials.
        self.assertNotIn("secret-credentials", json.dumps(calls["state.json"].args[1]))
        self.assertFalse(self.tv.needs_pairing)
        self.assertTrue(self.handler.closed)

    async def test_wrong_pin_is_refused_and_nothing_stored(self) -> None:
        await self.manager.pair_start("TV1")
        with self.assertRaises(ValueError):
            await self.manager.pair_finish("TV1", "9999")
        self.assertTrue(self.tv.needs_pairing)
        self.assertFalse((self.data / "pairings.json").exists())
        self.assertTrue(self.handler.closed)

    async def test_pin_must_be_four_digits(self) -> None:
        await self.manager.pair_start("TV1")
        for pin in ("", "123", "12345", "12a4", "١٢٣٤"):
            with self.assertRaises(ValueError):
                await self.manager.pair_finish("TV1", pin)

    async def test_pin_without_started_pairing_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            await self.manager.pair_finish("TV1", "1234")

    async def test_expired_pairing_is_refused(self) -> None:
        await self.manager.pair_start("TV1")
        ident, handler, started = self.manager._pairing
        self.manager._pairing = (ident, handler, started - player.PAIRING_TIMEOUT - 1)
        with self.assertRaises(ValueError):
            await self.manager.pair_finish("TV1", "1234")

    async def test_stereo_pairs_can_not_be_paired(self) -> None:
        pair = Speaker(self.manager, "pair-X", {"kind": "pair"})
        pair.config = mock.Mock()
        self.manager.speakers["pair-X"] = pair
        with self.assertRaises(ValueError):
            await self.manager.pair_start("pair-X")

    def test_stored_credentials_are_loaded(self) -> None:
        (self.data / "pairings.json").write_text(json.dumps({"TV1": "abc", "bad": 5}))
        manager = SpeakerManager(sources=None, data_dir=self.data)  # type: ignore[arg-type]
        self.assertEqual(manager._pairings, {"TV1": "abc"})


if __name__ == "__main__":
    unittest.main()
