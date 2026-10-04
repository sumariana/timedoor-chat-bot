import time
from typing import Any

from notion_client import AsyncClient

from src.config import get_config, get_error_logger, get_latency_logger
from src.fetcher.cache import get_cache
from src.models import NotionResult

_client: AsyncClient | None = None

_ACTIVE_STATUSES = ("Open", "In progress", "Re-Opened", "Re-Test")


def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(auth=get_config().notion.api_token)
    return _client


def _plain_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = value.get("type")
    payload = value.get(kind, {}) if kind else {}
    if kind in {"title", "rich_text"}:
        return "".join(item.get("plain_text", "") for item in payload).strip()
    if kind == "select":
        return (payload or {}).get("name")
    if kind == "multi_select":
        return [item.get("name") for item in payload]
    if kind == "date":
        return (payload or {}).get("start")
    if kind == "url":
        return payload
    if kind == "checkbox":
        return payload
    return value


def _property(properties: dict, *names: str) -> Any:
    wanted = {name.casefold() for name in names}
    for name, value in properties.items():
        if name.casefold() in wanted:
            return _plain_value(value)
    return None


def _page_url(page: dict) -> str | None:
    return page.get("url") or page.get("public_url")


def _latency(operation: str, tier: int, started: float, from_cache: bool) -> None:
    try:
        get_latency_logger().info(
            operation,
            extra={
                "module": "fetcher",
                "operation": operation,
                "source": "api",
                "tier": tier,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "from_cache": from_cache,
            },
        )
    except RuntimeError:
        pass


def _error(operation: str, error: Exception) -> None:
    try:
        get_error_logger().error("%s failed: %s", operation, error, extra={"module": "fetcher"})
    except RuntimeError:
        pass


async def search_project_in_db(project_name: str, db_id: str) -> dict | None:
    response = await _get_client().databases.query(
        database_id=db_id,
        filter={"property": "Name", "title": {"contains": project_name}},
        page_size=1,
    )
    results = response.get("results", [])
    return results[0] if results else None


async def get_project_properties(page_id: str) -> NotionResult:
    started = time.perf_counter()
    key = f"project_props:{page_id}"
    cached = get_cache().get(key)
    if cached is not None:
        _latency("get_project_properties", 1, started, True)
        return NotionResult(cached["data"], "api", 1, True, cached["notion_url"])
    try:
        page = await _get_client().pages.retrieve(page_id=page_id)
        props = page.get("properties", {})
        data = {
            "name": _property(props, "Name", "Project Name"),
            "status": _property(props, "Status", "Project Status", "State"),
            "platform": _property(props, "Platform"),
            "category": _property(props, "Category"),
            "pm": _property(props, "PM", "Project Manager"),
            "framework": _property(props, "Framework"),
            "tech_stack": _property(props, "Tech Stack", "Stack"),
            "language": _property(props, "Language"),
            "dates": _property(props, "Dates", "Date"),
            "app_store_urls": _property(props, "App Store URLs", "App Store URL"),
            "firebase_status": _property(props, "Firebase Status", "Firebase"),
            "sentry": _property(props, "Sentry", "Sentry Status"),
            "maintenance_status": _property(props, "Maintenance Status", "Maintenance"),
        }
        url = _page_url(page)
        get_cache().set(key, {"data": data, "notion_url": url}, get_config().cache.project_properties_ttl)
        _latency("get_project_properties", 1, started, False)
        return NotionResult(data, "api", 1, False, url)
    except Exception as exc:
        _error("get_project_properties", exc)
        _latency("get_project_properties", 1, started, False)
        return NotionResult(None, "api", 1, False, None)


async def _find_child_database(page_id: str, name_hint: str) -> str | None:
    response = await _get_client().blocks.children.list(block_id=page_id)
    hint = name_hint.casefold()
    for block in response.get("results", []):
        if block.get("type") != "child_database":
            continue
        child = block.get("child_database", {})
        if hint in child.get("title", "").casefold():
            return block.get("id")
    return None


async def get_bug_count(page_id: str, environment: str | None) -> NotionResult:
    started = time.perf_counter()
    key = f"bug_count:{page_id}" if environment is None else f"bug_count:{page_id}:{environment}"
    cached = get_cache().get(key)
    if cached is not None:
        _latency("get_bug_count", 2, started, True)
        return NotionResult(cached, "api", 2, True, None)
    try:
        database_id = await _find_child_database(page_id, "Bug List")
        if not database_id:
            return NotionResult(None, "api", 2, False, None)
        filters: list[dict] = [{"or": [{"property": "Status", "status": {"equals": status}} for status in _ACTIVE_STATUSES]}]
        if environment:
            filters.append({"property": "Environment", "select": {"equals": environment}})
        query_filter = filters[0] if len(filters) == 1 else {"and": filters}
        response = await _get_client().databases.query(database_id=database_id, filter=query_filter)
        by_status: dict[str, int] = {}
        for bug in response.get("results", []):
            status = _property(bug.get("properties", {}), "Status") or "Unknown"
            by_status[status] = by_status.get(status, 0) + 1
        data = {"total": sum(by_status.values()), "by_status": by_status, "environment": environment}
        get_cache().set(key, data, get_config().cache.bug_counts_ttl)
        _latency("get_bug_count", 2, started, False)
        return NotionResult(data, "api", 2, False, None)
    except Exception as exc:
        _error("get_bug_count", exc)
        _latency("get_bug_count", 2, started, False)
        return NotionResult(None, "api", 2, False, None)


async def get_latest_changelog(page_id: str) -> NotionResult:
    started = time.perf_counter()
    key = f"changelog:{page_id}"
    cached = get_cache().get(key)
    if cached is not None:
        _latency("get_latest_changelog", 2, started, True)
        return NotionResult(cached, "api", 2, True, None)
    try:
        database_id = await _find_child_database(page_id, "Change Log")
        if not database_id:
            return NotionResult(None, "api", 2, False, None)
        response = await _get_client().databases.query(
            database_id=database_id,
            sorts=[{"property": "Date", "direction": "descending"}],
            page_size=1,
        )
        if not response.get("results"):
            return NotionResult(None, "api", 2, False, None)
        props = response["results"][0].get("properties", {})
        data = {
            "version": _property(props, "Version", "Name"),
            "date": _property(props, "Date", "Release Date"),
            "notes": _property(props, "Notes", "Description"),
        }
        get_cache().set(key, data, get_config().cache.changelog_ttl)
        _latency("get_latest_changelog", 2, started, False)
        return NotionResult(data, "api", 2, False, None)
    except Exception as exc:
        _error("get_latest_changelog", exc)
        _latency("get_latest_changelog", 2, started, False)
        return NotionResult(None, "api", 2, False, None)


async def list_all_project_names() -> list[str]:
    names: list[str] = []
    databases = get_config().notion.databases
    for database_id in (databases.mobile_team, databases.web_team, databases.backend_team):
        try:
            cursor = None
            while True:
                kwargs = {"database_id": database_id, "page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                response = await _get_client().databases.query(**kwargs)
                for page in response.get("results", []):
                    name = _property(page.get("properties", {}), "Name", "Project Name")
                    if name:
                        names.append(name)
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")
        except Exception as exc:
            _error("list_all_project_names", exc)
    return names
