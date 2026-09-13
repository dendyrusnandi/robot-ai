import asyncio

from core.event_bus import EventBus
from core.events import Event, EventType
from providers.factory import create_provider
from providers.mock_provider import MockRealtimeProvider


def test_event_bus_delivers_event() -> None:
    seen = []
    bus = EventBus()
    bus.subscribe(EventType.FACE_READY, lambda event: seen.append(event.type))
    asyncio.run(bus.publish(Event(EventType.FACE_READY)))
    assert seen == [EventType.FACE_READY]


def test_mock_provider_factory() -> None:
    provider = create_provider({"ai": {"provider": "mock"}})
    assert isinstance(provider, MockRealtimeProvider)

