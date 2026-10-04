import asyncio
from pathlib import Path

from core.event_bus import EventBus
from core.events import Event, EventType
from providers.factory import create_provider
from providers.mock_provider import MockRealtimeProvider
from knowledge.store import KnowledgeStore
from cli import INSTRUCTIONS, extract_output_text


def test_event_bus_delivers_event() -> None:
    seen = []
    bus = EventBus()
    bus.subscribe(EventType.FACE_READY, lambda event: seen.append(event.type))
    asyncio.run(bus.publish(Event(EventType.FACE_READY)))
    assert seen == [EventType.FACE_READY]


def test_mock_provider_factory() -> None:
    provider = create_provider({"ai": {"provider": "mock"}})
    assert isinstance(provider, MockRealtimeProvider)


def test_remote_vector_store_initializes_without_local_documents(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store = KnowledgeStore(Path("."), {
        "knowledge": {
            "enabled": True,
            "vector_store_id": "vs_6ab3cab661708191be05af2341a70785",
        }
    })

    assert asyncio.run(store.initialize()) is True
    assert store.enabled is True


def test_cli_extracts_text_response() -> None:
    response = {
        "output": [
            {"type": "file_search_call", "status": "completed"},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Jawaban dari knowledge."}
                ],
            },
        ]
    }

    assert extract_output_text(response) == "Jawaban dari knowledge."


def test_cli_instructions_fall_back_to_general_knowledge_without_permission() -> None:
    assert "langsung jawab" in INSTRUCTIONS
    assert "pengetahuan umum model" in INSTRUCTIONS
    assert "jangan meminta izin" in INSTRUCTIONS
