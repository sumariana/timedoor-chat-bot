from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models import NotionResult, ParsedQuery, QueryIntent
from src.router import router
from src.router.normalizer import normalize_properties


@pytest.fixture
def config(monkeypatch):
    value = SimpleNamespace(
        notion=SimpleNamespace(
            databases=SimpleNamespace(mobile_team="mobile", web_team="web", backend_team="backend")
        )
    )
    monkeypatch.setattr(router, "get_config", lambda: value)
    return value


def intent(kind, project="Orange Care", environment=None):
    return QueryIntent(kind, project, environment, "en", "question")


@pytest.mark.asyncio
async def test_project_info_routes_to_api(config, monkeypatch):
    search = AsyncMock(return_value={"id": "page-1", "url": "https://notion/page-1"})
    fetch = AsyncMock(return_value=NotionResult({"Tech Stack": "Flutter"}, "api", 1, False, "url"))
    monkeypatch.setattr(router, "search_project_in_db", search)
    monkeypatch.setattr(router, "get_project_properties", fetch)

    result = await router.route_query(ParsedQuery([intent("project_info")], "s", 1, 1))

    assert result[0][1].data == {"framework": "Flutter"}
    fetch.assert_awaited_once_with("page-1")
    search.assert_awaited_once_with("Orange Care", "mobile")


@pytest.mark.asyncio
async def test_bug_query_api_miss_uses_mcp_fallback(config, monkeypatch):
    monkeypatch.setattr(
        router,
        "search_project_in_db",
        AsyncMock(return_value={"id": "page-1", "url": "page-url"}),
    )
    monkeypatch.setattr(
        router,
        "get_bug_count",
        AsyncMock(return_value=NotionResult(None, "api", 2, False, None)),
    )
    mcp = AsyncMock(return_value=NotionResult({"content": "bugs"}, "mcp", 3, False, "mcp-url"))
    monkeypatch.setattr(router, "fetch_mcp_page_content", mcp)

    result = await router.route_query(ParsedQuery([intent("bug_query")], "s", 1, 1))

    assert result[0][1].data == {"content": "bugs"}
    mcp.assert_awaited_once_with("Orange Care", "Bug List")


@pytest.mark.asyncio
async def test_unknown_skips_fetchers(config, monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(router, "search_project_in_db", search)

    result = await router.route_query(ParsedQuery([intent("unknown")], "s", 1, 1))

    assert result[0][1].data is None
    assert result[0][1].source is None
    search.assert_not_awaited()


def test_normalizer_maps_aliases_and_drops_unknown_fields():
    assert normalize_properties({"Tech Stack": "Flutter", "Figma": "https://figma", "Other": "x"}) == {
        "framework": "Flutter",
        "design_link": "https://figma",
    }
