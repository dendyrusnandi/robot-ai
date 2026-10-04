from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from core.events import AIConnected, AITextDelta
from providers.base import RealtimeAIProvider


class MockRealtimeProvider(RealtimeAIProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize=32)
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        await self._queue.put(AIConnected())

    async def disconnect(self) -> None:
        self._connected = False

    async def send_audio(self, pcm: bytes) -> None:
        del pcm

    async def send_text(self, text: str) -> None:
        await self._queue.put(AITextDelta(f"Mock menerima: {text}"))

    async def send_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> None:
        del image_bytes, mime_type

    async def send_tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        del call_id, result

    async def interrupt(self) -> None:
        return None

    async def end_turn(self) -> None:
        return None

    async def events(self) -> AsyncIterator[object]:
        while self._connected:
            yield await self._queue.get()
