# Plan 2 — Module 4: Data Fetcher
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: Executes all actual data retrieval from Notion — either via the Notion REST API (Tier 1 and 2) or via the Notion MCP server (Tier 3). Manages an in-memory cache with per-tier TTLs to avoid redundant API calls. Returns a `NotionResult` object to Module 3 (Router).

**Input**: Fetch parameters from Module 3 — project page ID, database IDs, intent type, and optional environment filter.

**Output**: `NotionResult` (defined in `src/models.py`) — structured data payload, source tag, tier number, cache flag, and Notion page URL.

**Position in build order**: Built second, after Module 6 (Config & Observability). Module 3 (Router) is built on top of this module.

**Depends on**: Module 6 (`get_config()` for tokens and TTL values).

**Depended on by**: Module 3 (Notion Data Router).

---

## 2. File Structure

```
apps/bot/src/fetcher/
├── __init__.py         ← exports all public fetch functions
├── notion_api.py       ← Tier 1 & 2: Notion REST API operations
├── notion_mcp.py       ← Tier 3: Notion MCP server client (singleton)
└── cache.py            ← in-memory TTL cache shared across all fetchers

apps/bot/tests/integration/
└── test_fetcher.py     ← integration tests for this module
```

---

## 3. Implementation Steps

### Step 1 — Implement `src/fetcher/cache.py`

Built first because both `notion_api.py` and `notion_mcp.py` depend on it.

```python
import time


class CacheStore:
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict, ttl: int) -> None: ...
    def invalidate(self, key: str) -> None: ...


_cache = CacheStore()


def get_cache() -> CacheStore:
    ...
```

**`CacheStore.get(key)`**:
- Returns cached `dict` if the key exists and has not expired
- Deletes the entry and returns `None` if TTL has passed
- Returns `None` if key does not exist

**`CacheStore.set(key, value, ttl)`**:
- Stores `{"data": value, "expires_at": time.time() + ttl}`
- Overwrites any existing entry for the same key

**`CacheStore.invalidate(key)`**:
- Removes a single key; silently does nothing if key does not exist

**`get_cache()`**:
- Returns the module-level `_cache` singleton — one shared instance for the entire bot process

**Cache key format** — must be consistent across all callers:

| Data type | Key format | Example |
|---|---|---|
| Project properties | `project_props:{page_id}` | `project_props:abc123` |
| Bug count (all envs) | `bug_count:{page_id}` | `bug_count:abc123` |
| Bug count (specific env) | `bug_count:{page_id}:{env}` | `bug_count:abc123:staging_mobile` |
| Changelog | `changelog:{page_id}` | `changelog:abc123` |
| Doc links | `doc_links:{page_id}` | `doc_links:abc123` |
| Credentials | **Never cached** | — |

**Constraint**: Credentials must never be cached regardless of how the fetcher is called. The cache layer does not enforce this — it is enforced by `notion_mcp.py` which simply never calls `cache.set()` for credential data.

---

### Step 2 — Implement `src/fetcher/notion_api.py`

Handles all Tier 1 and Tier 2 operations using the official `notion-client` Python package.

```python
from notion_client import AsyncClient
from src.config import get_config
from src.fetcher.cache import get_cache
from src.models import NotionResult


def _get_client() -> AsyncClient:
    ...

async def search_project_in_db(project_name: str, db_id: str) -> dict | None:
    ...

async def get_project_properties(page_id: str) -> NotionResult:
    ...

async def get_bug_count(page_id: str, environment: str | None) -> NotionResult:
    ...

async def get_latest_changelog(page_id: str) -> NotionResult:
    ...

async def _find_child_database(page_id: str, name_hint: str) -> str | None:
    ...
```

**`_get_client()`**:
- Creates and returns an `AsyncClient` initialized with `get_config().notion.api_token`
- Returns the same instance on repeated calls (module-level singleton)

