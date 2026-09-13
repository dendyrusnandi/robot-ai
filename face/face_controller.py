from __future__ import annotations

import asyncio

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from core.event_bus import EventBus
from core.events import Event, EventType
from core.robot_state import Emotion, FaceState


class FaceController(QObject):
    stateChanged = Signal()
    emotionChanged = Signal()
    mouthOpenChanged = Signal()

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._bus = event_bus
        self._state = FaceState.BOOT.value
        self._emotion = Emotion.NEUTRAL.value
        self._mouth_open = 0.0
        self._mouth_target = 0.0
        self._mouth_timer = QTimer(self)
        self._mouth_timer.setInterval(33)
        self._mouth_timer.timeout.connect(self._animate_mouth)
        self._mouth_timer.start()
        self._bind_events()

    def _bind_events(self) -> None:
        mapping = {
            EventType.AI_CONNECTED: FaceState.IDLE,
            EventType.USER_SPEECH_STARTED: FaceState.LISTENING,
            EventType.USER_SPEECH_ENDED: FaceState.THINKING,
            EventType.AI_THINKING: FaceState.THINKING,
            EventType.AI_SPEECH_STARTED: FaceState.SPEAKING,
            EventType.AI_SPEECH_ENDED: FaceState.IDLE,
            EventType.VISION_REQUESTED: FaceState.VISION,
            EventType.AI_DISCONNECTED: FaceState.OFFLINE,
        }
        for event_type, state in mapping.items():
            self._bus.subscribe(event_type, lambda _, value=state: self.set_state(value.value))

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=emotionChanged)
    def emotion(self) -> str:
        return self._emotion

    @Property(float, notify=mouthOpenChanged)
    def mouthOpen(self) -> float:
        return self._mouth_open

    @mouthOpen.setter
    def mouthOpen(self, value: float) -> None:
        self.set_mouth_open(value)

    @Slot(str)
    def set_state(self, value: str) -> None:
        normalized = value.upper()
        if normalized not in FaceState.__members__:
            return
        if normalized != self._state:
            self._state = normalized
            self.stateChanged.emit()

    @Slot(str)
    def set_emotion(self, value: str) -> None:
        normalized = value.upper()
        if normalized not in Emotion.__members__:
            return
        if normalized != self._emotion:
            self._emotion = normalized
            self.emotionChanged.emit()

    @Slot(float)
    def set_mouth_open(self, value: float) -> None:
        self._mouth_target = max(0.0, min(1.0, value))

    def _animate_mouth(self) -> None:
        difference = self._mouth_target - self._mouth_open
        smoothing = 0.24 if difference > 0 else 0.11
        next_value = self._mouth_open + difference * smoothing
        if abs(difference) < 0.004:
            next_value = self._mouth_target
        if abs(next_value - self._mouth_open) > 0.0005:
            self._mouth_open = next_value
            self.mouthOpenChanged.emit()

    def wake(self) -> None:
        self.set_state(FaceState.WAKING.value)
        asyncio.get_running_loop().call_later(1.4, self.set_state, FaceState.IDLE.value)
