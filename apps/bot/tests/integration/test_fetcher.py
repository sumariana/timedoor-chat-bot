import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from src.config import loader as config_loader
from src.fetcher import notion_api
from src.fetcher.cache import CacheStore, get_cache


CONFIG = {
    "discord": {
        "allowed_channels": [],
        "denied_channels": [],
        "allow_dms": True,
        "dm_require_server_membership": True,
        "timedoor_server_id": "server-1",
    },
    "notion": {"databases": {"mobile_team": "m", "web_team": "w", "backend_team": "b"}},
    "session": {"max_history": 5, "timeout_minutes": 30},
    "cache": {
        "project_properties_ttl": 1800,
        "bug_counts_ttl": 300,
        "changelog_ttl": 900,
        "doc_links_ttl": 3600,
    },
    "llm": {"model": "gemini", "temperature": 0.2, "max_output_tokens": 1024},
    "rate_limit": {"max_queries_per_user_per_minute": 5},
}


@pytest.fixture
def configured(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-test")
    monkeypatch.setenv("NOTION_API_TOKEN", "notion-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    monkeypatch.setattr(config_loader, "_config", None)
    monkeypatch.setattr(notion_api, "_client", None)
    get_cache()._entries.clear()
    config_loader.load_config(str(path))


def prop(kind, value):
    return {"type": kind, kind: value}


@pytest.mark.asyncio
async def test_project_properties_are_mapped_and_cached(configured, monkeypatch):
    page = {
        "url": "https://notion.so/page-1",
        "properties": {
            "Name": prop("title", [{"plain_text": "Orange Care"}]),
            "Status": prop("select", {"name": "Active"}),
            "PM": prop("rich_text", [{"plain_text": "Cindy"}]),
            "Framework": prop("rich_text", [{"plain_text": "Flutter"}]),
            "Platform": prop("select", {"name": "iOS"}),
        },
    }
    client = SimpleNamespace(pages=SimpleNamespace(retrieve=AsyncMock(return_value=page)))
    monkeypatch.setattr(notion_api, "_client", client)

    first = await notion_api.get_project_properties("page-1")
    second = await notion_api.get_project_properties("page-1")

    assert first.data["name"] == "Orange Care"
    assert first.data["status"] == "Active"
    assert first.data["pm"] == "Cindy"
    assert first.notion_url == page["url"]
    assert second.from_cache is True
    client.pages.retrieve.assert_awaited_once_with(page_id="page-1")


@pytest.mark.asyncio
async def test_bug_count_applies_environment_and_uses_cache(configured, monkeypatch):
    children = AsyncMock(return_value={
        "results": [{"id": "bugs-db", "type": "child_database", "child_database": {"title": "Bug List"}}]
    })
    query = AsyncMock(return_value={
        "results": [
            {"properties": {"Status": prop("select", {"name": "Open"})}},
            {"properties": {"Status": prop("select", {"name": "In Progress"})}},
        ]
    })
    client = SimpleNamespace(
        blocks=SimpleNamespace(children=SimpleNamespace(list=children)),
        databases=SimpleNamespace(query=query),
    )
    monkeypatch.setattr(notion_api, "_client", client)

    result = await notion_api.get_bug_count("page-1", "staging_mobile")
    cached = await notion_api.get_bug_count("page-1", "staging_mobile")

    assert result.data == {
        "total": 2,
        "by_status": {"Open": 1, "In Progress": 1},
        "environment": "staging_mobile",
    }
    assert cached.from_cache is True
    query.assert_awaited_once()
    sent_filter = query.await_args.kwargs["filter"]
    assert sent_filter["and"][1] == {
        "property": "Environment",
        "select": {"equals": "staging_mobile"},
    }


@pytest.mark.asyncio
async def test_missing_child_database_returns_not_found(configured, monkeypatch):
    children = AsyncMock(return_value={"results": []})
    client = SimpleNamespace(blocks=SimpleNamespace(children=SimpleNamespace(list=children)))
    monkeypatch.setattr(notion_api, "_client", client)

    result = await notion_api.get_latest_changelog("page-1")

    assert result.data is None
    assert result.source == "api"
    assert result.tier == 2


@pytest.mark.asyncio
async def test_latest_changelog_maps_first_sorted_result(configured, monkeypatch):
    children = AsyncMock(return_value={
        "results": [{"id": "log-db", "type": "child_database", "child_database": {"title": "Change Log"}}]
    })
    query = AsyncMock(return_value={
        "results": [{"properties": {
            "Name": prop("title", [{"plain_text": "v1.2.0"}]),
            "Date": prop("date", {"start": "2026-09-25"}),
            "Notes": prop("rich_text", [{"plain_text": "Bug fixes"}]),
        }}]
    })
    client = SimpleNamespace(
        blocks=SimpleNamespace(children=SimpleNamespace(list=children)),
        databases=SimpleNamespace(query=query),
    )
    monkeypatch.setattr(notion_api, "_client", client)

    result = await notion_api.get_latest_changelog("page-1")

    assert result.data == {"version": "v1.2.0", "date": "2026-09-25", "notes": "Bug fixes"}
    assert query.await_args.kwargs["sorts"] == [{"property": "Date", "direction": "descending"}]


def test_cache_returns_value_until_ttl_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    cache = CacheStore()

    cache.set("project_props:page-1", {"name": "Demo"}, ttl=10)
    assert cache.get("project_props:page-1") == {"name": "Demo"}

    now[0] = 110.0
    assert cache.get("project_props:page-1") is None


def test_cache_invalidate_is_idempotent():
    cache = CacheStore()
    cache.set("bug_count:page-1", {"total": 1}, ttl=60)

    cache.invalidate("bug_count:page-1")
    cache.invalidate("missing")

    assert cache.get("bug_count:page-1") is None
