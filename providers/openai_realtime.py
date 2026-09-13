from __future__ import annotations

import asyncio
import audioop
import base64
import json
import io
import logging
import os
import wave
from collections.abc import AsyncIterator
from typing import Any

import websockets
import httpx

from core.events import (
    AIAudioChunk, AIConnected, AIError, AISpeechEnded,
    AISpeechStarted, AITextDelta, AIToolCall,
)
from core.response_style import response_style_instruction
from providers.base import RealtimeAIProvider

REALTIME_URL = "wss://api.openai.com/v1/realtime"
# The Realtime API's pcm16 format is fixed at 24kHz mono regardless of what
# our microphone/speaker are configured for, so we resample at the edges.
OPENAI_PCM_RATE = 24000

SYSTEM_INSTRUCTION = """Kamu adalah RN, robot AI humanoid yang ramah dan multibahasa.
Bahasa default kamu SELALU Bahasa Indonesia yang natural, jelas, dan ringkas, dan kamu
memulai maupun kembali ke Bahasa Indonesia kecuali salah satu syarat di bawah terpenuhi.
Hanya beralih ke bahasa lain jika pengguna mengucapkan SATU KALIMAT PENUH yang jelas dan
bermakna dalam bahasa itu (bukan sekadar beberapa kata atau bunyi pendek/terputus). Ucapan
yang sangat singkat, terpotong, tidak jelas, atau terdengar seperti bunyi/gumaman/latar
BUKAN dasar yang cukup untuk berganti bahasa — anggap itu ambigu dan tetap balas dalam
Bahasa Indonesia sambil meminta pengguna mengulang lebih jelas. Jangan pernah menebak atau
mengarang bahasa dari audio yang tidak yakin kamu dengar dengan jelas.
Jika pengguna meminta bahasa tertentu secara eksplisit, gunakan bahasa yang diminta sampai
pengguna menggantinya. Jika ragu sama sekali, selalu gunakan Bahasa Indonesia.
Audiomu diputar langsung lewat speaker robot. Jangan pernah menyebut API internal.
Jika kamu tidak dapat mendengar dengan jelas, minta pengguna mengulang. Jangan mengarang
informasi visual. Bedakan ucapan pengguna yang ditujukan kepadamu dari televisi, musik,
percakapan orang lain, dan suara latar. Abaikan ucapan yang jelas bukan ditujukan kepadamu.
Dalam keadaan ramai atau ketika tujuan ucapan ambigu, hanya tanggapi jika pengguna memanggil
"RN". Dalam keadaan tenang, pengguna tetap boleh berbicara langsung tanpa kata panggil.
Nama domain, URL, merek, nama orang, dan kode harus dipertahankan persis seperti yang
terdengar. Jangan mengganti atau mengarang nama yang mirip. Jika ejaan kurang yakin,
ucapkan kembali nama yang kamu dengar lalu minta konfirmasi sebelum melanjutkan. Kamu
tidak memiliki akses browsing web langsung kecuali tersedia tool web khusus dalam sesi.
Jangan mengaku sudah membuka atau memeriksa situs jika tool tersebut tidak tersedia.
Jika pengguna bertanya tentang apa yang terlihat, ada siapa atau benda apa di depan, warna,
jumlah orang, atau keadaan sekitar saat ini, WAJIB panggil tool look_at_camera. Jangan
pernah menebak isi kamera tanpa snapshot terbaru.
"""

VISION_TOOL = {
    "type": "function",
    "name": "look_at_camera",
    "description": "Observe the current scene from the robot's front camera before answering a visual question.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What should be examined in the current camera image?",
            }
        },
        "required": ["question"],
    },
}

KNOWLEDGE_TOOL = {
    "type": "function",
    "name": "search_knowledge",
    "description": "Search approved local company, product, FAQ, about-us, and manual documents before answering.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The user's product or company question."}},
        "required": ["query"],
    },
}


