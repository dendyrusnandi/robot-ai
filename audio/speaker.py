from __future__ import annotations

import logging
import threading
import time
import asyncio
import audioop
from collections import deque
from collections.abc import Callable
from typing import Any

import sounddevice as sd


class Speaker:
    """Non-blocking PCM player backed by a PortAudio output callback."""

    def __init__(
        self, config: dict[str, Any], level_callback: Callable[[float], None] | None = None
    ) -> None:
        self.sample_rate = int(config.get("output_sample_rate", 24000))
        self.device = config.get("output_device")
        self.max_chunks = int(config.get("output_queue_size", 128))
        self.playback_buffer_ms = max(40, int(config.get("playback_buffer_ms", 320)))
        self.output_latency = str(config.get("output_latency", "high"))
        self._chunks: deque[bytes] = deque()
        self._pending = bytearray()
        self._lock = threading.Lock()
        self._stream: sd.RawOutputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._level_callback = level_callback
        self.current_level = 0.0
        self._echo_reference_level = 0.0
        self._echo_reference_at = 0.0
        self.logger = logging.getLogger("AUDIO")
        # Audio from the provider always arrives at self.sample_rate. If the
        # device can't open at that rate, we open it at its own native rate
        # and resample every chunk to match on the way in (see enqueue()).
        self._device_rate = self.sample_rate
        self._resample_state = None
        self._primed = False
        self._dropped_chunks = 0

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stream, self._device_rate = self._open_stream()
        self._stream.start()
        if self._device_rate != self.sample_rate:
            self.logger.info(
                "speaker started, resampling %s Hz -> device native %s Hz",
                self.sample_rate, self._device_rate,
            )
        else:
            self.logger.info("speaker started %s Hz callback mode", self.sample_rate)

    def _native_output_rate(self) -> int | None:
        try:
            info = sd.query_devices(self.device, "output")
            rate = int(info.get("default_samplerate") or 0)
            return rate or None
        except Exception:
            return None

    def _open_stream(
        self, attempts: int = 4, retry_delay: float = 0.3
    ) -> tuple[sd.RawOutputStream, int]:
        rate = self.sample_rate
        tried_fallback = False
        while True:
            last_exc: sd.PortAudioError | None = None
            for attempt in range(1, attempts + 1):
                try:
                    stream = sd.RawOutputStream(
                        samplerate=rate,
                        device=self.device,
                        channels=1,
                        dtype="int16",
                        blocksize=960,
                        latency=self.output_latency,
                        callback=self._callback,
                    )
                    return stream, rate
                except sd.PortAudioError as exc:
                    last_exc = exc
                    # PortAudio can also report the output device as
                    # transiently unavailable right after the previous
                    # stream closed (ALSA/Pulse hasn't released it yet).
                    # Retry briefly instead of killing the whole AI session.
                    if attempt < attempts:
                        self.logger.warning(
                            "speaker open failed, retrying (%s/%s): %s", attempt, attempts, exc
                        )
                        time.sleep(retry_delay)
            # The configured rate isn't transiently busy, it's just not
            # supported by this device. Fall back to whatever rate the
            # device actually advertises and resample into it.
            if tried_fallback:
                raise last_exc
            fallback_rate = self._native_output_rate()
            if not fallback_rate or fallback_rate == rate:
                raise last_exc
            self.logger.warning(
                "speaker cannot open at %s Hz (%s); falling back to device default %s Hz",
                rate, last_exc, fallback_rate,
            )
            rate = fallback_rate
            tried_fallback = True

    def enqueue(self, pcm: bytes) -> None:
        if self._device_rate != self.sample_rate:
            pcm, self._resample_state = audioop.ratecv(
                pcm, 2, 1, self.sample_rate, self._device_rate, self._resample_state
            )
        with self._lock:
            while len(self._chunks) >= self.max_chunks:
                self._chunks.popleft()
                self._dropped_chunks += 1
                if self._dropped_chunks == 1 or self._dropped_chunks % 25 == 0:
                    self.logger.warning(
                        "speaker queue overflow; dropped audio chunks=%s",
                        self._dropped_chunks,
                    )
            self._chunks.append(pcm)

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._pending.clear()
            self._primed = False
        self._resample_state = None

    def buffered_seconds(self) -> float:
        with self._lock:
            buffered_bytes = len(self._pending) + sum(map(len, self._chunks))
        return buffered_bytes / (self._device_rate * 2)

    def finish_response(self) -> None:
        """Flush a final response tail even when it is shorter than the jitter lead."""
        with self._lock:
            if self._pending or self._chunks:
                self._primed = True

    def echo_reference_level(self, hold_seconds: float = 0.45) -> float:
        """Peak-hold output level, accounting for delayed laptop-speaker echo."""
        age = time.monotonic() - self._echo_reference_at
        if age >= hold_seconds:
            return 0.0
        # Decay gently instead of dropping between streamed network chunks.
        return self._echo_reference_level * max(0.35, 1.0 - age / hold_seconds)

    def _callback(self, outdata, frames, time_info, status) -> None:
        del time_info
        if status:
            self.logger.warning("speaker status: %s", status)
        requested = frames * 2
        with self._lock:
            # Realtime packets do not always arrive at perfectly even
            # intervals. Collect a small lead before starting each response
            # so a brief network jitter does not create audible gaps/jumps.
            if not self._primed:
                buffered = len(self._pending) + sum(map(len, self._chunks))
                target = self._device_rate * 2 * self.playback_buffer_ms // 1000
                self._primed = buffered >= target
            if not self._primed:
                outdata[:requested] = b"\x00" * requested
                available = 0
            else:
                while len(self._pending) < requested and self._chunks:
                    self._pending.extend(self._chunks.popleft())
                available = min(requested, len(self._pending))
                outdata[:available] = self._pending[:available]
                del self._pending[:available]
                if available < requested and not self._chunks and not self._pending:
                    # End of a response or a real network underrun. Require a
                    # fresh lead before resuming instead of playing fragments.
                    self._primed = False
        if available < requested:
            outdata[available:requested] = b"\x00" * (requested - available)
        if self._level_callback is not None and self._loop is not None:
            level = min(1.0, audioop.rms(bytes(outdata), 2) / 6500.0)
            self.current_level = level
            if level >= self._echo_reference_level or time.monotonic() - self._echo_reference_at > 0.45:
                self._echo_reference_level = level
                self._echo_reference_at = time.monotonic()
            self._loop.call_soon_threadsafe(self._level_callback, level)

    def stop(self) -> None:
        self.clear()
        if self._stream is not None:
            self._stream.stop(ignore_errors=True)
            self._stream.close(ignore_errors=True)
            self._stream = None
        self.logger.info("speaker stopped")
