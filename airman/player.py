"""Speaker discovery and one independent player per speaker.

HomePods configured as a stereo pair in the Home app show up as two devices
sharing a group id. Streaming to the pair's leader only reaches that one HomePod,
so AirMan presents the pair as one speaker and sends the left channel to one
HomePod and the right channel to the other, in sync (see airplay.py).
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable

import pyatv
import pyatv.exceptions
from pyatv.const import PairingRequirement, Protocol
from pyatv.interface import AppleTV, BaseConfig, MediaMetadata

from .airplay import Output, PcmSource, stream_multi
from .config import read_json, write_json_atomic
from .sources import PreparedAudio, Sources, SourceError, Track

_LOGGER = logging.getLogger(__name__)

REPEAT_MODES = ("off", "one", "all")
HISTORY_SIZE = 15
MAX_QUEUE = 500
MAX_FAILURES = 3
RESCAN_INTERVAL = 300
PAIRING_TIMEOUT = 120  # seconds to type the PIN the Apple TV shows
SLEEP_FADE_FROM = 0.8  # the sleep timer fades out over its last 20 %
FADE_STEP_SECONDS = 2.0
OUTPUT_DELAY = 2.0  # seconds the speaker buffers before what we send is audible


class Speaker:
    def __init__(self, manager: "SpeakerManager", ident: str, saved: dict[str, Any]) -> None:
        self.manager = manager
        self.id = ident
        self.kind: str = "pair" if saved.get("kind") == "pair" else "single"
        self.name: str = saved.get("name") or ident
        # Stereo pairs: the two HomePods, which one stands on the left, and the leader
        # the Home app elected (informational only).
        self.target_id: str = saved.get("target_id") or ident
        self.members: list[str] = list(saved.get("members") or [])
        self.left_id: str = saved.get("left_id") or ""
        self.split: bool = bool(saved.get("split", False))
        # Multiroom: speakers with the same group number (1, 2, ...) play the same
        # thing in sync; 0 = on its own.
        group = saved.get("group", 0)
        self.group: int = group if isinstance(group, int) and group >= 0 else 0
        self.address: str = saved.get("address") or ""
        self.model: str = saved.get("model") or ""
        self.online = False
        self.supported = True
        # Apple TVs with access control: shown, but must be paired once (PIN on the TV).
        self.needs_pairing = False
        self.config: BaseConfig | None = None
        self.volume: float = _clamp(saved.get("volume", 35))
        self.muted: bool = bool(saved.get("muted", False))
        # Stereo pairs: -1 = only the left HomePod, 0 = centre, 1 = only the right one.
        self.balance: float = _clamp_balance(saved.get("balance", 0))
        self.repeat: str = saved.get("repeat") if saved.get("repeat") in REPEAT_MODES else "one"
        self.history: list[Track] = []
        for item in saved.get("history", []):
            try:
                self.history.append(Track.from_dict(item))
            except ValueError:
                pass
        # Where playback stopped, for "continue".
        self.resume: Track | None = None
        self.resume_position = 0.0
        saved_resume = saved.get("resume")
        if isinstance(saved_resume, dict):
            try:
                self.resume = Track.from_dict(saved_resume.get("track"))
                self.resume_position = max(0.0, float(saved_resume.get("position") or 0))
            except (ValueError, TypeError):
                self.resume = None
        # The playlist of this speaker (also what is playing in simple mode).
        self.queue: list[Track] = []
        for item in saved.get("queue", [])[:MAX_QUEUE]:
            try:
                self.queue.append(Track.from_dict(item))
            except ValueError:
                pass
        self.index = 0
        if isinstance(saved.get("index"), int) and 0 <= saved["index"] < len(self.queue):
            self.index = saved["index"]
        self.status = "idle"  # idle | loading | playing | error
        self.error = ""
        self.started_at: float | None = None
        self.sleep_at: float | None = None
        self.sleep_started: float | None = None
        self.fade = 1.0  # sleep timer fade factor, 1.0 = full volume
        self.download: dict[str, float | None] | None = None  # while a song downloads
        self._atvs: list[AppleTV] = []
        # While this speaker streams: each connected device and the speaker it
        # belongs to (itself, or another member of its group), for the volume.
        self._outputs: list[tuple[AppleTV, "Speaker"]] = []
        self._pcm: PcmSource | None = None
        self._task: asyncio.Task | None = None
        self._sleep_task: asyncio.Task | None = None
        self._stop_requested = False
        self._start_offset = 0.0

    # ----- public actions -------------------------------------------------

    async def play(self, tracks: list[Track], index: int = 0, start: float = 0) -> None:
        if not tracks:
            return
        await self.stop(keep_sleep=True)
        await self.manager.stop_conflicts(self)
        self.queue = tracks[:MAX_QUEUE]
        self.index = max(0, min(index, len(self.queue) - 1))
        self._start_offset = max(0.0, start)
        self._stop_requested = False
        self.error = ""
        _LOGGER.info("%s: play %d track(s) from #%d at %.0fs (repeat=%s)", self.name,
                     len(self.queue), self.index, self._start_offset, self.repeat)
        self._task = asyncio.create_task(self._run(), name=f"play-{self.name}")

    async def play_test_tone(self) -> None:
        """Low tone on the left channel, then high tone on the right (twice)."""
        await self.stop()
        await self.manager.stop_conflicts(self)
        self.queue = []
        self._stop_requested = False
        self.error = ""
        _LOGGER.info("%s: stereo test tone", self.name)
        self._task = asyncio.create_task(self._run_test_tone(), name=f"test-{self.name}")

    async def set_left(self, member_id: str) -> None:
        if self.kind != "pair" or member_id not in self.members:
            raise ValueError("Not a member of this pair")
        if member_id == self.left_id:
            return
        self.left_id = member_id
        _LOGGER.info("%s: left speaker is %s", self.name, self.manager.device_name(member_id))
        self.manager.save()
        # Apply right away by restarting the current song.
        if self.queue and self.status in ("playing", "loading"):
            await self.play(self.queue, self.index)

    async def set_split(self, split: bool) -> None:
        if self.kind != "pair":
            raise ValueError("Not a stereo pair")
        if split:
            await self.stop()
        else:
            for member in self.manager.members_of(self):
                await member.stop()
        self.split = split
        _LOGGER.info("%s: %s", self.name, "control separately" if split else "use as stereo pair")
        self.manager.save()

    async def continue_playing(self) -> None:
        """Pick up where playback stopped; live streams simply start again."""
        if self.status in ("playing", "loading"):
            return
        track, position = self.resume, self.resume_position
        if track is None:
            if not self.history:
                return
            track, position = self.history[0], 0.0
        if track.live or (track.duration and position > track.duration - 5):
            position = 0.0
        await self.play([track], start=position)

    async def seek(self, position: float) -> None:
        """Jump within the current song (restarts the stream at that point)."""
        current = self._current_track()
        if current is None or current.live or not current.duration:
            raise ValueError("This track can not be seeked")
        position = max(0.0, min(float(position), current.duration - 1))
        _LOGGER.info("%s: seek to %.0fs", self.name, position)
        await self.play(self.queue, self.index, start=position)

    async def replay(self) -> None:
        """Play the current song again from the start, or the last one played."""
        if self.queue and self.status in ("playing", "loading"):
            await self.play(self.queue, self.index)
        elif self.history:
            await self.play([self.history[0]])

    # ----- playlist ---------------------------------------------------------

    def _busy(self) -> bool:
        return self.status in ("playing", "loading")

    async def enqueue(self, tracks: list[Track]) -> None:
        """Add songs to the end of the playlist; starts playing if nothing plays."""
        room = MAX_QUEUE - len(self.queue)
        if room <= 0:
            raise ValueError("Playlist is full")
        first_new = len(self.queue)
        self.queue.extend(tracks[:room])
        _LOGGER.info("%s: added %d song(s) to the playlist (%d total)", self.name,
                     min(len(tracks), room), len(self.queue))
        self.manager.save()
        if not self._busy():
            await self.play(self.queue, first_new)

    async def queue_move(self, source: int, target: int) -> None:
        if not (0 <= source < len(self.queue) and 0 <= target < len(self.queue)):
            raise ValueError("Invalid position")
        track = self.queue.pop(source)
        self.queue.insert(target, track)
        # Keep pointing at the song that is playing.
        if self.index == source:
            self.index = target
        elif source < self.index <= target:
            self.index -= 1
        elif target <= self.index < source:
            self.index += 1
        self.manager.save()

    async def queue_remove(self, position: int) -> None:
        if not 0 <= position < len(self.queue):
            raise ValueError("Invalid position")
        removing_current = position == self.index and self._busy()
        self.queue.pop(position)
        if position < self.index:
            self.index -= 1
        if removing_current:
            if self.queue:
                await self.play(self.queue, min(position, len(self.queue) - 1))
            else:
                await self.stop()
        self.index = min(self.index, max(0, len(self.queue) - 1))
        self.manager.save()

    async def queue_play(self, position: int) -> None:
        if not 0 <= position < len(self.queue):
            raise ValueError("Invalid position")
        await self.play(self.queue, position)

    async def queue_clear(self) -> None:
        await self.stop()
        self.queue = []
        self.index = 0
        self.manager.save()

    async def skip(self, step: int) -> None:
        if not self.queue:
            return
        index = (self.index + step) % len(self.queue)
        await self.play(self.queue, index)

    async def stop(self, keep_sleep: bool = False) -> None:
        if self._task is not None:
            self._save_resume()
            _LOGGER.info("%s: stop", self.name)
        self._stop_requested = True
        if not keep_sleep:
            self._cancel_sleep()
        task, self._task = self._task, None
        if self._pcm is not None:
            self._pcm.finish()
        for atv in list(self._atvs):
            try:
                await atv.remote_control.stop()
            except Exception:  # noqa: BLE001 - stopping must never fail
                _LOGGER.debug("Graceful stop failed on %s", self.name, exc_info=True)
        if task and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                _LOGGER.warning("%s: player did not stop in time, cancelling", self.name)
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                pass
        self.status = "idle"
        self.started_at = None

    async def pause(self) -> None:
        """Stop and remember the position, so "continue" picks up right there."""
        await self.stop()

    async def stop_and_forget(self) -> None:
        """Stop for good: "continue" starts the last song from the beginning."""
        await self.stop()
        if self.resume is not None:
            self.resume_position = 0.0
            self.manager.save()

    async def set_volume(self, volume: float) -> None:
        self.volume = _clamp(volume)
        self.muted = False  # moving the slider unmutes
        _LOGGER.debug("%s: volume %.0f", self.name, self.volume)
        await self.manager.apply_volume(self)
        self.manager.save()

    async def set_balance(self, balance: float) -> None:
        if self.kind != "pair":
            raise ValueError("Balance needs a stereo pair")
        self.balance = _clamp_balance(balance)
        _LOGGER.debug("%s: balance %.2f", self.name, self.balance)
        self.manager.save()  # the audio splitter picks it up with the next chunk

    async def set_muted(self, muted: bool) -> None:
        self.muted = muted
        _LOGGER.info("%s: %s", self.name, "muted" if muted else "unmuted")
        await self.manager.apply_volume(self)
        self.manager.save()

    def set_repeat(self, mode: str) -> None:
        if mode not in REPEAT_MODES:
            raise ValueError("Unknown repeat mode")
        self.repeat = mode
        _LOGGER.debug("%s: repeat %s", self.name, mode)
        self.manager.save()

    def set_sleep(self, minutes: float) -> None:
        self._cancel_sleep()
        _LOGGER.info("%s: sleep timer %s", self.name, f"{minutes:g} min" if minutes else "off")
        if minutes > 0:
            self.sleep_started = time.time()
            self.sleep_at = self.sleep_started + minutes * 60
            self._sleep_task = asyncio.create_task(self._sleep_timer())

    # ----- state for the web UI ------------------------------------------

    def effective_volume(self) -> float:
        return 0.0 if self.muted else self.volume * self.fade

    def _current_track(self) -> Track | None:
        if self.queue and self.status in ("playing", "loading"):
            return self.queue[self.index]
        return None

    def to_dict(self) -> dict[str, Any]:
        data = self._own_dict()
        leader = self.manager.group_leader(self)
        if leader is not None and leader is not self:
            # A member of a playing group shows (and controls) what the group plays;
            # its volume, mute and history stay its own.
            playing = leader._own_dict()
            for key in ("status", "error", "track", "position", "queue_length", "queue", "index",
                        "elapsed", "progress", "seekable", "download", "repeat", "fading",
                        "sleep_remaining"):
                data[key] = playing[key]
        data["group"] = self.group
        data["group_leader"] = leader.id if leader is not None else None
        return data

    def _own_dict(self) -> dict[str, Any]:
        current = self.queue[self.index] if self.queue and self.status != "idle" else None
        pair = None
        if self.kind == "pair":
            names = {m: self.manager.device_name(m) for m in self.members}
            left, right = self._sides()
            pair = {
                "members": [{"id": m, "name": names[m]} for m in self.members],
                "left": {"id": left, "name": names.get(left, "")},
                "right": {"id": right, "name": names.get(right, "")},
                "leader": names.get(self.target_id, ""),
                "split": self.split,
                "balance": self.balance,
            }
        pair_of = next((p.id for p in self.manager.speakers.values()
                        if p.kind == "pair" and self.id in p.members), None)
        return {
            "id": self.id,
            "kind": self.kind,
            "pair": pair,
            "pair_of": pair_of,
            "name": self.name,
            "model": self.model,
            "online": self.online,
            "supported": self.supported,
            "needs_pairing": self.needs_pairing,
            "status": self.status,
            "error": self.error,
            "track": current.to_dict() if current else None,
            "position": self.index,
            "queue_length": len(self.queue) if self.status != "idle" else 0,
            "queue": [t.to_dict() for t in self.queue],
            "index": self.index,
            "elapsed": time.time() - self.started_at if self.started_at else None,
            # Audible position in the current song, and whether the slider may move it.
            "progress": self._position() if self.started_at else None,
            "seekable": bool(current and not current.live and current.duration),
            "download": self.download,
            "repeat": self.repeat,
            "volume": self.volume,
            "muted": self.muted,
            "fading": self.fade < 1.0,
            "sleep_remaining": max(0.0, self.sleep_at - time.time()) if self.sleep_at else None,
            "history": [t.to_dict() for t in self.history],
            "resume": {"title": self.resume.title, "live": self.resume.live,
                       "position": self.resume_position} if self.resume else None,
        }

    def to_saved(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "target_id": self.target_id,
            "members": self.members,
            "left_id": self.left_id,
            "split": self.split,
            "group": self.group,
            "address": self.address,
            "model": self.model,
            "volume": self.volume,
            "muted": self.muted,
            "balance": self.balance,
            "repeat": self.repeat,
            "history": [t.to_dict() for t in self.history],
            "queue": [t.to_dict() for t in self.queue],
            "index": self.index,
            "resume": {"track": self.resume.to_dict(), "position": self.resume_position}
            if self.resume else None,
        }

    # ----- internals -------------------------------------------------------

    def _sides(self) -> tuple[str, str]:
        """Member ids standing on the left and on the right."""
        left = self.left_id if self.left_id in self.members else (self.members or [""])[0]
        right = next((m for m in self.members if m != left), "")
        return left, right

    def device_gain(self, device_id: str) -> float:
        """Audio gain (0..1) for one HomePod of a stereo pair, from the balance."""
        if self.kind != "pair":
            return 1.0
        left, _ = self._sides()
        if device_id == left:
            return min(1.0, 1.0 - self.balance)
        return min(1.0, 1.0 + self.balance)

    def output_volume(self, owner: "Speaker") -> float:
        """Volume for a device of owner while this speaker streams: owner's own
        volume and mute, faded by this speaker's sleep timer."""
        return 0.0 if owner.muted else owner.volume * self.fade

    async def _apply_volume(self) -> None:
        for atv, owner in list(self._outputs):
            try:
                await atv.audio.set_volume(self.output_volume(owner))
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Volume change failed on %s", owner.name, exc_info=True)

    def _position(self) -> float:
        """Position in the current track that is audible right now."""
        if self.started_at is None:
            return 0.0
        return max(0.0, time.time() - self.started_at - OUTPUT_DELAY)

    def _save_resume(self) -> None:
        if self.status != "playing" or not self.queue or self.started_at is None:
            return
        track = self.queue[self.index]
        self.resume = track
        self.resume_position = 0.0 if track.live else self._position()
        _LOGGER.debug("%s: resume point %r at %.0fs", self.name, track.title,
                      self.resume_position)
        self.manager.save()

    def _remember(self, track: Track) -> None:
        self.history = [t for t in self.history if (t.source, t.ref) != (track.source, track.ref)]
        self.history.insert(0, track)
        del self.history[HISTORY_SIZE:]
        self.manager.save()

    def _cancel_sleep(self) -> None:
        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()
        self._sleep_task = None
        self.sleep_at = None
        self.sleep_started = None
        if self.fade < 1.0:
            self.fade = 1.0
            if self._atvs:
                asyncio.create_task(self._apply_volume())

    async def _sleep_timer(self) -> None:
        assert self.sleep_at is not None and self.sleep_started is not None
        start, end = self.sleep_started, self.sleep_at
        fade_from = start + (end - start) * SLEEP_FADE_FROM
        await asyncio.sleep(max(0.0, fade_from - time.time()))
        _LOGGER.info("%s: sleep timer fading out over %.0fs", self.name, end - fade_from)
        # Get quieter linearly until the volume reaches zero at the end.
        while (now := time.time()) < end:
            self.fade = max(0.0, (end - now) / (end - fade_from))
            await self._apply_volume()
            await asyncio.sleep(min(FADE_STEP_SECONDS, end - now))
        self.fade = 0.0
        await self._apply_volume()
        self._sleep_task = None
        self.sleep_at = None
        self.sleep_started = None
        _LOGGER.info("%s: sleep timer ended", self.name)
        await self.stop(keep_sleep=True)
        self.fade = 1.0  # next playback starts at the normal volume again

    def device_outputs(self) -> list[tuple[str, int | None]]:
        """The devices of this speaker: (device id, channel or None for stereo)."""
        if self.kind == "pair":
            left, right = self._sides()
            return [(left, 0), (right, 1)]
        return [(self.id, None)]

    async def _stream(self, prepared: PreparedAudio, metadata: MediaMetadata,
                      on_start: Callable[[], None] | None = None, offset: float = 0,
                      solo: bool = False) -> None:
        """Connect and stream one prepared source until it ends, on this speaker and
        (unless solo) on the other speakers of its group."""
        started = time.monotonic()
        members = [self] if solo else [self] + [m for m in self.manager.group_members(self)
                                                if m is not self]
        wanted = [(owner, ident, channel) for owner in members
                  for ident, channel in owner.device_outputs()]
        results = await asyncio.gather(*(self.manager.connect_device(ident)
                                         for _, ident, _ in wanted), return_exceptions=True)
        plan: list[tuple[Speaker, str, int | None]] = []
        for (owner, ident, channel), result in zip(wanted, results):
            if isinstance(result, BaseException):
                if owner is self:
                    # This speaker itself must work; group members are optional.
                    for other in results:
                        if not isinstance(other, BaseException):
                            self._atvs.append(other)
                    raise result
                _LOGGER.warning("%s: group member %s not reachable: %s", self.name,
                                self.manager.device_name(ident), result)
                continue
            self._atvs.append(result)
            self._outputs.append((result, owner))
            plan.append((owner, ident, channel))
        _LOGGER.debug("%s: connected to %d device(s) in %.2fs", self.name, len(plan),
                      time.monotonic() - started)
        if self._stop_requested:
            return
        pcm = PcmSource(prepared.stdout, metadata)
        self._pcm = pcm
        try:
            await pcm.wait_ready(timeout=30)
            self.status = "playing"
            self.started_at = time.time() - offset  # so elapsed is the position in the track
            self.error = ""
            if on_start:
                on_start()
            outputs = [Output(atv, self.manager.device_name(ident), channel,
                              self.output_volume(owner))
                       for (atv, _), (owner, ident, channel) in zip(self._outputs, plan)]
            await stream_multi(outputs, pcm,
                               gains=lambda: [owner.device_gain(ident) for owner, ident, _ in plan],
                               stop_all_on_end=len(members) == 1)
        finally:
            self._pcm = None
            await pcm.close()

    def _close_devices(self) -> None:
        self._outputs = []
        atvs, self._atvs = self._atvs, []
        for atv in atvs:
            atv.close()

    async def _run_test_tone(self) -> None:
        prepared = None
        self.status = "loading"
        try:
            prepared = await self.manager.sources.test_tone()
            await self._stream(prepared, MediaMetadata(title="AirMan L/R test", duration=8),
                               solo=True)
            self.status = "idle"
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            if self._stop_requested:
                _LOGGER.debug("%s: test tone ended by stop: %s", self.name, ex)
            else:
                self.error = _short_error(ex)
                self.status = "error"
                _LOGGER.warning("%s: test tone failed: %s", self.name, ex, exc_info=True)
        finally:
            self.started_at = None
            self._close_devices()
            if prepared is not None:
                await prepared.close()

    async def _run(self) -> None:
        failures = 0
        while not self._stop_requested and self.queue:
            if self.index >= len(self.queue):
                if self.repeat != "all":
                    # Played to the end: "continue" starts the last song from the beginning.
                    self.resume = None
                    self.manager.save()
                    break
                self.index = 0
            track = self.queue[self.index]
            self.status = "loading"
            prepared: PreparedAudio | None = None
            interrupted = False
            offset, self._start_offset = (0.0 if track.live else self._start_offset), 0.0
            try:
                def on_progress(fraction: float | None, eta: float | None) -> None:
                    self.download = {"fraction": fraction, "eta": eta}

                try:
                    prepared = await self.manager.sources.prepare(track, start=offset,
                                                                  progress=on_progress)
                finally:
                    self.download = None
                metadata = MediaMetadata(title=track.title, artist=track.subtitle or None,
                                         duration=track.duration)

                def started(track: Track = track) -> None:
                    self._remember(track)
                    _LOGGER.info("%s: playing %r (%s)", self.name, track.title, track.source)

                await self._stream(prepared, metadata, on_start=started, offset=offset)
                if self._stop_requested:
                    break
                if self.started_at is not None:
                    _LOGGER.info("%s: finished after %.1fs", self.name,
                                 time.time() - self.started_at)
                interrupted = self._was_interrupted(track, prepared)
                if interrupted:
                    self._save_resume()
                failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as ex:  # noqa: BLE001 - keep the player alive
                if self._stop_requested:
                    # Errors while stopping (e.g. "not connected") are expected.
                    _LOGGER.debug("%s: ended by stop: %s", self.name, ex)
                    break
                failures += 1
                if isinstance(ex, SourceError):
                    self.error = str(ex)
                    _LOGGER.info("%s: %s", self.name, ex)
                else:
                    self.error = _short_error(ex)
                    _LOGGER.warning("%s: playback failed: %s", self.name, ex, exc_info=True)
            finally:
                self.started_at = None
                self._close_devices()
                if prepared is not None:
                    await prepared.close()

            if self._stop_requested:
                break
            if interrupted:
                # Someone else (e.g. an iPhone) took over the speaker: do not fight back.
                _LOGGER.info("%s: interrupted by another device", self.name)
                self.error = "interrupted"
                break
            if failures:
                if failures >= MAX_FAILURES:
                    _LOGGER.warning("%s: giving up after %d failures", self.name, failures)
                    self.status = "error"
                    return
                _LOGGER.info("%s: retry %d/%d", self.name, failures, MAX_FAILURES)
                self.status = "loading"
                await asyncio.sleep(3 * failures)
                continue  # retry the same track
            if track.live or self.repeat == "one":
                continue
            self.index += 1
        self.status = "idle"

    def _was_interrupted(self, track: Track, prepared: PreparedAudio) -> bool:
        if self._stop_requested:
            return False
        # The decoder still running means the speaker ended the stream, not the song.
        if prepared.running:
            return True
        if track.duration and self.started_at is not None:
            return time.time() - self.started_at < track.duration * 0.9 - 2
        return False


