from src.config import get_config, get_error_logger
from src.fetcher import (
    fetch_mcp_page_content,
    get_bug_count,
    get_latest_changelog,
    get_project_properties,
    search_project_in_db,
)
from src.models import NotionResult, ParsedQuery, QueryIntent
from src.router.normalizer import normalize_properties


def _not_found_result() -> NotionResult:
    return NotionResult(None, None, None, False, None)


def _warn(message: str, **context: str | None) -> None:
    try:
        get_error_logger().warning(message, extra=context)
    except RuntimeError:
        pass


async def _resolve_project_page_id(project_name: str | None) -> tuple[str, str] | None:
    if not project_name:
        return None
    databases = get_config().notion.databases
    for db_id in (databases.mobile_team, databases.web_team, databases.backend_team):
        result = await search_project_in_db(project_name, db_id)
        if result:
            page_id = result.get("id")
            notion_url = result.get("url") or result.get("public_url")
            if page_id:
                return page_id, notion_url
    return None


async def _try_mcp_fallback(
    intent: QueryIntent,
    notion_url: str | None,
    page_hint: str,
) -> NotionResult:
    _warn(
        "API returned null, attempting MCP fallback",
        intent=intent.intent,
        project=intent.project_name,
        page_hint=page_hint,
    )
    result = await fetch_mcp_page_content(intent.project_name or "", page_hint)
    if result.data is not None:
        return result
    return NotionResult(None, "mcp", 3, False, notion_url)


async def _route_doc_link(
    project_name: str,
    page_id: str,
    notion_url: str | None,
) -> NotionResult:
    result = await get_project_properties(page_id)
    if result.data:
        normalized = normalize_properties(result.data)
        design_link = normalized.get("design_link")
        drive_link = normalized.get("drive_link")
        if design_link or drive_link:
            return NotionResult(
                {"design_link": design_link, "drive_link": drive_link},
                "api",
                2,
                result.from_cache,
                notion_url,
            )
    _warn("doc_link not found in API properties, falling back to MCP", project=project_name)
    return await fetch_mcp_page_content(project_name, "Design")


async def _route_intent(
    intent: QueryIntent,
    page_id: str,
    notion_url: str | None,
) -> NotionResult:
    match intent.intent:
        case "project_info" | "status_query":
            result = await get_project_properties(page_id)
            if result.data:
                result.data = normalize_properties(result.data)
                return result
            return await _try_mcp_fallback(intent, notion_url, "Overview")
        case "bug_query":
            result = await get_bug_count(page_id, environment=None)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, notion_url, "Bug List")
        case "bug_query_env":
            result = await get_bug_count(page_id, intent.environment)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, notion_url, "Bug List")
        case "version_query":
            result = await get_latest_changelog(page_id)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, notion_url, "Change Log")
        case "credential_query":
            return await fetch_mcp_page_content(intent.project_name or "", "Credentials")
        case "doc_link_query":
            return await _route_doc_link(intent.project_name or "", page_id, notion_url)
        case _:
            return _not_found_result()


async def route_query(parsed_query: ParsedQuery) -> list[tuple[QueryIntent, NotionResult]]:
    resolution_cache: dict[str, tuple[str, str] | None] = {}
    for question in parsed_query.questions:
        name = question.project_name
        if (
            question.intent == "unknown"
            or getattr(question, "is_ambiguous", False)
            or not name
        ):
            continue
        if name not in resolution_cache:
            resolution_cache[name] = await _resolve_project_page_id(name)

    results: list[tuple[QueryIntent, NotionResult]] = []
    for question in parsed_query.questions:
        if question.intent == "unknown" or getattr(question, "is_ambiguous", False):
            results.append((question, _not_found_result()))
            continue
        resolution = resolution_cache.get(question.project_name or "")
        if not resolution:
            _warn("Project not found in any team database", project=question.project_name)
            results.append((question, _not_found_result()))
            continue
        page_id, notion_url = resolution
        results.append((question, await _route_intent(question, page_id, notion_url)))
    return results