**`search_project_in_db(project_name, db_id)`**:
- Queries the given Notion database using a `title` filter on `project_name`
- Returns the first matching page as a raw dict, or `None` if no match
- Not cached — this is a lookup operation called by Module 3 to resolve a name to a page ID; the result (page ID) is then used in the cached fetch functions

**`get_project_properties(page_id)`** — Tier 1:
- Cache key: `project_props:{page_id}`, TTL: `config.cache.project_properties_ttl`
- On cache hit: return `NotionResult(data=cached, source="api", tier=1, from_cache=True, notion_url=...)`
- On cache miss: call `notion.pages.retrieve(page_id=page_id)`, extract relevant properties, cache result, return `NotionResult`
- Properties to extract: Name, Status, Platform, Category, PM, Framework, Tech Stack, Language, Dates, App Store URLs, Firebase Status, Sentry, Maintenance Status

**`_find_child_database(page_id, name_hint)`** — internal helper for Tier 2:
- Calls `notion.blocks.children.list(block_id=page_id)` to list all child blocks of the project page
- Finds the child block where `type == "child_database"` and the database title contains `name_hint` (e.g., "Bug List", "Change Log")
- Returns the child database ID, or `None` if not found
- This is the "multi-hop" step: Project Page → child database ID

**`get_bug_count(page_id, environment)`** — Tier 2:
- Cache key: `bug_count:{page_id}` or `bug_count:{page_id}:{environment}`, TTL: `config.cache.bug_counts_ttl`
- On cache miss:
  1. Call `_find_child_database(page_id, "Bug List")` to get the bug list DB ID
  2. If `environment` is provided, add a `select` filter on the environment property
  3. Query the database with a `Status` filter for active statuses (Open, In Progress, Re-Opened, Re-Test)
  4. Count results and group by Status
- Returns `NotionResult` with `data = {"total": int, "by_status": dict, "environment": str | None}`
- If child database not found: return `NotionResult(data=None, ...)`

**`get_latest_changelog(page_id)`** — Tier 2:
- Cache key: `changelog:{page_id}`, TTL: `config.cache.changelog_ttl`
- On cache miss:
  1. Call `_find_child_database(page_id, "Change Log")` to get changelog DB ID
  2. Query database sorted by date descending, limit 1
- Returns `NotionResult` with `data = {"version": str, "date": str, "notes": str | None}`
- If child database not found: return `NotionResult(data=None, ...)`

---

### Step 3 — Implement `src/fetcher/notion_mcp.py`

Handles Tier 3 operations by connecting to the Notion MCP server through **LangChain's MCP adapter** (`langchain-mcp-adapters`). LangChain's role here is a thin adapter only — it manages the MCP subprocess connection and tool loading. It does NOT orchestrate routing decisions (that stays in Module 3).

The Notion MCP server is a Node.js process (`@notionhq/notion-mcp-server`) that communicates via stdio.

**Pre-requisite**: The Notion MCP server must be installed before running the bot:
```bash
npm install -g @notionhq/notion-mcp-server
```

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from src.config import get_config, get_latency_logger, get_error_logger
from src.fetcher.cache import get_cache
from src.models import NotionResult


class NotionMCPClient:
    _instance: "NotionMCPClient | None" = None
    _client: MultiServerMCPClient | None = None
    _tools: dict | None = None                # tool_name → LangChain BaseTool

    @classmethod
    async def get_instance(cls) -> "NotionMCPClient":
        ...

    async def _connect(self) -> None:
        ...

    async def search_workspace(self, query: str) -> list[dict]:
        ...

    async def get_page_content(self, page_id: str) -> dict | None:
        ...

    async def list_child_pages(self, parent_page_id: str) -> list[dict]:
        ...


async def fetch_mcp_page_content(project_name: str, page_hint: str) -> NotionResult:
    ...
