from enum import Enum


class FaceState(str, Enum):
    BOOT = "BOOT"
    WAKING = "WAKING"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    VISION = "VISION"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    SLEEPING = "SLEEPING"


class Emotion(str, Enum):
    NEUTRAL = "NEUTRAL"
    HAPPY = "HAPPY"
    EXCITED = "EXCITED"
    CURIOUS = "CURIOUS"
    SURPRISED = "SURPRISED"
    SAD = "SAD"
    ANGRY = "ANGRY"
    DIZZY = "DIZZY"
    SLEEPY = "SLEEPY"


class Readiness(str, Enum):
    STARTING = "STARTING"
    PARTIAL_READY = "PARTIAL_READY"
    READY = "READY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
