from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class RealtimeAIProvider(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_audio(self, pcm: bytes) -> None: ...

    @abstractmethod
    async def send_text(self, text: str) -> None: ...

    @abstractmethod
    async def send_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> None: ...

    @abstractmethod
    async def send_tool_result(self, call_id: str, result: dict[str, Any]) -> None: ...

    @abstractmethod
    async def interrupt(self) -> None: ...

    @abstractmethod
    async def end_turn(self) -> None: ...

    async def detect_interrupt_keyword(self, pcm: bytes, sample_rate: int) -> bool:
        del pcm, sample_rate
        return False

    @abstractmethod
    def events(self) -> AsyncIterator[object]: ...