```

**`NotionMCPClient._connect()`**:
- Instantiates `MultiServerMCPClient` with a config dict pointing to the Notion MCP server:
  ```python
  self._client = MultiServerMCPClient({
      "notion": {
          "command": "notion-mcp-server",
          "args": [],
          "env": {"NOTION_API_TOKEN": get_config().notion.api_token},
          "transport": "stdio",
      }
  })
  ```
- Calls `await self._client.get_tools()` to load available MCP tools and stores them in `self._tools` (keyed by tool name)
- Called once at startup; the connection stays open for the bot's lifetime

**`NotionMCPClient.get_instance()`**:
- Returns the singleton `_instance`, calling `_connect()` first if not yet initialized
- All MCP callers go through this — never instantiate directly

**`NotionMCPClient.search_workspace(query)`**:
- Invokes the loaded `notion_search` tool via `await self._tools["notion_search"].ainvoke({"query": query})`
- Returns a list of matching page summaries (id, title, url)

**`NotionMCPClient.get_page_content(page_id)`**:
- Invokes the loaded `notion_get_page` tool via `.ainvoke({"page_id": page_id})`
- Returns the raw page content as a dict (blocks, properties, text)

**`NotionMCPClient.list_child_pages(parent_page_id)`**:
- Invokes the loaded `notion_list_children` tool via `.ainvoke({"block_id": parent_page_id})`
- Returns only child blocks of type `child_page` (filters out other block types)

**`fetch_mcp_page_content(project_name, page_hint)`** — public function called by Module 3:
- `page_hint` is the name of the child page to find (e.g., `"Credentials"`, `"Design"`)
- Flow:
  1. Search workspace for `project_name` → get project page ID
  2. List child pages of the project page
  3. Find the child page whose title contains `page_hint`
  4. Fetch that page's content
- Cache: `doc_links` type uses TTL `config.cache.doc_links_ttl`; credentials are **never cached**
- Returns `NotionResult(data={"content": str, "notion_url": str}, source="mcp", tier=3, from_cache=False, notion_url=str)`
- If any step returns nothing: return `NotionResult(data=None, source="mcp", tier=3, from_cache=False, notion_url=None)`

**Constraint — credentials never cached**:
When `page_hint == "Credentials"`, `fetch_mcp_page_content` must not call `cache.set()` under any circumstances. The returned `NotionResult.data` contains raw page text — Module 5 (LLM Synthesizer) is responsible for filtering out sensitive fields via prompt engineering (see PRD Section 7 Module 5 — Credential Extractor).

---

### Step 4 — Export from `src/fetcher/__init__.py`

```python
from src.fetcher.notion_api import (
    search_project_in_db,
    get_project_properties,
    get_bug_count,
    get_latest_changelog,
)
from src.fetcher.notion_mcp import fetch_mcp_page_content
```

Module 3 imports only from `src.fetcher` — never from sub-files directly.

---

## 4. Dependencies

| Package | Version | Why |
|---|---|---|
| `notion-client` | `>=2.2.1` | Official Notion REST API async client |
| `langchain-mcp-adapters` | `>=0.0.5` | LangChain wrapper for MCP connection (thin adapter — no agent orchestration) |
| `mcp` | `>=1.0.0` | MCP protocol SDK — required transitively by `langchain-mcp-adapters` |

All three are already in `requirements.txt` from Plan 0. No new packages needed.

**External tooling** (not a Python package — must be installed separately):
```bash
npm install -g @notionhq/notion-mcp-server
```
This is a one-time setup step on each machine running the bot.

---

## 5. Integration Points

**Consumed by Module 3 (Notion Data Router)**:

Module 3 calls these functions after resolving the project page ID:

```python
from src.fetcher import (
    search_project_in_db,
    get_project_properties,
    get_bug_count,
    get_latest_changelog,
    fetch_mcp_page_content,
)

# Tier 1
result: NotionResult = await get_project_properties(page_id="abc123")

# Tier 2
result: NotionResult = await get_bug_count(page_id="abc123", environment="staging_mobile")
result: NotionResult = await get_latest_changelog(page_id="abc123")

