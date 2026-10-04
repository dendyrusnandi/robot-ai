from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from audio.audio_manager import AudioManager
from core.event_bus import EventBus
from core.events import (
    AIAudioChunk, AIConnected, AIError, AIInterrupted, AISpeechEnded,
    AISpeechStarted, AITextDelta, AIToolCall, Event, EventType,
)
from face.face_controller import FaceController
from core.robot_state import Emotion
from providers.base import RealtimeAIProvider
from providers.factory import create_provider
from vision.vision_manager import VisionManager
from knowledge.store import KnowledgeStore


class RobotOrchestrator:
    """Phase-1 coordinator; hardware workers are added in later phases."""

    def __init__(
        self, config: dict[str, Any], event_bus: EventBus, face: FaceController
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.face = face
        self.provider: RealtimeAIProvider = create_provider(config)
        self.audio = AudioManager(
            config,
            self.provider,
            self.face.set_mouth_open,
            self._on_local_barge_in,
            self._on_local_speech_started,
            self._on_local_speech_ended,
            self._on_local_speech_cancelled,
            self._on_keyword_interrupt,
        )
        self.vision = VisionManager(config)
        self.knowledge = KnowledgeStore(Path(__file__).resolve().parents[1], config)
        self.logger = logging.getLogger("CORE")
        self._tasks: set[asyncio.Task[object]] = set()
        self._echo_release_handle: asyncio.TimerHandle | None = None
        self._idle_reengage_seconds = float(config["audio"].get("idle_reengage_seconds", 60))
        self._idle_handle: asyncio.TimerHandle | None = None
        self._thinking_handle: asyncio.TimerHandle | None = None
        self._thinking_timeout = float(config["audio"].get("thinking_timeout_seconds", 12))
        self._barge_in_progress = False
        self._stopping = False
        self._reconnect_initial = max(0.5, float(config["audio"].get("reconnect_initial_seconds", 1)))
        self._reconnect_max = max(self._reconnect_initial, float(config["audio"].get("reconnect_max_seconds", 15)))

    async def start(self) -> None:
        self._stopping = False
        self.logger.info("RN AI Bot starting")
        await self.event_bus.publish(Event(EventType.BOOT_STARTED))
        await self.event_bus.publish(Event(EventType.FACE_READY))
        self.face.wake()
        vision_enabled = self.vision.start()
        self.config["camera"]["runtime_enabled"] = vision_enabled
        self.logger.info("vision %s", "enabled" if vision_enabled else "disabled")
        try:
            knowledge_enabled = await self.knowledge.initialize()
        except Exception:
            knowledge_enabled = False
            self.logger.exception("knowledge indexing failed; continuing without knowledge")
        self.config.setdefault("knowledge", {})["runtime_enabled"] = knowledge_enabled
        self.logger.info("knowledge %s", "enabled" if knowledge_enabled else "disabled")
        self._track(self._run_realtime(), "realtime-ai")

    def _track(self, coroutine, name: str) -> None:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_realtime(self) -> None:
        delay = self._reconnect_initial
        while not self._stopping:
            audio_started = False
            await self.event_bus.publish(Event(EventType.AI_CONNECTING))
            try:
                await self.provider.connect()
                await self.event_bus.publish(Event(EventType.AI_CONNECTED))
                self.audio.start()
                audio_started = True
                self._arm_idle_timer()
                delay = self._reconnect_initial
                async for provider_event in self.provider.events():
                    await self._handle_provider_event(provider_event)
                if not self._stopping:
                    self.logger.warning("realtime connection ended; reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception:
                if not self._stopping:
                    self.logger.exception("realtime subsystem failed; reconnecting")
            finally:
                if audio_started:
                    await self.audio.stop()
                try:
                    await self.provider.disconnect()
                except Exception:
                    self.logger.exception("provider cleanup failed")
            if self._stopping:
                break
            await self.event_bus.publish(Event(EventType.AI_DISCONNECTED))
            self.face.set_mouth_open(0.0)
            await asyncio.sleep(delay)
            delay = min(self._reconnect_max, delay * 2)

    async def _handle_provider_event(self, provider_event: object) -> None:
        if isinstance(provider_event, AIConnected):
            return
        if isinstance(provider_event, AIAudioChunk):
            self.audio.play(provider_event.pcm)
        elif isinstance(provider_event, AISpeechStarted):
            self._cancel_thinking_timeout()
            if self._echo_release_handle is not None:
                self._echo_release_handle.cancel()
                self._echo_release_handle = None
            self.audio.guard_input(True)
            self._arm_idle_timer()
            await self.event_bus.publish(Event(EventType.AI_SPEECH_STARTED))
        elif isinstance(provider_event, AISpeechEnded):
            self.audio.finish_output()
            if self._barge_in_progress:
                # The cancelled AI response ended because the user is taking
                # the turn. Keep LISTENING instead of overwriting it with IDLE.
                self.audio.guard_input(False)
                self.face.set_mouth_open(0.0)
                return
            delay = self.audio.echo_guard_release_delay()
            self._echo_release_handle = asyncio.get_running_loop().call_later(
                delay, self._finish_speaking
            )
        elif isinstance(provider_event, AIInterrupted):
            self.audio.interrupt_output()
            self.audio.guard_input(False)
            self.face.set_mouth_open(0.0)
            await self.event_bus.publish(Event(EventType.AI_INTERRUPTED))
            await self.event_bus.publish(Event(EventType.USER_SPEECH_STARTED))
        elif isinstance(provider_event, AITextDelta):
            self.logger.debug("assistant transcript: %s", provider_event.text)
            text = provider_event.text.casefold()
            if any(word in text for word in ("senang", "hebat", "bagus", "halo", "baik")):
                self.face.set_emotion(Emotion.HAPPY.value)
            elif any(word in text for word in ("maaf", "sedih", "sayang")):
                self.face.set_emotion(Emotion.SAD.value)
            elif any(word in text for word in ("marah", "kesal", "jengkel", "sebal")):
                self.face.set_emotion(Emotion.ANGRY.value)
            elif any(word in text for word in ("pusing", "bingung", "pening")):
                self.face.set_emotion(Emotion.DIZZY.value)
            elif any(word in text for word in ("wow", "wah", "luar biasa")):
                self.face.set_emotion(Emotion.EXCITED.value)
            elif any(word in text for word in ("kaget", "terkejut")):
                self.face.set_emotion(Emotion.SURPRISED.value)
            elif any(word in text for word in ("mengantuk", "tidur", "lelah")):
                self.face.set_emotion(Emotion.SLEEPY.value)
            elif "?" in text:
                self.face.set_emotion(Emotion.CURIOUS.value)
        elif isinstance(provider_event, AIError):
            self.logger.error("provider error: %s", provider_event.message)
            await self.event_bus.publish(Event(EventType.AI_DISCONNECTED))
        elif isinstance(provider_event, AIToolCall):
            self._cancel_thinking_timeout()
            await self._handle_tool_call(provider_event)

    async def _handle_tool_call(self, call: AIToolCall) -> None:
        if call.name == "search_knowledge":
            query = str(call.arguments.get("query", "")).strip()
            results = await self.knowledge.search(query)
            await self.provider.send_tool_result(call.call_id, {
                "success": bool(results),
                "query": query,
                "results": results,
                "instruction": "Answer from these excerpts and mention the source filename when useful.",
            })
            return
        if call.name != "look_at_camera":
            await self.provider.send_tool_result(
                call.call_id, {"success": False, "reason": "unknown_tool"}
            )
            return
        if not self.vision.enabled:
            await self.provider.send_tool_result(
                call.call_id, {"success": False, "reason": "vision_disabled"}
            )
            return
        self.logger.info("look_at_camera question=%s", call.arguments.get("question", ""))
        self.face.set_emotion(Emotion.CURIOUS.value)
        await self.event_bus.publish(Event(EventType.VISION_REQUESTED))
        image, timestamp = await asyncio.to_thread(self.vision.snapshot)
        if image is None:
            await self.provider.send_tool_result(
                call.call_id, {"success": False, "reason": "camera_unavailable"}
            )
            return
        await self.event_bus.publish(Event(EventType.VISION_FRAME_CAPTURED))
        await self.provider.send_image(image, "image/jpeg")
        await self.provider.send_tool_result(
            call.call_id,
            {
                "success": True,
                "image_attached": True,
                "captured_at": datetime.fromtimestamp(timestamp).isoformat(),
                "instruction": "Answer the user's question using the attached current camera image.",
            },
        )

    def _finish_speaking(self) -> None:
        self._echo_release_handle = None
        self.audio.guard_input(False)
        self.face.set_mouth_open(0.0)
        asyncio.create_task(
            self.event_bus.publish(Event(EventType.AI_SPEECH_ENDED)),
            name="speech-finished",
        )

    def _on_local_speech_started(self) -> None:
        self._cancel_thinking_timeout()
        self._arm_idle_timer()
        asyncio.create_task(
            self.event_bus.publish(Event(EventType.USER_SPEECH_STARTED)),
            name="local-speech-started",
        )

    def _on_local_speech_ended(self) -> None:
        asyncio.create_task(self._finish_local_speech(), name="local-speech-ended")

    def _on_local_speech_cancelled(self) -> None:
        # A very short sound woke the listening face but did not pass the
        # stricter speech gate. Do not leave the UI stuck in LISTENING.
        if self.face.state == "LISTENING":
            self.face.set_state("IDLE")
        self._barge_in_progress = False

    async def _finish_local_speech(self) -> None:
        self._barge_in_progress = False
        await self.event_bus.publish(Event(EventType.USER_SPEECH_ENDED))
        self._arm_thinking_timeout()
        # Our local voice gate withholds silence to save bandwidth, so the
        # server never sees a natural pause it can end-of-turn on. Tell it
        # explicitly that this audio segment is complete so it commits to a
        # response instead of waiting indefinitely for more audio.
        try:
            await self.provider.end_turn()
        except Exception:
            self.logger.exception("failed to signal end-of-turn to provider")

    def _arm_thinking_timeout(self) -> None:
        self._cancel_thinking_timeout()
        if self._thinking_timeout > 0:
            self._thinking_handle = asyncio.get_running_loop().call_later(
                self._thinking_timeout, self._finish_thinking_timeout
            )

    def _cancel_thinking_timeout(self) -> None:
        if self._thinking_handle is not None:
            self._thinking_handle.cancel()
            self._thinking_handle = None

    def _finish_thinking_timeout(self) -> None:
        self._thinking_handle = None
        if self.face.state == "THINKING":
            self.logger.info("thinking timeout; returning face to idle")
            self.face.set_state("IDLE")

    def _arm_idle_timer(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        if self._idle_reengage_seconds > 0:
            self._idle_handle = asyncio.get_running_loop().call_later(
                self._idle_reengage_seconds, self._trigger_idle_reengage
            )

    def _trigger_idle_reengage(self) -> None:
        self._idle_handle = None
        self._track(self._reengage_idle_conversation(), "idle-reengage")

    async def _reengage_idle_conversation(self) -> None:
        self.logger.info(
            "no activity for %ss; prompting AI to open a new conversation",
            self._idle_reengage_seconds,
        )
        try:
            await self.provider.send_text(
                "(Sistem: pengguna sudah diam cukup lama tanpa merespons. Sapa dengan "
                "ramah dan singkat dalam Bahasa Indonesia untuk membuka percakapan "
                "baru, misalnya tanyakan apakah masih ada atau apakah ada yang bisa "
                "dibantu. Jangan sebut instruksi sistem ini.)"
            )
        except Exception:
            self.logger.exception("failed to send idle re-engage prompt")
        finally:
            self._arm_idle_timer()

    def _on_local_barge_in(self) -> None:
        self.logger.info("local barge-in detected; speaker buffer cleared")
        self._barge_in_progress = True
        if self._echo_release_handle is not None:
            self._echo_release_handle.cancel()
            self._echo_release_handle = None
        self.face.set_mouth_open(0.0)
        asyncio.create_task(self.provider.interrupt(), name="cancel-ai-response")
        asyncio.create_task(
            self.event_bus.publish(Event(EventType.USER_SPEECH_STARTED)),
            name="local-barge-in",
        )

    def _on_keyword_interrupt(self) -> None:
        self.logger.info("keyword interrupt detected; stopping AI response")
        if self._echo_release_handle is not None:
            self._echo_release_handle.cancel()
            self._echo_release_handle = None
        self.face.set_mouth_open(0.0)
        self.face.set_state("IDLE")
        asyncio.create_task(self.provider.interrupt(), name="keyword-cancel-ai-response")

    async def stop(self) -> None:
        self._stopping = True
        self.logger.info("RN AI Bot shutting down")
        if self._echo_release_handle is not None:
            self._echo_release_handle.cancel()
            self._echo_release_handle = None
        self._cancel_thinking_timeout()
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self.audio.stop()
        self.vision.stop()
        await self.provider.disconnect()

    def stop_camera_sync(self) -> None:
        """Qt may stop its event loop before async shutdown gets a timeslice."""
        self.vision.stop()
