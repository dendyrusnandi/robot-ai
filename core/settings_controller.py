from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Property, QObject, Signal, Slot


class SettingsController(QObject):
    OPENAI_VOICES = {
        "alloy", "ash", "ballad", "coral", "echo",
        "sage", "shimmer", "verse", "marin", "cedar",
    }
    RESPONSE_STYLES = {"kasual", "formal", "profesional", "ramah", "ringkas", "humoris"}
    valuesChanged = Signal()
    saved = Signal(str)

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        super().__init__()
        self.root = root
        self.config_path = root / "config.yaml"
        self.env_path = root / ".env"
        self.config = config

    @Property("QVariantMap", notify=valuesChanged)
    def values(self) -> dict[str, Any]:
        audio = self.config["audio"]
        provider = str(self.config["ai"].get("provider", "gemini"))
        knowledge = self.config.get("knowledge", {})
        return {
            "provider": provider,
            "apiKeySet": bool(os.getenv("GEMINI_API_KEY")),
            "openaiApiKeySet": bool(os.getenv("OPENAI_API_KEY")),
            "language": self.config["app"].get("language", "id-ID"),
            "responseStyle": self.config["app"].get("response_style", "kasual"),
            "model": self.config["providers"].get(provider, {}).get("model", ""),
            "geminiModel": self.config["providers"].get("gemini", {}).get("model", ""),
            "openaiModel": self.config["providers"].get("openai", {}).get("model", ""),
            "openaiVoice": self.config["providers"].get("openai", {}).get("voice", "marin"),
            "vadEnabled": bool(audio.get("vad_enabled", True)),
            "vadMinimumLevel": int(audio.get("vad_minimum_level", 280)),
            "vadNoiseRatio": float(audio.get("vad_noise_ratio", 2.2)),
            "minimumSpeechMs": int(audio.get("minimum_speech_ms", 400)),
            "silenceReleaseMs": int(audio.get("silence_release_ms", 650)),
            "wakeWord": str(audio.get("wake_word", "RN")),
            "echoGuard": bool(audio.get("echo_guard_enabled", True)),
            "bargeIn": bool(audio.get("barge_in_enabled", True)),
            "bargeInMode": str(audio.get("barge_in_mode", "bebas")),
            "cameraDevice": str(self.config["camera"].get("device", 0)),
            "fullscreen": bool(self.config["display"].get("fullscreen", True)),
            "debug": bool(self.config["app"].get("debug", False)),
            "knowledgeEnabled": bool(knowledge.get("enabled", True)),
            "knowledgeFolder": str(knowledge.get("folder", "knowledge")),
        }

    @Slot("QVariantMap", result=str)
    def save(self, values: dict[str, Any]) -> str:
        try:
            audio = self.config["audio"]
            provider = str(values.get("provider", "gemini")).strip() or "gemini"
            if provider not in ("gemini", "openai"):
                raise ValueError(f"provider AI tidak dikenal: {provider}")
            self.config["ai"]["provider"] = provider
            self.config["app"]["language"] = str(values.get("language", "id-ID")).strip() or "id-ID"
            response_style = str(values.get("responseStyle", "kasual")).strip().lower()
            if response_style not in self.RESPONSE_STYLES:
                raise ValueError(f"gaya jawaban tidak dikenal: {response_style}")
            self.config["app"]["response_style"] = response_style
            self.config["app"]["debug"] = bool(values.get("debug", False))
            model = str(values.get("model", "")).strip()
            if not model:
                raise ValueError(f"model {provider} tidak boleh kosong")
            self.config["providers"].setdefault(provider, {})["model"] = model
            voice = str(values.get("openaiVoice", "marin")).strip().lower()
            if voice not in self.OPENAI_VOICES:
                raise ValueError(f"voice OpenAI tidak dikenal: {voice}")
            self.config["providers"].setdefault("openai", {})["voice"] = voice
            audio["vad_enabled"] = bool(values.get("vadEnabled", True))
            audio["vad_minimum_level"] = self._integer(values, "vadMinimumLevel", 80, 10000)
            audio["vad_noise_ratio"] = self._number(values, "vadNoiseRatio", 1.1, 8.0)
            audio["minimum_speech_ms"] = self._integer(values, "minimumSpeechMs", 80, 3000)
            audio["silence_release_ms"] = self._integer(values, "silenceReleaseMs", 120, 5000)
            audio["wake_word"] = str(values.get("wakeWord", "RN")).strip() or "RN"
            audio["echo_guard_enabled"] = bool(values.get("echoGuard", True))
            barge_mode = str(values.get("bargeInMode", "bebas")).strip().lower()
            if barge_mode not in ("bebas", "kata_kunci"):
                raise ValueError(f"mode interupsi tidak dikenal: {barge_mode}")
            audio["barge_in_mode"] = barge_mode
            audio["barge_in_enabled"] = barge_mode == "bebas"
            device = str(values.get("cameraDevice", "0")).strip()
            self.config["camera"]["device"] = int(device) if device.lstrip("-").isdigit() else device
            self.config["display"]["fullscreen"] = bool(values.get("fullscreen", True))
            knowledge = self.config.setdefault("knowledge", {})
            knowledge["enabled"] = bool(values.get("knowledgeEnabled", True))
            folder = str(values.get("knowledgeFolder", "knowledge")).strip()
            if not folder or folder.startswith("/") or ".." in Path(folder).parts:
                raise ValueError("folder knowledge harus berupa path relatif yang aman")
            knowledge["folder"] = folder

            api_key = str(values.get("apiKey", "")).strip()
            if api_key and ("\n" in api_key or "\r" in api_key):
                raise ValueError("format API key tidak valid")

            temporary = self.config_path.with_suffix(".yaml.tmp")
            temporary.write_text(
                yaml.safe_dump(self.config, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            temporary.replace(self.config_path)

            if api_key:
                env_key = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
                self._write_env_value(env_key, api_key)
                os.environ[env_key] = api_key
            self.valuesChanged.emit()
            message = "Tersimpan. Restart RN AI Bot untuk menerapkan perubahan."
            self.saved.emit(message)
            return message
        except (TypeError, ValueError, OSError) as exc:
            return f"Gagal menyimpan: {exc}"

    def _write_env_value(self, key: str, value: str) -> None:
        lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.exists() else []
        replacement = f"{key}={value}"
        output: list[str] = []
        found = False
        for line in lines:
            if line.strip().startswith(f"{key}="):
                output.append(replacement)
                found = True
            else:
                output.append(line)
        if not found:
            output.append(replacement)
        temporary = self.env_path.with_suffix(".env.tmp")
        temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.env_path)

    @staticmethod
    def _integer(values: dict[str, Any], key: str, low: int, high: int) -> int:
        return max(low, min(high, int(float(values[key]))))

    @staticmethod
    def _number(values: dict[str, Any], key: str, low: float, high: float) -> float:
        return max(low, min(high, float(values[key])))