# Tier 3
result: NotionResult = await fetch_mcp_page_content(project_name="Inwan", page_hint="Credentials")
```

**Data returned to Module 3 → passed to Module 5**:

```python
# NotionResult fields (from src/models.py)
result.data        # dict with fetched content, or None if not found
result.source      # "api" or "mcp"
result.tier        # 1, 2, or 3
result.from_cache  # True if served from cache
result.notion_url  # Notion page URL — required for credential responses
```

**Consumes Module 6 (Config & Observability)**:

```python
from src.config import get_config, get_error_logger, get_latency_logger
import time

config = get_config()
token  = config.notion.api_token
ttl    = config.cache.bug_counts_ttl

# Error logging
get_error_logger().error(
    "Notion API call failed",
    extra={"module": "fetcher", "page_id": page_id},
)

# Latency logging — every fetch operation must be timed
start = time.perf_counter()
result = await notion.pages.retrieve(page_id=page_id)
duration_ms = int((time.perf_counter() - start) * 1000)
get_latency_logger().info(
    "notion_api_call",
    extra={
        "module": "fetcher",
        "operation": "get_project_properties",
        "source": "api",
        "tier": 1,
        "duration_ms": duration_ms,
        "from_cache": False,
    },
)
```

**Latency logging requirement — this module is the primary contributor to end-to-end response time.** Every public fetch function (`get_project_properties`, `get_bug_count`, `get_latest_changelog`, `fetch_mcp_page_content`) must wrap its actual network call in a latency timer and emit a `tab.latency` log line with `operation`, `source`, `tier`, `duration_ms`, and `from_cache` fields. Cache hits should also be logged (with `duration_ms` reflecting cache lookup time and `from_cache=True`) so we can measure cache effectiveness.

---

## 6. Tests

**File**: `apps/bot/tests/integration/test_fetcher.py`

All tests mock the Notion API client and MCP client — no live Notion calls during testing.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | Cache hit returns cached data without API call | Notion API client | Second call within TTL returns `from_cache=True`; API mock called exactly once |
| T2 | Cache miss after TTL expiry triggers fresh API call | Notion API client + `time.time()` (advanced past TTL) | After TTL, API mock called again; `from_cache=False` |
| T3 | Credentials fetch never writes to cache | MCP client | After credential fetch, `cache.get("credentials:...")` returns `None` |
| T4 | `get_bug_count` with environment filters correctly | Notion API client | API called with environment filter in query; result scoped to that environment |
| T5 | `get_bug_count` without environment returns all envs | Notion API client | API called without environment filter |
| T6 | `_find_child_database` returns None for missing sub-DB | Notion blocks.children.list mock returning no child DBs | `get_bug_count` returns `NotionResult(data=None)` |
| T7 | `get_project_properties` maps raw Notion response to expected dict shape | Notion API client | Returned `data` dict contains keys: `name`, `status`, `pm`, `framework`, `platform` |
| T8 | MCP client connects only once across multiple calls | MCP subprocess | `_connect()` called exactly once; subsequent calls reuse `_session` |
| T9 | `fetch_mcp_page_content` returns `data=None` when project not found in workspace | MCP search mock returning empty list | `NotionResult(data=None, source="mcp", tier=3)` |
| T10 | Every fetch operation writes a `tab.latency` log entry | Notion API + MCP clients; capture latency logger output | Each fetch call produces exactly one latency log with fields `operation`, `source`, `tier`, `duration_ms`, `from_cache` |

---

## 7. Open Questions

1. **Notion MCP tool names**: The exact tool names exposed by `@notionhq/notion-mcp-server` (e.g., `notion_search`, `notion_get_page`) must be verified by running `session.list_tools()` after connecting and checking the output. Update `notion_mcp.py` tool name strings to match.

2. **Environment property name in Bug List**: The Notion property used for environment tabs (e.g., "Dev Mobile", "Staging Mobile") may vary across team databases. Verify the exact property name in the real Notion Bug List database before implementing the environment filter in `get_bug_count`.
