from __future__ import annotations

import asyncio
import audioop
import logging
import time
from typing import Any

import sounddevice as sd


class Microphone:
    def __init__(self, config: dict[str, Any], queue: asyncio.Queue[bytes]) -> None:
        self.sample_rate = int(config["input_sample_rate"])
        self.channels = int(config.get("input_channels", 1))
        self.chunk_ms = int(config.get("chunk_ms", 40))
        self.device = config.get("input_device")
        self.queue = queue
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stream: sd.RawInputStream | None = None
        self.logger = logging.getLogger("AUDIO")
        self._silent_chunks = 0
        self._silence_warning_chunks = max(1, 5000 // self.chunk_ms)
        self._silence_warned = False

    def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        blocksize = self.sample_rate * self.chunk_ms // 1000
        self.stream = self._open_stream(blocksize)
        self.stream.start()
        self.logger.info(
            "microphone started device=%s %s Hz, %s ms chunks",
            self.device or "default", self.sample_rate, self.chunk_ms,
        )

    def _open_stream(self, blocksize: int, attempts: int = 4, retry_delay: float = 0.3) -> sd.RawInputStream:
        # Same transient "device busy" issue as the speaker can happen here;
        # retry briefly instead of killing the whole AI session.
        for attempt in range(1, attempts + 1):
            try:
                return sd.RawInputStream(
                    samplerate=self.sample_rate,
                    blocksize=blocksize,
                    device=self.device,
                    channels=self.channels,
                    dtype="int16",
                    callback=self._callback,
                )
            except sd.PortAudioError as exc:
                if attempt == attempts:
                    raise
                self.logger.warning(
                    "microphone open failed, retrying (%s/%s): %s", attempt, attempts, exc
                )
                time.sleep(retry_delay)
        raise AssertionError("unreachable")

    def _callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info
        if status:
            self.logger.warning("microphone status: %s", status)
        data = bytes(indata)
        if audioop.max(data, 2) == 0:
            self._silent_chunks += 1
            if (
                self._silent_chunks >= self._silence_warning_chunks
                and not self._silence_warned
            ):
                self._silence_warned = True
                self.logger.error(
                    "microphone is returning digital silence; check PulseAudio "
                    "input source, mute state, and the user running start.sh"
                )
        else:
            self._silent_chunks = 0
            self._silence_warned = False
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._put_latest, data)

    def _put_latest(self, data: bytes) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(data)

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.logger.info("microphone stopped")
