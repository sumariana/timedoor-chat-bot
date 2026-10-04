from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from src.gateway import client
from src.gateway import filters, formatters
from src.gateway.rate_limiter import RateLimiter
from src.models import BotResponse, NotionResult, ParsedQuery, QueryIntent


class FakeChannel:
    id = 10

    @asynccontextmanager
    async def typing(self):
        yield


class FakeUser:
    id = 7


class FakeMessage:
    def __init__(self, author, content="@bot status", mentions=None, channel=None):
        self.author = author
        self.content = content
        self.mentions = mentions or []
        self.channel = channel or FakeChannel()
        self.reply = AsyncMock()


@pytest.fixture
def configured(monkeypatch):
    config = SimpleNamespace(
        discord=SimpleNamespace(
            allowed_channels=[], denied_channels=[], allow_dms=True, timedoor_server_id="1"
        ),
        rate_limit=SimpleNamespace(max_queries_per_user_per_minute=5),
    )
    monkeypatch.setattr(client, "get_config", lambda: config)
    monkeypatch.setattr(filters, "get_config", lambda: config)
    return config


def parsed():
    return ParsedQuery([QueryIntent("project_info", "Orange Care", None, "en", "status")], "s", 7, 10)


def patch_pipeline(monkeypatch, response=None):
    monkeypatch.setattr(client, "parse_message", AsyncMock(return_value=parsed()))
    monkeypatch.setattr(client, "route_query", AsyncMock(return_value=[(parsed().questions[0], NotionResult({"status": "Active"}, "api", 1, False, None))]))
    monkeypatch.setattr(client, "synthesize_response", AsyncMock(return_value=response or BotResponse("Active", "en")))
    monkeypatch.setattr(client, "add_to_session", lambda **kwargs: None)
    monkeypatch.setattr(client, "update_session_project", lambda **kwargs: None)
    monkeypatch.setattr(client, "get_latency_logger", lambda: SimpleNamespace(info=lambda *a, **k: None))
    monkeypatch.setattr(client, "get_error_logger", lambda: SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None))


@pytest.mark.asyncio
async def test_own_message_ignored(configured, monkeypatch):
    bot = SimpleNamespace(user=object())
    message = FakeMessage(bot.user)
    parse = AsyncMock()
    monkeypatch.setattr(client, "parse_message", parse)

    await client._handle_message(message, bot)

    parse.assert_not_awaited()
    message.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_unmentioned_channel_ignored(configured, monkeypatch):
    bot = SimpleNamespace(user=object())
    message = FakeMessage(FakeUser(), mentions=[])
    parse = AsyncMock()
    monkeypatch.setattr(client, "parse_message", parse)

    await client._handle_message(message, bot)

    parse.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowed_channel_runs_pipeline(configured, monkeypatch):
    bot = SimpleNamespace(user=object())
    message = FakeMessage(FakeUser(), mentions=[bot.user])
    patch_pipeline(monkeypatch)
    monkeypatch.setattr(client, "get_rate_limiter", lambda: SimpleNamespace(is_allowed=lambda _: True))

    await client._handle_message(message, bot)

    client.parse_message.assert_awaited_once()
    message.reply.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_limited_message_rejected(configured, monkeypatch):
    bot = SimpleNamespace(user=object())
    message = FakeMessage(FakeUser(), mentions=[bot.user])
    parse = AsyncMock()
    monkeypatch.setattr(client, "parse_message", parse)
    monkeypatch.setattr(client, "get_rate_limiter", lambda: SimpleNamespace(is_allowed=lambda _: False))

    await client._handle_message(message, bot)

    parse.assert_not_awaited()
    message.reply.assert_awaited_once()
    assert message.reply.call_args.kwargs["embed"].colour == formatters.COLOUR_ERROR


@pytest.mark.asyncio
async def test_nonmember_dm_rejected(configured, monkeypatch):
    bot = SimpleNamespace(user=object())
    message = FakeMessage(FakeUser(), channel=discord.DMChannel.__new__(discord.DMChannel))
    monkeypatch.setattr(client, "is_timedoor_member", AsyncMock(return_value=False))
    parse = AsyncMock()
    monkeypatch.setattr(client, "parse_message", parse)

    await client._handle_message(message, bot)

    parse.assert_not_awaited()
    message.reply.assert_awaited_once()


def test_rate_limiter_enforces_configured_limit(monkeypatch):
    monkeypatch.setattr("src.gateway.rate_limiter.get_config", lambda: SimpleNamespace(rate_limit=SimpleNamespace(max_queries_per_user_per_minute=2)))
    limiter = RateLimiter()

    assert limiter.is_allowed(7)
    assert limiter.is_allowed(7)
    assert not limiter.is_allowed(7)


def test_embed_colours_and_truncates():
    error = formatters.build_embed(BotResponse("x", "en", is_error=True))
    credential = formatters.build_embed(BotResponse("x", "en", is_credential=True))
    success = formatters.build_embed(BotResponse("x", "en"), "Orange Care")
    long = formatters.build_embed(BotResponse("x" * 5000, "en"))

    assert error.colour == formatters.COLOUR_ERROR
    assert credential.colour == formatters.COLOUR_CREDENTIAL
    assert success.colour == formatters.COLOUR_SUCCESS
    assert len(long.description) == 4096
