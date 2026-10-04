from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):
    BOOT_STARTED = "BOOT_STARTED"
    FACE_READY = "FACE_READY"
    AI_CONNECTING = "AI_CONNECTING"
    AI_CONNECTED = "AI_CONNECTED"
    AI_DISCONNECTED = "AI_DISCONNECTED"
    USER_SPEECH_STARTED = "USER_SPEECH_STARTED"
    USER_SPEECH_ENDED = "USER_SPEECH_ENDED"
    AI_THINKING = "AI_THINKING"
    AI_SPEECH_STARTED = "AI_SPEECH_STARTED"
    AI_SPEECH_ENDED = "AI_SPEECH_ENDED"
    AI_INTERRUPTED = "AI_INTERRUPTED"
    VISION_REQUESTED = "VISION_REQUESTED"
    VISION_FRAME_CAPTURED = "VISION_FRAME_CAPTURED"
    TOOL_CALL_RECEIVED = "TOOL_CALL_RECEIVED"
    TOOL_CALL_COMPLETED = "TOOL_CALL_COMPLETED"
    TOOL_CALL_REJECTED = "TOOL_CALL_REJECTED"
    ESP32_CONNECTED = "ESP32_CONNECTED"
    ESP32_DISCONNECTED = "ESP32_DISCONNECTED"
    MOTION_STARTED = "MOTION_STARTED"
    MOTION_FINISHED = "MOTION_FINISHED"
    MANUAL_OVERRIDE_ON = "MANUAL_OVERRIDE_ON"
    MANUAL_OVERRIDE_OFF = "MANUAL_OVERRIDE_OFF"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    payload: Any = None


@dataclass(frozen=True, slots=True)
class AIConnected:
    pass


@dataclass(frozen=True, slots=True)
class AITextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class AIAudioChunk:
    pcm: bytes
    sample_rate: int


@dataclass(frozen=True, slots=True)
class AISpeechStarted:
    pass


@dataclass(frozen=True, slots=True)
class AISpeechEnded:
    pass


@dataclass(frozen=True, slots=True)
class AIInterrupted:
    pass


@dataclass(frozen=True, slots=True)
class AIToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AIError:
    message: str
