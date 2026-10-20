"""Stream raw PCM from ffmpeg to an AirPlay speaker.

pyatv's own stream_file() decodes pipes with miniaudio, which proved unreliable
(MP3/WAV pipes fail, FLAC pipes stop early). ffmpeg already decodes everything,
so we hand pyatv finished PCM samples instead. This mirrors RaopStream.stream_file
in pyatv 0.18 but skips the decoder.

Several speakers at once (stereo pairs, multiroom groups): every device gets its
own stream, a stereo pair's HomePods one channel each. pyatv schedules every
packet relative to the session's start timestamp (start_ts), so giving all
sessions the same start_ts makes the speakers play in sync even if their
connections were set up a few milliseconds apart.
"""

from __future__ import annotations

import array
import asyncio
import logging
import sys
from typing import Any, Callable

from pyatv.const import Protocol
from pyatv.interface import Audio, AppleTV, MediaMetadata, Metadata, PushUpdater, RemoteControl
from pyatv.protocols.airplay.auth import extract_credentials
from pyatv.protocols.raop import timing
from pyatv.protocols.raop.audio_source import AudioSource

_LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_SIZE = 2  # bytes, 16 bit
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_SIZE
PREBUFFER = BYTES_PER_SECOND  # 1 s, absorbs network hiccups of radio streams
MAX_BUFFER = BYTES_PER_SECOND * 4
READ_SIZE = 16 * 1024


class PcmSource(AudioSource):
    """Audio source reading big-endian 16 bit PCM (what AirPlay expects)."""

    def __init__(self, reader: asyncio.StreamReader, metadata: MediaMetadata) -> None:
        self._reader = reader
        self._metadata = metadata
        self._buffer = bytearray()
        self._eof = False
        self._changed = asyncio.Event()
        self._task = asyncio.create_task(self._fill())

    async def _fill(self) -> None:
        try:
            while not self._eof:
                while len(self._buffer) >= MAX_BUFFER:
                    self._changed.clear()
                    await self._changed.wait()
                chunk = await self._reader.read(READ_SIZE)
                if not chunk:
                    self._eof = True
                else:
                    self._buffer += chunk
                self._changed.set()
        except (ConnectionError, OSError):
            self._eof = True
            self._changed.set()

    async def wait_ready(self, timeout: float) -> None:
        """Wait until enough audio is buffered (or the source ended)."""
        async def ready() -> None:
            while len(self._buffer) < PREBUFFER and not self._eof:
                self._changed.clear()
                await self._changed.wait()

        await asyncio.wait_for(ready(), timeout)
        if not self._buffer:
            raise EOFError("source delivered no audio")

    async def readframes(self, nframes: int) -> bytes:
        wanted = nframes * CHANNELS * SAMPLE_SIZE
        while len(self._buffer) < wanted and not self._eof:
            self._changed.clear()
            await self._changed.wait()
        size = min(wanted, len(self._buffer))
        size -= size % (CHANNELS * SAMPLE_SIZE)
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        self._changed.set()  # lets the filler continue
        return data

    def finish(self) -> None:
        """End the stream right away; the speaker sees a normal end of song."""
        self._eof = True
        self._buffer.clear()
        self._changed.set()

    async def get_metadata(self) -> MediaMetadata:
        return self._metadata

    async def close(self) -> None:
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def channels(self) -> int:
        return CHANNELS

    @property
    def sample_size(self) -> int:
        return SAMPLE_SIZE

    @property
    def duration(self) -> int:
        return int(self._metadata.duration or 0)


def _mono_channel(data: bytes, channel: int) -> bytes:
    """Copy one channel of interleaved 16 bit stereo frames into both channels."""
    out = bytearray(len(data))
    first = channel * SAMPLE_SIZE
    for offset in (0, SAMPLE_SIZE):  # left and right slot of each output frame
        for byte in range(SAMPLE_SIZE):
            out[offset + byte::CHANNELS * SAMPLE_SIZE] = \
                data[first + byte::CHANNELS * SAMPLE_SIZE]
    return bytes(out)


def _apply_gain(data: bytes, gain: float) -> bytes:
    """Scale big-endian 16 bit samples by gain (0..1)."""
    if gain >= 0.999:
        return data
    samples = array.array("h")
    samples.frombytes(data)
    if sys.byteorder == "little":
        samples.byteswap()
    scaled = array.array("h", [int(x * gain) for x in samples])
    if sys.byteorder == "little":
        scaled.byteswap()
    return scaled.tobytes()


class ChannelSource(AudioSource):
    """What one device plays of a shared PcmSource: both channels, or only one
    (channel 0 = left, 1 = right) for a HomePod of a stereo pair."""

    def __init__(self, splitter: "ChannelSplitter", channel: int | None) -> None:
        self._splitter = splitter
        self.channel = channel
        self.buffer = bytearray()
        self.closed = False

    async def readframes(self, nframes: int) -> bytes:
        wanted = nframes * CHANNELS * SAMPLE_SIZE
        while len(self.buffer) < wanted and await self._splitter.pull(nframes):
            pass
        size = min(wanted, len(self.buffer))
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    async def get_metadata(self) -> MediaMetadata:
        return await self._splitter.upstream.get_metadata()

    async def close(self) -> None:
        self.closed = True
        self.buffer.clear()

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def channels(self) -> int:
        return CHANNELS

    @property
    def sample_size(self) -> int:
        return SAMPLE_SIZE

    @property
    def duration(self) -> int:
        return self._splitter.upstream.duration


