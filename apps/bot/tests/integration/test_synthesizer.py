from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models import BotResponse, NotionResult, QueryIntent
import src.synthesizer as synthesizer
from src.synthesizer import gemini
from src.synthesizer import synthesize_response


def intent(kind="project_info", language="en", project="Orange Care", **kwargs):
    return QueryIntent(kind, project, None, language, "What is the status?", **kwargs)


def result(data=None, source="api", tier=1, url=None):
    return NotionResult(data, source, tier, False, url)


@pytest.fixture(autouse=True)
def reset_llm(monkeypatch):
    monkeypatch.setattr(gemini, "_llm", None)


@pytest.mark.asyncio
async def test_standard_query_uses_gemini(monkeypatch):
    call = AsyncMock(return_value="Orange Care is active.")
    monkeypatch.setattr(synthesizer, "call_gemini", call)

    response = await synthesize_response([(intent(), result({"status": "Active"}))], [])

    assert response == BotResponse("Orange Care is active.", "en")
    call.assert_awaited_once()


@pytest.mark.asyncio
async def test_multiple_standard_queries_batch_one_call(monkeypatch):
    call = AsyncMock(return_value="1. Active\n2. 3 open bugs")
    monkeypatch.setattr(synthesizer, "call_gemini", call)

    response = await synthesize_response(
        [(intent(), result({"status": "Active"})), (intent("bug_query"), result({"total": 3}))],
        [],
    )

    assert "Active" in response.content
    assert "3 open bugs" in response.content
    call.assert_awaited_once()


@pytest.mark.asyncio
async def test_credentials_extract_without_synthesis(monkeypatch):
    extract = AsyncMock(return_value={"server_host": "api.x.com", "environment": "Production"})
    synthesis = AsyncMock()
    monkeypatch.setattr(synthesizer, "call_gemini_extract_credentials", extract)
    monkeypatch.setattr(synthesizer, "call_gemini", synthesis)

    response = await synthesize_response(
        [(intent("credential_query"), result({"content": "password=SECRET"}, "mcp", 3, "notion-url"))], []
    )

    assert "api.x.com" in response.content
    assert "SECRET" not in response.content
    assert response.is_credential is True
    synthesis.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_data_uses_template_without_gemini(monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr(synthesizer, "call_gemini", call)

    response = await synthesize_response([(intent(), result())], [])

    assert "no data found" in response.content
    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguity_and_reset_use_templates(monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr(synthesizer, "call_gemini", call)
    ambiguous = intent(is_ambiguous=True, candidates=["Orange Care", "Orange Cafe"])
    reset = intent("session_reset", project=None)

    response = await synthesize_response([(ambiguous, result()), (reset, result())], [])

    assert "Orange Care" in response.content
    assert "reset" in response.content.lower()
    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_gemini_failure_returns_error(monkeypatch):
    monkeypatch.setattr(synthesizer, "call_gemini", AsyncMock(side_effect=RuntimeError("offline")))

    response = await synthesize_response([(intent(), result({"status": "Active"}))], [])

    assert response.is_error is True
    assert "error" in response.content.lower()


def test_indonesian_prompt_has_language_and_guardrail():
    from src.synthesizer.prompt import build_system_prompt

    prompt = build_system_prompt("id")
    assert "Indonesian (Bahasa Indonesia)" in prompt
    assert "Do NOT guess" in prompt
