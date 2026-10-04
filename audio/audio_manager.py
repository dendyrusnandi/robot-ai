from __future__ import annotations

import asyncio
import audioop
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from audio.microphone import Microphone
from audio.speaker import Speaker
from audio.voice_gate import AdaptiveVoiceGate
from providers.base import RealtimeAIProvider


class AudioManager:
    def __init__(
        self,
        config: dict[str, Any],
        provider: RealtimeAIProvider,
        level_callback: Callable[[float], None] | None = None,
        barge_in_callback: Callable[[], None] | None = None,
        speech_started_callback: Callable[[], None] | None = None,
        speech_ended_callback: Callable[[], None] | None = None,
        speech_cancelled_callback: Callable[[], None] | None = None,
        keyword_interrupt_callback: Callable[[], None] | None = None,
    ) -> None:
        audio_config = config["audio"]
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=int(audio_config.get("queue_size", 32))
        )
        self.microphone = Microphone(audio_config, self.input_queue)
        self.speaker = Speaker(audio_config, level_callback)
        self.voice_gate = AdaptiveVoiceGate(audio_config)
        self.provider = provider
        self.echo_guard_enabled = bool(audio_config.get("echo_guard_enabled", True))
        self.echo_guard_release_ms = int(audio_config.get("echo_guard_release_ms", 250))
        self.barge_in_enabled = bool(audio_config.get("barge_in_enabled", True))
        self.barge_in_mode = str(
            audio_config.get("barge_in_mode", "bebas" if self.barge_in_enabled else "kata_kunci")
        )
        self.barge_in_min_level = float(audio_config.get("barge_in_min_level", 0.40))
        self.barge_in_echo_ratio = float(audio_config.get("barge_in_echo_ratio", 2.0))
        self.barge_in_chunks = int(audio_config.get("barge_in_chunks", 5))
        self.barge_in_grace_ms = int(audio_config.get("barge_in_grace_ms", 650))
        self._barge_in_callback = barge_in_callback
        self._speech_started_callback = speech_started_callback
        self._speech_ended_callback = speech_ended_callback
        self._speech_cancelled_callback = speech_cancelled_callback
        self._keyword_interrupt_callback = keyword_interrupt_callback
        self._barge_count = 0
        self._prebuffer: deque[bytes] = deque(maxlen=6)
        self._input_muted = False
        self._guard_started_at = 0.0
        keyword_config = dict(audio_config)
        keyword_config.update(minimum_speech_ms=240, silence_release_ms=320, maximum_speech_ms=3000)
        self._keyword_gate = AdaptiveVoiceGate(keyword_config)
        self._keyword_audio = bytearray()
        self._keyword_task: asyncio.Task[None] | None = None
        self._send_task: asyncio.Task[None] | None = None
        self.logger = logging.getLogger("AUDIO")

    def start(self) -> None:
        if self._send_task is not None and not self._send_task.done():
            return
        self.voice_gate.reset()
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.logger.info(
            "adaptive voice gate=%s minimum=%sms release=%sms",
            self.voice_gate.enabled,
            self.voice_gate.minimum_chunks * self.microphone.chunk_ms,
            self.voice_gate.hangover_chunks * self.microphone.chunk_ms,
        )
        self.speaker.start()
        self.microphone.start()
        self._send_task = asyncio.create_task(self._send_microphone(), name="microphone-sender")

    async def _send_microphone(self) -> None:
        while True:
            pcm = await self.input_queue.get()
            if self._input_muted:
                if self.barge_in_mode == "kata_kunci":
                    self._process_keyword_audio(pcm)
                    continue
                self._prebuffer.append(pcm)
                if self._is_barge_in(pcm):
                    self._input_muted = False
                    self.speaker.clear()
                    if self._barge_in_callback is not None:
                        self._barge_in_callback()
                    # Never send raw buffered echo directly. Feed it through
                    # the normal VAD so only a sustained human interruption
                    # reaches the provider.
                    self.voice_gate.reset()
                    for buffered in self._prebuffer:
                        for filtered in self.voice_gate.process(buffered):
                            await self.provider.send_audio(filtered)
                    self._prebuffer.clear()
                continue
            was_speaking = self.voice_gate.speaking
            was_listening = self.voice_gate.listening
            chunks = self.voice_gate.process(pcm)
            is_listening = self.voice_gate.listening
            if is_listening and not was_listening:
                if self._speech_started_callback is not None:
                    self._speech_started_callback()
            elif was_listening and not is_listening and not was_speaking:
                if self._speech_cancelled_callback is not None:
                    self._speech_cancelled_callback()
            if was_speaking and not self.voice_gate.speaking:
                if self._speech_ended_callback is not None:
                    self._speech_ended_callback()
            for filtered_chunk in chunks:
                await self.provider.send_audio(filtered_chunk)

    def _is_barge_in(self, pcm: bytes) -> bool:
        if not self.barge_in_enabled or self.barge_in_mode != "bebas":
            return False
        if (time.monotonic() - self._guard_started_at) * 1000 < self.barge_in_grace_ms:
            self._barge_count = 0
            return False
        input_level = min(1.0, audioop.rms(pcm, 2) / 6500.0)
        threshold = max(
            self.barge_in_min_level,
            self.speaker.echo_reference_level() * self.barge_in_echo_ratio,
        )
        self._barge_count = self._barge_count + 1 if input_level >= threshold else 0
        return self._barge_count >= self.barge_in_chunks

    def _process_keyword_audio(self, pcm: bytes) -> None:
        was_speaking = self._keyword_gate.speaking
        chunks = self._keyword_gate.process(pcm)
        for chunk in chunks:
            self._keyword_audio.extend(chunk)
        if was_speaking and not self._keyword_gate.speaking and self._keyword_audio:
            audio = bytes(self._keyword_audio)
            self._keyword_audio.clear()
            if self._keyword_task is None or self._keyword_task.done():
                self._keyword_task = asyncio.create_task(
                    self._check_interrupt_keyword(audio), name="keyword-interrupt"
                )

    async def _check_interrupt_keyword(self, pcm: bytes) -> None:
        if not await self.provider.detect_interrupt_keyword(
            pcm, self.microphone.sample_rate
        ):
            return
        self.speaker.clear()
        if self._keyword_interrupt_callback is not None:
            self._keyword_interrupt_callback()

    def play(self, pcm: bytes) -> None:
        self.speaker.enqueue(pcm)

    def interrupt_output(self) -> None:
        self.speaker.clear()

    def finish_output(self) -> None:
        self.speaker.finish_response()

    def guard_input(self, enabled: bool) -> None:
        if self.echo_guard_enabled:
            self._input_muted = enabled
            if enabled:
                self._guard_started_at = time.monotonic()
            self._barge_count = 0
            self._prebuffer.clear()
            self.voice_gate.reset()
            self._keyword_gate.reset()
            self._keyword_audio.clear()
            if enabled:
                while not self.input_queue.empty():
                    try:
                        self.input_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

    def echo_guard_release_delay(self) -> float:
        return self.speaker.buffered_seconds() + self.echo_guard_release_ms / 1000

    async def stop(self) -> None:
        self.microphone.stop()
        if self._send_task is not None:
            self._send_task.cancel()
            await asyncio.gather(self._send_task, return_exceptions=True)
            self._send_task = None
        self.speaker.stop()
