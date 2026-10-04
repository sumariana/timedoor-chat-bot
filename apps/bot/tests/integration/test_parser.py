from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models import QueryIntent
from src.parser import parse_message
from src.parser import matcher, session
from src.parser.classifier import classify_message


@pytest.fixture(autouse=True)
def reset_parser_state(monkeypatch):
    session.get_session_store()._sessions.clear()
    monkeypatch.setattr(matcher, "_registry", [])


def configure(monkeypatch, max_history=2, timeout_minutes=30):
    monkeypatch.setattr(
        session,
        "get_config",
        lambda: SimpleNamespace(session=SimpleNamespace(max_history=max_history, timeout_minutes=timeout_minutes)),
    )


def test_session_store_limits_history_and_remembers_project(monkeypatch):
    configure(monkeypatch, max_history=2)
    store = session.SessionStore()
    key = store.make_key(1, 2)

    store.add_exchange(key, "one", "answer one")
    store.add_exchange(key, "two", "answer two")
    store.add_exchange(key, "three", "answer three")
    store.update_last_project(key, "Orange Care")

    assert [item.content for item in store.get_history(key)] == [
        "two", "answer two", "three", "answer three"
    ]
    assert store.get_last_project(key) == "Orange Care"


def test_fuzzy_match_returns_match_or_ambiguity(monkeypatch):
    monkeypatch.setattr(matcher, "_registry", ["Orange Care", "Orange Cafe"])

    matched, candidates = matcher.fuzzy_match_project("Orange Care")
    assert matched == "Orange Care"
    assert candidates == []

    matched, candidates = matcher.fuzzy_match_project("Orange C")
    assert matched is None
    assert set(candidates) == {"Orange Care", "Orange Cafe"}


@pytest.mark.asyncio
async def test_parse_message_matches_project_and_inherits_context(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(matcher, "_registry", ["Orange Care"])
    monkeypatch.setattr(
        "src.parser.classify_message",
        AsyncMock(
            side_effect=[
                ("en", [{"intent": "project_info", "project_name": "Orange Car", "environment": None, "raw_question": "info"}]),
                ("en", [{"intent": "status_query", "project_name": None, "environment": None, "raw_question": "status?"}]),
            ]
        ),
    )

    first = await parse_message("info", 1, 2)
    session.get_session_store().update_last_project(first.session_key, first.questions[0].project_name)
    second = await parse_message("status?", 1, 2)

    assert first.questions[0].project_name == "Orange Care"
    assert second.questions[0].project_name == "Orange Care"


@pytest.mark.asyncio
async def test_classifier_falls_back_to_unknown(monkeypatch):
    monkeypatch.setattr("src.parser.classifier.get_config", lambda: SimpleNamespace(llm=SimpleNamespace(
        api_key="key", model="gemini", temperature=0.2, max_output_tokens=100
    )))
    monkeypatch.setattr("src.parser.classifier.genai.configure", lambda **kwargs: None)
    model = SimpleNamespace(generate_content_async=AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("src.parser.classifier.genai.GenerativeModel", lambda _: model)

    language, questions = await classify_message("berapa bug?", [])

    assert language == "id"
    assert questions[0]["intent"] == "unknown"
    assert questions[0]["raw_question"] == "berapa bug?"