class OpenAIRealtimeProvider(RealtimeAIProvider):
    """Adapter for OpenAI's Realtime API (WebSocket, GA `gpt-realtime` family).

    Turn-taking mirrors GeminiLiveProvider: our own local voice gate decides
    when the user has stopped speaking (see RobotOrchestrator), so server-side
    VAD is disabled and `interrupt()` explicitly commits the audio buffer and
    asks for a response instead of relying on OpenAI's own turn detection.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        openai_config = config["providers"]["openai"]
        self.model = openai_config.get("model", "gpt-realtime")
        self.voice = openai_config.get("voice", "marin")
        self.transcribe_model = openai_config.get("transcribe_model", "gpt-4o-transcribe")
        self.input_rate = int(config["audio"]["input_sample_rate"])
        self.output_rate = int(config["audio"].get("output_sample_rate", 24000))
        self._ws: Any = None
        self._connected = False
        self._speaking = False
        self._response_active = False
        self._in_resample_state = None
        self._call_names: dict[str, str] = {}
        self.logger = logging.getLogger("AI")

    async def connect(self) -> None:
        self._speaking = False
        self._response_active = False
        self._in_resample_state = None
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        url = f"{REALTIME_URL}?model={self.model}"
        self._ws = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            max_size=None,
        )
        created = json.loads(await asyncio.wait_for(self._ws.recv(), timeout=15))
        if created.get("type") == "error":
            raise RuntimeError(str(created.get("error", created)))
        if created.get("type") != "session.created":
            raise RuntimeError(f"Unexpected OpenAI event: {created.get('type')}")
        vision_enabled = bool(self.config["camera"].get("runtime_enabled", False))
        knowledge_enabled = bool(self.config.get("knowledge", {}).get("runtime_enabled", False))
        instructions = SYSTEM_INSTRUCTION if vision_enabled else SYSTEM_INSTRUCTION + (
            "\nKamera tidak tersedia. Vision sedang nonaktif. Jika ditanya tentang apa "
            "yang terlihat, jelaskan dengan singkat bahwa kamera tidak tersedia."
        )
        instructions += response_style_instruction(self.config)
        if knowledge_enabled:
            instructions += (
                "\nUntuk pertanyaan tentang produk, perusahaan, FAQ, manual, layanan, "
                "kebijakan, atau tentang kami, WAJIB panggil search_knowledge sebelum "
                "menjawab. Utamakan dokumen knowledge dan jangan mengarang detail."
            )
        tools = []
        if vision_enabled:
            tools.append(VISION_TOOL)
        if knowledge_enabled:
            tools.append(KNOWLEDGE_TOOL)
        await self._send({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.model,
                "output_modalities": ["audio"],
                "instructions": instructions,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": OPENAI_PCM_RATE},
                        # The built-in MacBook microphone is a far-field
                        # source; this is more resistant to room/speaker echo
                        # than the headset-oriented near_field profile.
                        "noise_reduction": {"type": "far_field"},
                        "transcription": {
                            "model": self.transcribe_model,
                            "language": "id",
                            "prompt": (
                                "Transkripsikan percakapan Bahasa Indonesia secara literal "
                                "dan natural. Kosakata umum mencakup: ngobrol, berbicara, "
                                "tentang, pesawat, teknologi, produk, berita, kamera. "
                                "Perintah singkat 'stop' harus ditulis tepat sebagai stop, "
                                "bukan top, tob, atau setop. "
                                "Pertahankan nama, merek, domain, URL, angka, dan kode persis "
                                "seperti yang diucapkan; jangan mengarang kata yang tidak jelas."
                            ),
                        },
                        # Local adaptive VAD owns turn boundaries. This avoids
                        # waiting once locally and then again for Semantic VAD.
                        "turn_detection": None,
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": OPENAI_PCM_RATE},
                        "voice": self.voice,
                    },
                },
                "tools": tools,
            },
        })
        updated = json.loads(await asyncio.wait_for(self._ws.recv(), timeout=15))
        if updated.get("type") == "error":
            raise RuntimeError(str(updated.get("error", updated)))
        if updated.get("type") != "session.updated":
            raise RuntimeError(f"Unexpected OpenAI event: {updated.get('type')}")
        self._connected = True
        self.logger.info("connected openai model=%s", self.model)

    async def disconnect(self) -> None:
        self._connected = False
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self.logger.info("disconnected openai")

    async def _send(self, event: dict[str, Any]) -> None:
        if self._ws is not None:
            await self._ws.send(json.dumps(event))

    async def send_audio(self, pcm: bytes) -> None:
        if self._ws is None:
            return
        if self.input_rate != OPENAI_PCM_RATE:
            pcm, self._in_resample_state = audioop.ratecv(
                pcm, 2, 1, self.input_rate, OPENAI_PCM_RATE, self._in_resample_state
            )
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm).decode("ascii"),
        })

    async def send_text(self, text: str) -> None:
        if self._ws is None:
            raise RuntimeError("OpenAI session is not connected")
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        })
        await self._send({"type": "response.create"})

    async def send_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> None:
        if self._ws is None:
            raise RuntimeError("OpenAI session is not connected")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{encoded}",
                }],
            },
        })

    async def send_tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("OpenAI session is not connected")
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": self._call_names.pop(call_id, call_id),
                "output": json.dumps(result),
            },
        })
        await self._send({"type": "response.create"})

    async def interrupt(self) -> None:
        if self._ws is None:
            return
        if self._response_active:
            await self._send({"type": "response.cancel"})

    async def end_turn(self) -> None:
        if self._ws is None:
            return
        if self._response_active:
            await self._send({"type": "response.cancel"})
        await self._send({"type": "input_audio_buffer.commit"})
        await self._send({"type": "response.create"})

    async def detect_interrupt_keyword(self, pcm: bytes, sample_rate: int) -> bool:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not pcm:
            return False
        wav_data = io.BytesIO()
        with wave.open(wav_data, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={
                        "model": "gpt-4o-mini-transcribe",
                        "language": "id",
                        "prompt": "Perintah interupsi: stop atau sebentar.",
                    },
                    files={"file": ("interrupt.wav", wav_data.getvalue(), "audio/wav")},
                )
            response.raise_for_status()
            text = str(response.json().get("text", "")).casefold()
            matched = "stop" in text or "sebentar" in text
            self.logger.info("keyword interrupt transcript=%r matched=%s", text, matched)
            return matched
        except Exception:
            self.logger.exception("keyword interrupt transcription failed")
            return False

    async def events(self) -> AsyncIterator[object]:
        yield AIConnected()
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                message = json.loads(raw)
                async for event in self._normalize(message):
                    yield event
        except Exception as exc:
            if self._connected:
                self.logger.exception("OpenAI receive failed")
                yield AIError(str(exc))

    async def _normalize(self, message: dict[str, Any]) -> AsyncIterator[object]:
        kind = message.get("type", "")
        if kind == "response.created":
            self._response_active = True
        elif kind == "conversation.item.input_audio_transcription.completed":
            self.logger.info("user transcript: %s", message.get("transcript", ""))
        elif kind in ("response.output_audio_transcript.delta", "response.audio_transcript.delta"):
            delta = message.get("delta", "")
            if delta:
                yield AITextDelta(delta)
        elif kind in ("response.output_audio.delta", "response.audio.delta"):
            delta = message.get("delta", "")
            if delta:
                if not self._speaking:
                    self._speaking = True
                    yield AISpeechStarted()
                yield AIAudioChunk(base64.b64decode(delta), self.output_rate)
        elif kind in ("response.done", "response.cancelled"):
            self._response_active = False
            if self._speaking:
                self._speaking = False
                yield AISpeechEnded()
        elif kind == "input_audio_buffer.speech_started" and self._speaking:
            self._speaking = False
            yield AISpeechEnded()
        elif kind == "response.function_call_arguments.done":
            call_id = message.get("call_id", "")
            name = message.get("name", "")
            try:
                arguments = json.loads(message.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            self._call_names[call_id] = call_id
            yield AIToolCall(call_id, name, arguments)
        elif kind == "error":
            detail = message.get("error", message)
            if isinstance(detail, dict) and detail.get("code") == "response_cancel_not_active":
                self.logger.debug("response already finished before cancellation")
                return
            self.logger.error("openai error event: %s", detail)
            yield AIError(str(detail))