class ChannelSplitter:
    """Feeds one PcmSource to several devices (ChannelSources).

    channels: per device None (both channels) or 0/1 (only left/right, copied to
    both outputs). gains() returns the current gain of each device; it is read for
    every chunk, so balance changes apply while playing. (HomePods in a stereo
    pair share one volume setting, so the balance can not be done with the device
    volume.)
    """

    def __init__(self, upstream: PcmSource,
                 gains: Callable[[], list[float]] | None = None,
                 channels: list[int | None] | None = None) -> None:
        self.upstream = upstream
        self._gains = gains
        self.sides = [ChannelSource(self, c) for c in (channels if channels is not None
                                                       else [0, 1])]
        self._lock = asyncio.Lock()

    async def pull(self, nframes: int) -> bool:
        """Read the next chunk from upstream into both sides. False at the end."""
        async with self._lock:
            data = await self.upstream.readframes(nframes)
            if not data:
                return False
            gains = self._gains() if self._gains else [1.0] * len(self.sides)
            for side, gain in zip(self.sides, gains):
                if not side.closed:
                    audio = data if side.channel is None else _mono_channel(data, side.channel)
                    side.buffer += _apply_gain(audio, gain)
            return True


class RaopSession:
    """One AirPlay (RAOP) audio session on a connected device."""

    def __init__(self, atv: AppleTV, name: str) -> None:
        raop = atv.stream.get(Protocol.RAOP)  # type: ignore[attr-defined]
        if raop is None:
            raise RuntimeError(f"{name}: no AirPlay audio (RAOP) service")
        self.name = name
        self._raop = raop
        self._release: Any = None
        self._client: Any = None
        self._context: Any = None

    async def setup(self) -> None:
        raop = self._raop
        raop.playback_manager.acquire()
        self._release = raop.core.takeover(Audio, Metadata, PushUpdater, RemoteControl)
        client, context = await raop.playback_manager.setup(raop.core.service)
        context.credentials = extract_credentials(raop.core.service)
        context.password = raop.core.service.password
        client.listener = raop.listener
        await client.initialize(raop.core.service.properties)
        if (context.sample_rate, context.channels, context.bytes_per_channel) != (
                SAMPLE_RATE, CHANNELS, SAMPLE_SIZE):
            raise RuntimeError(
                f"{self.name}: unsupported audio format {context.sample_rate}/"
                f"{context.channels}/{context.bytes_per_channel}")
        self._client, self._context = client, context

    async def play(self, source: AudioSource, volume: float, start_ts: int | None = None) -> None:
        context = self._context
        if start_ts is not None:
            # send_audio() calls context.reset(), which picks a fresh start time.
            # Pin it to the shared one so all speakers of a pair play in sync.
            original_reset = context.reset

            def synced_reset() -> None:
                original_reset()
                context.start_ts = start_ts
                context.head_ts = start_ts

            context.reset = synced_reset
        deferred_volume = None
        try:
            await self._raop.audio.set_volume(volume)
        except Exception:  # noqa: BLE001 - some devices only accept it once streaming
            _LOGGER.debug("%s: setting volume before streaming failed, deferring", self.name)
            deferred_volume = volume
        await self._client.send_audio(source, await source.get_metadata(), volume=deferred_volume)

    def stop(self) -> None:
        if self._client is not None:
            self._client.stop()

    async def close(self) -> None:
        if self._release is not None:
            self._release()
            self._release = None
        await self._raop.playback_manager.teardown()


async def stream_pcm(atv: AppleTV, source: PcmSource, volume: float) -> None:
    """Play a PcmSource on one connected device until it ends or is stopped."""
    session = RaopSession(atv, "speaker")
    try:
        await session.setup()
        await session.play(source, volume)
    finally:
        await session.close()


async def stream_stereo(targets: list[tuple[AppleTV, str]], source: PcmSource, volume: float,
                        gains: Callable[[], list[float]] | None = None) -> None:
    """Play the left channel on targets[0] and the right channel on targets[1], in sync."""
    await stream_multi([Output(atv, name, channel, volume)
                        for (atv, name), channel in zip(targets, (0, 1))],
                       source, gains, stop_all_on_end=True)


class Output:
    """One device of a synchronized stream."""

    def __init__(self, atv: AppleTV, name: str, channel: int | None, volume: float) -> None:
        self.atv, self.name, self.channel, self.volume = atv, name, channel, volume


async def stream_multi(outputs: list[Output], source: PcmSource,
                       gains: Callable[[], list[float]] | None = None,
                       stop_all_on_end: bool = False) -> None:
    """Play one source on several devices in sync.

    stop_all_on_end: a stereo pair stops completely when one of its HomePods ends
    (taken over, error); in a group the other speakers play on.
    """
    splitter = ChannelSplitter(source, gains, [o.channel for o in outputs])
    sessions = [RaopSession(o.atv, o.name) for o in outputs]
    try:
        await asyncio.gather(*(session.setup() for session in sessions))
        start_ts = timing.ntp2ts(timing.ntp_now(), SAMPLE_RATE)
        tasks = [asyncio.create_task(session.play(side, output.volume, start_ts))
                 for session, side, output in zip(sessions, splitter.sides, outputs)]
        failed: list[BaseException] = []
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                side = splitter.sides[tasks.index(task)]
                await side.close()  # the splitter stops feeding a device that ended
                if not task.cancelled() and task.exception():
                    failed.append(task.exception())  # type: ignore[arg-type]
                    _LOGGER.info("%s: stream ended with %s", sessions[tasks.index(task)].name,
                                 task.exception())
            if pending and stop_all_on_end:
                for session in sessions:
                    session.stop()
                await asyncio.wait(pending, timeout=5)
                break
        if failed and (stop_all_on_end or len(failed) == len(tasks)):
            raise failed[0]
    finally:
        for side in splitter.sides:
            await side.close()
        await asyncio.gather(*(session.close() for session in sessions), return_exceptions=True)
