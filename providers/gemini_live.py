from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from core.events import (
    AIAudioChunk, AIConnected, AIError, AIInterrupted, AISpeechEnded,
    AISpeechStarted, AITextDelta, AIToolCall,
)
from core.response_style import response_style_instruction
from providers.base import RealtimeAIProvider

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
Your audio is played directly through the robot speaker. Never mention internal APIs.
If you cannot hear clearly, ask the user to repeat. Do not invent visual information.
Bedakan ucapan pengguna yang ditujukan kepadamu dari televisi, musik, percakapan orang
lain, dan suara latar. Abaikan ucapan yang jelas bukan ditujukan kepadamu. Dalam keadaan
ramai atau ketika tujuan ucapan ambigu, hanya tanggapi jika pengguna memanggil "RN".
Dalam keadaan tenang, pengguna tetap boleh berbicara langsung tanpa kata panggil.
Nama domain, URL, merek, nama orang, dan kode harus dipertahankan persis seperti yang
terdengar. Jangan mengganti atau mengarang nama yang mirip. Jika ejaan kurang yakin,
ucapkan kembali nama yang kamu dengar lalu minta konfirmasi sebelum melanjutkan. Kamu
tidak memiliki akses browsing web langsung kecuali tersedia tool web khusus dalam sesi.
Jangan mengaku sudah membuka atau memeriksa situs jika tool tersebut tidak tersedia.
Jika pengguna bertanya tentang apa yang terlihat, ada siapa atau benda apa di depan,
warna, jumlah orang, atau keadaan sekitar saat ini, WAJIB panggil tool look_at_camera.
Jangan pernah menebak isi kamera tanpa snapshot terbaru.
"""

VISION_TOOL = types.Tool(function_declarations=[types.FunctionDeclaration(
    name="look_at_camera",
    description="Observe the current scene from the robot's front camera before answering a visual question.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "question": {
                "type": "STRING",
                "description": "What should be examined in the current camera image?",
            }
        },
        "required": ["question"],
    },
)])

KNOWLEDGE_TOOL = types.Tool(function_declarations=[types.FunctionDeclaration(
    name="search_knowledge",
    description="Search approved local company, product, FAQ, about-us, and manual documents before answering.",
    parameters={
        "type": "OBJECT",
        "properties": {"query": {"type": "STRING", "description": "The user's product or company question."}},
        "required": ["query"],
    },
)])


class GeminiLiveProvider(RealtimeAIProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model = config["providers"]["gemini"]["model"]
        self.input_rate = int(config["audio"]["input_sample_rate"])
        self.output_rate = int(config["audio"].get("output_sample_rate", 24000))
        self.client: genai.Client | None = None
        self.session = None
        self._connection = None
        self._connected = False
        self._speaking = False
        self._call_names: dict[str, str] = {}
        self.logger = logging.getLogger("AI")

    async def connect(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=api_key)
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
        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            speech_config=types.SpeechConfig(),
            system_instruction=instructions,
            tools=tools,
        )
        self._connection = self.client.aio.live.connect(model=self.model, config=live_config)
        self.session = await self._connection.__aenter__()
        self._connected = True
        self.logger.info("connected gemini model=%s", self.model)

    async def disconnect(self) -> None:
        self._connected = False
        if self.session is not None:
            await self.session.close()
            self.session = None
        if self._connection is not None:
            await self._connection.__aexit__(None, None, None)
            self._connection = None
        self.client = None
        self.logger.info("disconnected gemini")

    async def send_audio(self, pcm: bytes) -> None:
        if self.session is not None:
            await self.session.send_realtime_input(
                audio=types.Blob(data=pcm, mime_type=f"audio/pcm;rate={self.input_rate}")
            )

    async def send_text(self, text: str) -> None:
        if self.session is None:
            raise RuntimeError("Gemini session is not connected")
        await self.session.send_realtime_input(text=text)

    async def send_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> None:
        if self.session is None:
            raise RuntimeError("Gemini session is not connected")
        await self.session.send_realtime_input(video=types.Blob(data=image_bytes, mime_type=mime_type))

    async def send_tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        if self.session is None:
            raise RuntimeError("Gemini session is not connected")
        await self.session.send_tool_response(
            function_responses=types.FunctionResponse(
                id=call_id,
                name=self._call_names.pop(call_id, "look_at_camera"),
                response=result,
            )
        )

    async def interrupt(self) -> None:
        if self.session is not None:
            await self.session.send_realtime_input(audio_stream_end=True)

    async def end_turn(self) -> None:
        if self.session is not None:
            await self.session.send_realtime_input(audio_stream_end=True)

    async def events(self) -> AsyncIterator[object]:
        yield AIConnected()
        while self._connected and self.session is not None:
            try:
                async for message in self.session.receive():
                    async for event in self._normalize(message):
                        yield event
            except Exception as exc:
                if self._connected:
                    self.logger.exception("Gemini receive failed")
                    yield AIError(str(exc))
                break

    async def _normalize(self, message) -> AsyncIterator[object]:
        content = message.server_content
        if content is not None:
            if content.interrupted:
                self._speaking = False
                yield AIInterrupted()
            if content.input_transcription and content.input_transcription.text:
                self.logger.info("user transcript: %s", content.input_transcription.text)
            if content.output_transcription and content.output_transcription.text:
                yield AITextDelta(content.output_transcription.text)
            if content.model_turn:
                for part in content.model_turn.parts or []:
                    inline = part.inline_data
                    if inline and inline.data:
                        if not self._speaking:
                            self._speaking = True
                            yield AISpeechStarted()
                        yield AIAudioChunk(bytes(inline.data), self.output_rate)
            if content.turn_complete and self._speaking:
                self._speaking = False
                yield AISpeechEnded()
        if message.tool_call:
            for call in message.tool_call.function_calls or []:
                self._call_names[call.id or ""] = call.name or ""
                yield AIToolCall(call.id or "", call.name or "", dict(call.args or {}))
