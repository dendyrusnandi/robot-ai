from __future__ import annotations

import audioop
import logging
from collections import deque
from typing import Any


class AdaptiveVoiceGate:
    """Low-cost adaptive VAD/noise gate for 16-bit mono PCM chunks."""

    def __init__(self, config: dict[str, Any]) -> None:
        chunk_ms = int(config.get("chunk_ms", 40))
        self.chunk_ms = chunk_ms
        self._log_interval = max(1, 1000 // chunk_ms)  # ~once per second
        self._log_counter = 0
        self.logger = logging.getLogger("AUDIO")
        self.enabled = bool(config.get("vad_enabled", True))
        self.minimum_level = int(config.get("vad_minimum_level", 280))
        self.noise_ratio = float(config.get("vad_noise_ratio", 2.2))
        self.rise_margin = int(config.get("vad_rise_margin", 140))
        self.minimum_chunks = max(1, int(config.get("minimum_speech_ms", 400)) // chunk_ms)
        self.feedback_chunks = max(
            1,
            min(
                self.minimum_chunks,
                int(config.get("listening_feedback_ms", 80)) // chunk_ms,
            ),
        )
        self.hangover_chunks = max(1, int(config.get("silence_release_ms", 650)) // chunk_ms)
        self.maximum_speech_chunks = max(
            self.minimum_chunks,
            int(config.get("maximum_speech_ms", 12000)) // chunk_ms,
        )
        self.attack_gap_chunks = max(1, int(config.get("vad_attack_gap_ms", 120)) // chunk_ms)
        pre_roll_chunks = max(1, int(config.get("vad_pre_roll_ms", 240)) // chunk_ms)
        self._pre_roll: deque[bytes] = deque(maxlen=pre_roll_chunks)
        self._candidate: list[bytes] = []
        self._candidate_voiced = 0
        self._candidate_gap = 0
        self._noise_floor = float(config.get("vad_initial_noise_level", 120))
        self._noise_ceiling = float(config.get("vad_noise_ceiling", 1600))
        self._speaking = False
        self._silence_chunks = 0
        self._speech_chunks = 0

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    @property
    def speaking(self) -> bool:
        return self._speaking

    @property
    def listening(self) -> bool:
        """Fast UI indication while the stricter speech gate is confirming audio."""
        return self._speaking or self._candidate_voiced >= self.feedback_chunks

    def process(self, pcm: bytes) -> list[bytes]:
        if not self.enabled:
            return [pcm]

        level = audioop.rms(pcm, 2)
        threshold = max(
            self.minimum_level,
            int(self._noise_floor * self.noise_ratio + self.rise_margin),
        )
        voiced = level >= threshold

        self._log_counter += 1
        if self._log_counter >= self._log_interval:
            self._log_counter = 0
            peak = audioop.max(pcm, 2)
            clipping = " CLIPPING" if peak >= 32000 else ""
            self.logger.debug(
                "vad level=%s peak=%s threshold=%s floor=%.0f speaking=%s voiced=%s%s",
                level, peak, threshold, self._noise_floor, self._speaking, voiced, clipping,
            )

        if not self._speaking:
            if voiced:
                if not self._candidate:
                    self._candidate.extend(self._pre_roll)
                self._candidate.append(pcm)
                self._candidate_voiced += 1
                self._candidate_gap = 0
                if self._candidate_voiced >= self.minimum_chunks:
                    self._speaking = True
                    self._silence_chunks = 0
                    self._speech_chunks = len(self._candidate)
                    output = self._candidate
                    self._candidate = []
                    self._candidate_voiced = 0
                    self._pre_roll.clear()
                    return output
                return []

            if self._candidate:
                # Tolerate brief dips inside a candidate (plosives, short gaps
                # between syllables) instead of discarding all progress on a
                # single quiet chunk.
                self._candidate.append(pcm)
                self._candidate_gap += 1
                if self._candidate_gap <= self.attack_gap_chunks:
                    return []
                self._candidate.clear()  # Reject clicks, knocks, and short sounds.
                self._candidate_voiced = 0
                self._candidate_gap = 0

            # Learn slowly only from chunks currently classified as background,
            # and cap the floor so it can never climb high enough to make
            # normal speech permanently undetectable.
            self._noise_floor = min(
                self._noise_ceiling, self._noise_floor * 0.97 + level * 0.03
            )
            self._pre_roll.append(pcm)
            return []

        if voiced:
            self._silence_chunks = 0
        else:
            self._silence_chunks += 1
            self._noise_floor = min(
                self._noise_ceiling, self._noise_floor * 0.995 + level * 0.005
            )

        self._speech_chunks += 1
        timed_out = self._speech_chunks >= self.maximum_speech_chunks
        if self._silence_chunks >= self.hangover_chunks or timed_out:
            if timed_out:
                self.logger.warning(
                    "forcing speech end after %sms; continuous noise may be keeping VAD open",
                    self.maximum_speech_chunks * self.chunk_ms,
                )
                # Treat the sustained level as the new room baseline so the
                # same fan/TV/noise does not immediately open another turn.
                self._noise_floor = min(
                    self._noise_ceiling, max(self._noise_floor, float(level))
                )
            self._speaking = False
            self._silence_chunks = 0
            self._speech_chunks = 0
            self._pre_roll.clear()
        return [pcm]

    def reset(self) -> None:
        self._pre_roll.clear()
        self._candidate.clear()
        self._candidate_voiced = 0
        self._candidate_gap = 0
        self._speaking = False
        self._silence_chunks = 0
        self._speech_chunks = 0