class SpeakerManager:
    def __init__(self, sources: Sources, data_dir: Path) -> None:
        self.sources = sources
        self._state_file = data_dir / "state.json"
        state = read_json(self._state_file, {})
        self.last_speaker: str | None = state.get("last_speaker")
        self.speakers: dict[str, Speaker] = {
            ident: Speaker(self, ident, saved)
            for ident, saved in (state.get("speakers") or {}).items()
            # Ids with colons came from a short-lived version that used AirPlay ids.
            if isinstance(saved, dict) and ":" not in ident
        }
        self._scan_lock = asyncio.Lock()
        self._rescan_task: asyncio.Task | None = None
        # Credentials from pairing with Apple TVs. Secret: they let anyone holding them
        # stream to that Apple TV, so the file is readable only by this user account.
        self._pairings_file = data_dir / "pairings.json"
        pairings = read_json(self._pairings_file, {})
        self._pairings: dict[str, str] = {
            k: v for k, v in pairings.items() if isinstance(k, str) and isinstance(v, str)
        } if isinstance(pairings, dict) else {}
        self._pairing: tuple[str, Any, float] | None = None  # (speaker id, handler, started)

    async def start(self) -> None:
        await self.scan()
        self._rescan_task = asyncio.create_task(self._rescan_loop())

    async def shutdown(self) -> None:
        if self._rescan_task:
            self._rescan_task.cancel()
        await asyncio.gather(*(s.stop() for s in self.speakers.values()), return_exceptions=True)
        self.save()

    async def _rescan_loop(self) -> None:
        while True:
            await asyncio.sleep(RESCAN_INTERVAL)
            try:
                await self.scan()
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Speaker scan failed", exc_info=True)

    async def scan(self) -> None:
        async with self._scan_lock:
            started = time.monotonic()
            loop = asyncio.get_running_loop()
            configs = await pyatv.scan(loop, timeout=5, protocol={Protocol.RAOP, Protocol.AirPlay})
            seen = set()
            groups: dict[str, list[tuple[BaseConfig, dict]]] = {}
            for conf in configs:
                service = conf.get_service(Protocol.RAOP)
                ident = _raop_id(conf)
                if service is None or not ident:
                    continue
                speaker = self.speakers.get(ident)
                if speaker is None:
                    speaker = Speaker(self, ident, {})
                    self.speakers[ident] = speaker
                    _LOGGER.info("New speaker: %s (%s, %s)", conf.name,
                                 conf.device_info.model_str, conf.address)
                speaker.config = conf
                speaker.name = conf.name
                speaker.address = str(conf.address)
                speaker.model = conf.device_info.model_str
                if ident in self._pairings:
                    conf.set_credentials(Protocol.RAOP, self._pairings[ident])
                needs_pairing = (service.pairing == PairingRequirement.Mandatory
                                 and ident not in self._pairings)
                speaker.supported = service.pairing in (
                    PairingRequirement.NotNeeded, PairingRequirement.Optional,
                    PairingRequirement.Mandatory)
                speaker.needs_pairing = needs_pairing
                speaker.online = True
                seen.add(ident)
                airplay = conf.get_service(Protocol.AirPlay)
                props = dict(airplay.properties) if airplay else {}
                _LOGGER.debug("Scan: %s %s pairing=%s gid=%s igl=%s gpn=%s", conf.name,
                              conf.address, service.pairing.name, props.get("gid"),
                              props.get("igl"), props.get("gpn"))
                # The group id changes with AirPlay sessions; tsid is the stable pair id.
                group = props.get("tsid") or (props.get("gid") or "").split("+")[0]
                if speaker.supported and not needs_pairing and group and props.get("gpn"):
                    groups.setdefault(group, []).append((conf, props))

            for group, members in groups.items():
                self._update_pair(group, members, seen)

            for ident, speaker in self.speakers.items():
                if ident not in seen and speaker.status == "idle":
                    speaker.online = False
            self.save()
            _LOGGER.info("Found %d AirPlay speaker(s) in %.1fs", len(seen),
                         time.monotonic() - started)

    def _update_pair(self, group: str, members: list[tuple[BaseConfig, dict]], seen: set) -> None:
        """Turn two HomePods sharing a group id into one stereo-pair speaker."""
        if len(members) != 2:
            return
        if not all((props.get("model") or "").startswith("AudioAccessory") for _, props in members):
            return  # e.g. Apple TV home theater groups: not a stereo pair
        # Informational: the leader the Home app elected (both may claim it briefly).
        leader = next((conf for conf, props in members if props.get("igl") == "1"),
                      members[0][0])
        props = members[0][1]
        ident = "pair-" + group
        pair = self.speakers.get(ident)
        if pair is None:
            pair = Speaker(self, ident, {"kind": "pair"})
            self.speakers[ident] = pair
            _LOGGER.info("New stereo pair: %s (%s)", props["gpn"],
                         " + ".join(conf.name for conf, _ in members))
        pair.kind = "pair"
        pair.name = props["gpn"]
        pair.target_id = _raop_id(leader)
        pair.members = sorted((_raop_id(conf) for conf, _ in members), key=self.device_name)
        if pair.left_id not in pair.members:
            pair.left_id = pair.members[0]
        pair.address = str(leader.address)
        pair.model = "Stereo pair"
        pair.supported = True
        pair.online = True
        seen.add(ident)

    async def connect_device(self, ident: str) -> AppleTV:
        """Connect to one physical speaker by its id."""
        speaker = self.speakers.get(ident)
        name = speaker.name if speaker else ident
        address = speaker.address if speaker else ""
        loop = asyncio.get_running_loop()
        conf = None
        # A direct lookup is fast; fall back to a full scan if the address changed.
        if address:
            found = await pyatv.scan(loop, timeout=3, hosts=[address], protocol=Protocol.RAOP)
            conf = next((c for c in found if c.identifier == ident), None)
        if conf is None:
            _LOGGER.info("%s: not found at %s, searching the network", name, address)
            found = await pyatv.scan(loop, timeout=5, identifier=ident, protocol=Protocol.RAOP)
            conf = found[0] if found else None
        if conf is None:
            if speaker:
                speaker.online = False
            raise SourceError(f"{name} not reachable")
        if speaker:
            speaker.online = True
            speaker.address = str(conf.address)
        if ident in self._pairings:
            conf.set_credentials(Protocol.RAOP, self._pairings[ident])
        elif speaker and speaker.needs_pairing:
            raise SourceError(f"{name} must be paired first")
        return await pyatv.connect(conf, loop)

    # ----- pairing with Apple TVs ---------------------------------------------

    async def pair_start(self, ident: str) -> None:
        """Start pairing: the Apple TV shows a PIN on the screen."""
        speaker = self.get(ident)
        if speaker.kind != "single" or speaker.config is None:
            raise ValueError("this speaker can not be paired")
        await self.pair_cancel()
        loop = asyncio.get_running_loop()
        handler = await pyatv.pair(speaker.config, Protocol.RAOP, loop, name="AirMan")
        try:
            await handler.begin()
        except Exception:
            await handler.close()
            raise
        self._pairing = (ident, handler, time.monotonic())
        _LOGGER.info("%s: pairing started, PIN shown on the screen", speaker.name)

    async def pair_finish(self, ident: str, pin: str) -> None:
        """Finish pairing with the PIN the Apple TV shows."""
        if not (pin.isascii() and pin.isdigit() and len(pin) == 4):
            raise ValueError("PIN must be 4 digits")
        if (self._pairing is None or self._pairing[0] != ident
                or time.monotonic() - self._pairing[2] > PAIRING_TIMEOUT):
            await self.pair_cancel()
            raise ValueError("pairing expired, start again")
        _, handler, _ = self._pairing
        speaker = self.get(ident)
        try:
            handler.pin(int(pin))
            await handler.finish()
            if not handler.has_paired or not handler.service.credentials:
                raise ValueError("pairing failed")
            self._pairings[ident] = str(handler.service.credentials)
            write_json_atomic(self._pairings_file, self._pairings, private=True)
        except pyatv.exceptions.PairingError as ex:
            _LOGGER.info("%s: pairing failed: %s", speaker.name, ex)
            raise ValueError("wrong PIN or pairing failed") from ex
        finally:
            await self.pair_cancel()
        speaker.needs_pairing = False
        if speaker.config is not None:
            speaker.config.set_credentials(Protocol.RAOP, self._pairings[ident])
        _LOGGER.info("%s: paired", speaker.name)
        self.save()

    async def pair_cancel(self) -> None:
        if self._pairing is not None:
            handler = self._pairing[1]
            self._pairing = None
            try:
                await handler.close()
            except Exception:  # noqa: BLE001 - closing a half-open pairing is best effort
                _LOGGER.debug("Closing the pairing failed", exc_info=True)

    # ----- multiroom groups -----------------------------------------------------

    def group_members(self, speaker: Speaker) -> list[Speaker]:
        """All usable speakers with the same group number (including speaker)."""
        if not speaker.group:
            return [speaker]
        return [s for s in self._visible()
                if s.group == speaker.group and s.online and not s.needs_pairing]

    def group_leader(self, speaker: Speaker) -> Speaker | None:
        """The speaker that is playing for speaker's group right now, if any."""
        if speaker._busy():
            return speaker
        if not speaker.group:
            return None
        return next((s for s in self._visible() if s.group == speaker.group and s._busy()), None)

    def playback_target(self, speaker: Speaker) -> Speaker:
        """Who receives play/pause/skip/...: the group's playing speaker, else speaker."""
        return self.group_leader(speaker) or speaker

    async def apply_volume(self, speaker: Speaker) -> None:
        """A volume or mute change: tell whoever streams to speaker's devices."""
        leader = self.group_leader(speaker)
        if leader is not None:
            await leader._apply_volume()

    def group_count(self) -> int:
        """How many group numbers there are: one per speaker."""
        return max(1, len(self._visible()))

    async def set_group(self, speaker: Speaker, group: int) -> None:
        if not 0 <= group <= self.group_count():
            raise ValueError("Invalid group")
        if group == speaker.group:
            return
        old_leader = self.group_leader(speaker)
        speaker.group = group
        _LOGGER.info("%s: %s", speaker.name, f"group {group}" if group else "no group")
        self.save()
        new_leader = next((s for s in self._visible()
                           if group and s.group == group and s is not speaker and s._busy()),
                          None)
        restart: list[Speaker] = []
        if old_leader is not None and old_leader is not speaker:
            restart.append(old_leader)  # drops this speaker from its devices
        if new_leader is not None:
            if speaker._busy():
                await speaker.stop()
            restart.append(new_leader)  # adds this speaker
        elif speaker._busy():
            restart.append(speaker)  # its group now includes the others
        for leader in restart:
            if leader._busy() and leader.queue:
                await leader.play(leader.queue, leader.index, start=leader._position())

    def members_of(self, pair: Speaker) -> list[Speaker]:
        return [self.speakers[m] for m in pair.members if m in self.speakers]

    async def stop_conflicts(self, speaker: Speaker) -> None:
        """Devices can only play one thing: a pair and its own HomePods, and the
        speakers of a group (the group plays what speaker starts)."""
        others: list[Speaker] = []
        for member in self.group_members(speaker):
            if member is not speaker:
                others.append(member)
            if member.kind == "pair":
                others += self.members_of(member)
            else:
                others += [p for p in self.speakers.values()
                           if p.kind == "pair" and member.id in p.members]
        for other in dict.fromkeys(o for o in others if o is not speaker):
            if other.status != "idle":
                _LOGGER.info("%s: stopping %s first", speaker.name, other.name)
                await other.stop()

    def device_name(self, ident: str) -> str:
        speaker = self.speakers.get(ident)
        return speaker.name if speaker else ident

    def get(self, ident: str) -> Speaker:
        speaker = self.speakers.get(ident)
        if speaker is None:
            raise KeyError(ident)
        return speaker

    def mark_used(self, speaker: Speaker) -> None:
        if self.last_speaker != speaker.id:
            self.last_speaker = speaker.id
            self.save()

    def save(self) -> None:
        write_json_atomic(self._state_file, {
            "last_speaker": self.last_speaker,
            "speakers": {ident: s.to_saved() for ident, s in self.speakers.items()},
        })

    def _visible(self) -> list[Speaker]:
        hidden: set[str] = set()
        for s in self.speakers.values():
            if s.kind == "pair":
                hidden |= {s.id} if s.split else set(s.members)
        return [s for s in self.speakers.values() if s.supported and s.id not in hidden]

    def to_list(self) -> list[dict[str, Any]]:
        # Stereo pairs first: they are the default choice for their room.
        items = sorted(self._visible(), key=lambda s: (s.kind != "pair", s.name.lower()))
        return [s.to_dict() for s in items]

    def preferred_speaker(self) -> str | None:
        """Last used speaker, mapped onto its stereo pair when the pair is active."""
        for s in self.speakers.values():
            if s.kind == "pair" and not s.split and self.last_speaker in s.members:
                return s.id
        return self.last_speaker


def _raop_id(conf: BaseConfig) -> str:
    """Stable id of a device: the one its AirPlay audio (RAOP) service reports."""
    service = conf.get_service(Protocol.RAOP)
    return (service.identifier if service and service.identifier else conf.identifier) or ""


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 35.0


def _clamp_balance(value: Any) -> float:
    try:
        return max(-1.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _short_error(ex: Exception) -> str:
    text = str(ex) or ex.__class__.__name__
    return text[:200]
