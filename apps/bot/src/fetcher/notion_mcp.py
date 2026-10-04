import time
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config import get_config, get_error_logger, get_latency_logger
from src.fetcher.cache import get_cache
from src.models import NotionResult


class NotionMCPClient:
    _instance: "NotionMCPClient | None" = None

    def __init__(self) -> None:
        self._client: MultiServerMCPClient | None = None
        self._tools: dict[str, Any] = {}

    @classmethod
    async def get_instance(cls) -> "NotionMCPClient":
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._connect()
        return cls._instance

    async def _connect(self) -> None:
        self._client = MultiServerMCPClient({
            "notion": {
                "command": "notion-mcp-server",
                "args": [],
                "env": {"NOTION_API_TOKEN": get_config().notion.api_token},
                "transport": "stdio",
            }
        })
        tools = await self._client.get_tools()
        self._tools = {tool.name: tool for tool in tools}

    async def _invoke(self, names: tuple[str, ...], payload: dict) -> Any:
        for name in names:
            if name in self._tools:
                return await self._tools[name].ainvoke(payload)
        raise KeyError(f"MCP tool not found: {names[0]}")

    async def search_workspace(self, query: str) -> list[dict]:
        result = await self._invoke(("notion_search", "search"), {"query": query})
        return result if isinstance(result, list) else result.get("results", [])

    async def get_page_content(self, page_id: str) -> dict | None:
        result = await self._invoke(("notion_get_page", "get_page"), {"page_id": page_id})
        return result if isinstance(result, dict) else None

    async def list_child_pages(self, parent_page_id: str) -> list[dict]:
        result = await self._invoke(("notion_list_children", "list_children"), {"block_id": parent_page_id})
        blocks = result if isinstance(result, list) else result.get("results", [])
        return [block for block in blocks if block.get("type") == "child_page"]


async def fetch_mcp_page_content(project_name: str, page_hint: str) -> NotionResult:
    started = time.perf_counter()
    is_credential = page_hint.casefold() == "credentials"
    key = f"doc_links:{project_name}:{page_hint}" if not is_credential else ""
    if key:
        cached = get_cache().get(key)
        if cached is not None:
            _log_latency(started, True)
            return NotionResult(cached["data"], "mcp", 3, True, cached["notion_url"])
    try:
        client = await NotionMCPClient.get_instance()
        matches = await client.search_workspace(project_name)
        if not matches:
            return NotionResult(None, "mcp", 3, False, None)
        project = matches[0]
        project_id = project.get("id")
        children = await client.list_child_pages(project_id)
        hint = page_hint.casefold()
        child = next((item for item in children if hint in _title(item).casefold()), None)
        if child is None:
            return NotionResult(None, "mcp", 3, False, None)
        page = await client.get_page_content(child.get("id"))
        if page is None:
            return NotionResult(None, "mcp", 3, False, None)
        url = page.get("url") or child.get("url") or project.get("url")
        data = {"content": _content(page), "notion_url": url}
        if key:
            get_cache().set(key, {"data": data, "notion_url": url}, get_config().cache.doc_links_ttl)
        _log_latency(started, False)
        return NotionResult(data, "mcp", 3, False, url)
    except Exception as exc:
        try:
            get_error_logger().error("fetch_mcp_page_content failed: %s", exc, extra={"module": "fetcher"})
        except RuntimeError:
            pass
        _log_latency(started, False)
        return NotionResult(None, "mcp", 3, False, None)


def _title(item: dict) -> str:
    title = item.get("child_page", {}).get("title") or item.get("title")
    return title if isinstance(title, str) else ""


def _content(page: dict) -> str:
    content = page.get("content") or page.get("text")
    if isinstance(content, str):
        return content
    return str(content if content is not None else page)


def _log_latency(started: float, from_cache: bool) -> None:
    try:
        get_latency_logger().info(
            "fetch_mcp_page_content",
            extra={
                "module": "fetcher",
                "operation": "fetch_mcp_page_content",
                "source": "mcp",
                "tier": 3,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "from_cache": from_cache,
            },
        )
    except RuntimeError:
        pass
