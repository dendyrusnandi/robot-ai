from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from core.events import Event, EventType

EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """Small in-process async pub/sub bus with isolated handler failures."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._logger = logging.getLogger("EVENT")

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        handlers = tuple(self._handlers.get(event.type, ()))
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._invoke(handler, event) for handler in handlers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                self._logger.error("handler failed for %s", event.type, exc_info=result)

    async def _invoke(self, handler: EventHandler, event: Event) -> None:
        result = handler(event)
        if inspect.isawaitable(result):
            await result

