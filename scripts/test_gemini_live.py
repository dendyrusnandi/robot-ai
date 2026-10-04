from __future__ import annotations

import asyncio
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.events import AIAudioChunk, AISpeechEnded
from providers.gemini_live import GeminiLiveProvider

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    load_dotenv(ROOT / ".env")
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    provider = GeminiLiveProvider(config)
    audio_bytes = 0
    try:
        await provider.connect()
        print("Gemini Live: CONNECTED")
        await provider.send_text("Jawab singkat dalam Bahasa Indonesia: tes koneksi berhasil.")
        async for event in provider.events():
            if isinstance(event, AIAudioChunk):
                audio_bytes += len(event.pcm)
            elif isinstance(event, AISpeechEnded):
                break
        print(f"Gemini audio received: {audio_bytes} bytes")
        if audio_bytes == 0:
            raise RuntimeError("No response audio received")
    finally:
        await provider.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
