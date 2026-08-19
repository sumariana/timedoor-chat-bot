# Plan 3 — Module 3: Notion Data Router
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: Acts as the brain between the Query Parser and the Data Fetcher. Takes a `ParsedQuery` (one or more `QueryIntent`s), resolves each project name to a Notion page ID, routes each intent to the correct data source (Tier 1/2 via API or Tier 3 via MCP), handles the API → MCP fallback, and returns one `NotionResult` per question.

**Input**: `ParsedQuery` from Module 2 (Query Parser) — contains a list of `QueryIntent` objects, each with an intent type, project name, environment, and language.

**Output**: `list[tuple[QueryIntent, NotionResult]]` — each question paired with its fetched Notion data. Passed to Module 5 (LLM Response Synthesizer).

**Position in build order**: Built third, after Module 6 (Config) and Module 4 (Data Fetcher). Module 2 (Query Parser) is built on top of this module.

**Depends on**: Module 6 (`get_config()`), Module 4 (all fetch functions).

**Depended on by**: Module 2 connects through this module to reach Notion data. Module 5 receives this module's output.

---

## 2. File Structure

```
apps/bot/src/router/
├── __init__.py         ← exports route_query (the only function Module 2 calls)
├── router.py           ← routing logic, project resolution, MCP fallback
└── normalizer.py       ← maps variant Notion property names to canonical keys

apps/bot/tests/integration/
└── test_router.py      ← integration tests for this module
```

---

## 3. Implementation Steps

### Step 1 — Implement `src/router/normalizer.py`

Built first because `router.py` depends on it.

```python
PROPERTY_ALIASES: dict[str, list[str]] = { ... }

def normalize_properties(raw_properties: dict) -> dict:
    ...
```

**`PROPERTY_ALIASES`** — maps canonical key → list of known Notion property name variants:

```python
PROPERTY_ALIASES: dict[str, list[str]] = {
    "name":               ["Name", "Project Name", "Nama", "Nama Project"],
    "status":             ["Status", "Project Status", "State"],
    "pm":                 ["PM", "Project Manager", "PIC", "Person in Charge", "Penanggung Jawab"],
    "platform":           ["Platform", "Platforms", "Target Platform"],
    "framework":          ["Framework", "Tech Stack", "Stack", "Technologies", "Teknologi"],
    "language":           ["Language", "Programming Language", "Bahasa Pemrograman"],
    "category":           ["Category", "Kategori", "Type", "Project Type"],
    "start_date":         ["Start Date", "Tanggal Mulai", "Date Started", "Kick Off"],
    "end_date":           ["End Date", "Tanggal Selesai", "Due Date", "Deadline"],
    "app_store_url":      ["App Store URL", "App Store", "iOS URL", "Apple Store"],
    "play_store_url":     ["Play Store URL", "Play Store", "Android URL", "Google Play"],
    "firebase_status":    ["Firebase Status", "Firebase"],
    "sentry":             ["Sentry", "Sentry Status"],
    "maintenance_status": ["Maintenance Status", "Maintenance", "Status Maintenance"],
    "design_link":        ["Design Link", "Figma", "Design", "UI Design", "Figma Link"],
    "drive_link":         ["Drive Link", "Google Drive", "Drive", "GDrive"],
}
```

**`normalize_properties(raw_properties)`**:
- Iterates over `PROPERTY_ALIASES`
- For each canonical key, checks if any alias exists in `raw_properties`
- Returns a new dict with canonical keys only — drops any Notion property that has no alias mapping
- If multiple aliases match for the same canonical key, the first match wins

**Constraint**: This alias list is a living document. When a new team's database uses a property name not listed here, add it to `PROPERTY_ALIASES` — no other code change is needed.

---

### Step 2 — Implement `src/router/router.py`

```python
from src.config import get_config, get_error_logger
from src.fetcher import (
    search_project_in_db,
    get_project_properties,
    get_bug_count,
    get_latest_changelog,
    fetch_mcp_page_content,
)
from src.models import ParsedQuery, QueryIntent, NotionResult
from src.router.normalizer import normalize_properties


async def route_query(parsed_query: ParsedQuery) -> list[tuple[QueryIntent, NotionResult]]:
    ...

async def _resolve_project_page_id(project_name: str) -> tuple[str, str] | None:
    ...

async def _route_intent(intent: QueryIntent, page_id: str, notion_url: str) -> NotionResult:
    ...

async def _route_doc_link(page_id: str, project_name: str, notion_url: str) -> NotionResult:
    ...

def _not_found_result() -> NotionResult:
    ...
```

---

**`_not_found_result()`** — internal helper:
- Returns `NotionResult(data=None, source=None, tier=None, from_cache=False, notion_url=None)`
- Used whenever a project is not found in any team DB, or the intent is `unknown`
- Centralized so Module 5 only needs to check `result.data is None` to detect not-found
- Note: this is distinct from a fetch that was attempted but returned null — those set `source` and `tier` to reflect what was tried (see `_try_mcp_fallback` below)

---

**`_resolve_project_page_id(project_name)`**:
- Searches across all team databases in order: mobile → web → backend
- For each database ID from `get_config().notion.databases`, calls `search_project_in_db(project_name, db_id)`
- Returns `(page_id, notion_url)` on first match, or `None` if not found in any database
- Stops searching as soon as a match is found — does not search all teams

```python
async def _resolve_project_page_id(project_name: str) -> tuple[str, str] | None:
    config = get_config()
    databases = config.notion.databases

    for db_id in [databases.mobile_team, databases.web_team, databases.backend_team]:
        result = await search_project_in_db(project_name, db_id)
        if result:
            return result["id"], result["url"]

    return None
```

---

**`_route_intent(intent, page_id, notion_url)`** — routes a single resolved intent:

```python
async def _route_intent(
    intent: QueryIntent,
    page_id: str,
    notion_url: str,
) -> NotionResult:
    match intent.intent:
        case "project_info" | "status_query":
            result = await get_project_properties(page_id)
            if result.data:
                result.data = normalize_properties(result.data)
                return result
            return await _try_mcp_fallback(intent, page_id, notion_url, page_hint="Overview")

        case "bug_query":
            result = await get_bug_count(page_id, environment=None)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, page_id, notion_url, page_hint="Bug List")

        case "bug_query_env":
            result = await get_bug_count(page_id, environment=intent.environment)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, page_id, notion_url, page_hint="Bug List")

        case "version_query":
            result = await get_latest_changelog(page_id)
            if result.data:
                return result
            return await _try_mcp_fallback(intent, page_id, notion_url, page_hint="Change Log")

        case "credential_query":
            # Tier 3 primary — MCP is the only source; no API fallback exists
            return await fetch_mcp_page_content(
                project_name=intent.project_name,
                page_hint="Credentials",
            )

        case "doc_link_query":
            return await _route_doc_link(page_id, intent.project_name, notion_url)

        case _:
            return _not_found_result()
```

**Constraint**: `normalize_properties` is only applied to Tier 1 results (`project_info`, `status_query`) — bug counts and changelogs have their own well-defined structures that do not need normalization.

**Broad MCP fallback policy**: For any intent whose API path returns null (`result.data is None`), the router attempts an MCP fetch on the equivalent page before declaring "not found". This matches PRD Section 7 Module 3's Null Fallback sub-component: *"If API returns empty and MCP also fails, route returns explicit not found signal."*

---

**`_try_mcp_fallback(intent, page_id, notion_url, page_hint)`** — universal API → MCP fallback:

```python
async def _try_mcp_fallback(
    intent: QueryIntent,
    page_id: str,
    notion_url: str,
    page_hint: str,
) -> NotionResult:
    get_error_logger().warning(
        "API returned null, attempting MCP fallback",
        extra={
            "intent": intent.intent,
            "project": intent.project_name,
            "page_hint": page_hint,
        },
    )
    mcp_result = await fetch_mcp_page_content(
        project_name=intent.project_name,
        page_hint=page_hint,
    )
    if mcp_result.data is not None:
        return mcp_result

    # Both API and MCP failed — return a "fetch was attempted" not-found result
    return NotionResult(
        data=None,
        source="mcp",
        tier=3,
        from_cache=False,
        notion_url=notion_url,
    )
```

---

**`_route_doc_link(page_id, project_name, notion_url)`** — API-first with MCP fallback (special case because of the composite `design_link` + `drive_link` shape):

```python
async def _route_doc_link(
    page_id: str,
    project_name: str,
    notion_url: str,
) -> NotionResult:
    # Try API first (Tier 2)
    result = await get_project_properties(page_id)

    if result.data:
        normalized = normalize_properties(result.data)
        design_link = normalized.get("design_link")
        drive_link  = normalized.get("drive_link")

        if design_link or drive_link:
            return NotionResult(
                data={"design_link": design_link, "drive_link": drive_link},
                source="api",
                tier=2,
                from_cache=result.from_cache,
                notion_url=notion_url,
            )

    # API returned nothing — fall back to MCP (Tier 3)
    get_error_logger().warning(
        "doc_link not found in API properties, falling back to MCP",
        extra={"project": project_name},
    )
    return await fetch_mcp_page_content(project_name=project_name, page_hint="Design")
```

---

**`route_query(parsed_query)`** — the main public function:

Resolves project names once across all questions (avoids duplicate Notion API searches for multi-question queries about the same project), then routes each intent.

```python
async def route_query(
    parsed_query: ParsedQuery,
) -> list[tuple[QueryIntent, NotionResult]]:
    # Step 1: collect unique project names and resolve them to page IDs
    resolution_cache: dict[str, tuple[str, str] | None] = {}

    for question in parsed_query.questions:
        name = question.project_name
        if name and name not in resolution_cache:
            resolution_cache[name] = await _resolve_project_page_id(name)

    # Step 2: route each intent using the resolved page ID
    results: list[tuple[QueryIntent, NotionResult]] = []

    for question in parsed_query.questions:
        if question.intent == "unknown":
            results.append((question, _not_found_result()))
            continue

        # Ambiguous project name — skip routing entirely. Module 5 reads
        # `intent.is_ambiguous` and `intent.candidates` from QueryIntent directly,
        # so the NotionResult carries no payload here.
        if question.is_ambiguous:
            results.append((question, _not_found_result()))
            continue

        resolution = resolution_cache.get(question.project_name)
        if not resolution:
            get_error_logger().warning(
                "Project not found in any team database",
                extra={"project": question.project_name},
            )
            results.append((question, _not_found_result()))
            continue

        page_id, notion_url = resolution
        notion_result = await _route_intent(question, page_id, notion_url)
        results.append((question, notion_result))

    return results
```

---

### Step 3 — Export from `src/router/__init__.py`

```python
from src.router.router import route_query
```

Module 2 (and later Module 5 via Module 2's orchestration) only imports `route_query`. Internal functions stay private.

---

## 4. Dependencies

No new packages required. All dependencies are provided by Module 6 (config) and Module 4 (fetchers).

| Used from | Import |
|---|---|
| Module 6 | `get_config`, `get_error_logger` |
| Module 4 | `search_project_in_db`, `get_project_properties`, `get_bug_count`, `get_latest_changelog`, `fetch_mcp_page_content` |
| `src/models.py` | `ParsedQuery`, `QueryIntent`, `NotionResult` |

---

## 5. Integration Points

**Consumed by Module 2 (Query Parser)**:

Module 2 calls `route_query` after parsing the user's message and passes the result directly to Module 5:

```python
from src.router import route_query
from src.models import ParsedQuery

results: list[tuple[QueryIntent, NotionResult]] = await route_query(parsed_query)
```

**Consumed by Module 5 (LLM Response Synthesizer)**:

Module 5 receives the paired list and uses both the intent and the result to build the LLM prompt:

```python
for intent, notion_result in results:
    if notion_result.data is None:
        # generate "not found" response for this question
    elif intent.intent == "credential_query":
        # use credential formatter template
    else:
        # use standard prompt builder
```

**Consumes Module 4 (Data Fetcher)**:

All routing decisions terminate in a Module 4 function call. The router never touches the Notion API or MCP directly — that is Module 4's responsibility.

```python
# Tier 1
result = await get_project_properties(page_id)

# Tier 2
result = await get_bug_count(page_id, environment="staging_mobile")
result = await get_latest_changelog(page_id)

# Tier 3
result = await fetch_mcp_page_content(project_name="Inwan", page_hint="Credentials")
```

**Consumes Module 6 (Config & Observability)**:

```python
config = get_config()
# Access: config.notion.databases.mobile_team / .web_team / .backend_team

logger = get_error_logger()
logger.warning("Project not found", extra={"project": project_name})
```

---

## 6. Tests

**File**: `apps/bot/tests/integration/test_router.py`

All Module 4 fetch functions are mocked. Tests verify routing decisions only — not data fetching.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | `project_info` intent routes to `get_project_properties` | All Module 4 functions | `get_project_properties` called once; other fetchers not called |
| T2 | `bug_query` intent routes to `get_bug_count` with `environment=None` | All Module 4 functions | `get_bug_count(page_id, environment=None)` called |
| T3 | `bug_query_env` intent routes to `get_bug_count` with correct environment | All Module 4 functions | `get_bug_count(page_id, environment="staging_mobile")` called |
| T4 | `version_query` routes to `get_latest_changelog` | All Module 4 functions | `get_latest_changelog` called once |
| T5 | `credential_query` routes to `fetch_mcp_page_content` with `page_hint="Credentials"` | All Module 4 functions | `fetch_mcp_page_content(project_name=..., page_hint="Credentials")` called |
| T6 | `doc_link_query` with API hit does not call MCP | `get_project_properties` returns data with `design_link` | `fetch_mcp_page_content` never called |
| T7 | `doc_link_query` with API miss falls back to MCP | `get_project_properties` returns `NotionResult(data=None)` | `fetch_mcp_page_content(page_hint="Design")` called |
| T8 | `unknown` intent returns `NotionResult(data=None)` without any Notion call | All Module 4 functions | No Module 4 function called; `result.data is None` |
| T9 | Project not found in any team DB returns `NotionResult(data=None)` | `search_project_in_db` returns `None` for all 3 DBs | `result.data is None`; all 3 team DBs searched |
| T10 | Multi-question with same project resolves page ID only once | `search_project_in_db` | `search_project_in_db` called exactly 3 times total (once per team DB), not 3 × number of questions |
| T11 | `normalize_properties` maps variant names to canonical keys | Nothing | Raw `{"Tech Stack": "Flutter"}` becomes `{"framework": "Flutter"}` in `result.data` |
| T12 | `bug_query` with null API result triggers MCP fallback | `get_bug_count` returns `NotionResult(data=None)`; `fetch_mcp_page_content` returns valid data | `fetch_mcp_page_content(page_hint="Bug List")` called; final result uses MCP data |
| T13 | `version_query` with null API result triggers MCP fallback | `get_latest_changelog` returns `data=None`; `fetch_mcp_page_content` returns valid data | `fetch_mcp_page_content(page_hint="Change Log")` called |
| T14 | `project_info` with null API result triggers MCP fallback | `get_project_properties` returns `data=None`; `fetch_mcp_page_content` returns valid data | `fetch_mcp_page_content(page_hint="Overview")` called |
| T15 | Both API and MCP null returns `NotionResult(data=None, source="mcp", tier=3)` | Both fetchers return `data=None` | Final result has `data=None`, `source="mcp"`, `tier=3` |
| T16 | `credential_query` does NOT try API fallback | `fetch_mcp_page_content` returns `data=None` | `get_project_properties`, `get_bug_count`, `get_latest_changelog` never called |
| T17 | Ambiguous intent skips routing without calling any fetcher | `QueryIntent(is_ambiguous=True, candidates=["Inwan (Orange Care)", "Inwan Bali"])` | `NotionResult(data=None)` returned; no Module 4 fetch called; Module 5 reads candidates from `intent.candidates` directly |

---

## 7. Open Questions

1. **Team DB search order**: Currently searches mobile → web → backend and stops at first match. If the same project name exists in two team databases (unlikely but possible), only the first one is returned. Confirm this behavior is acceptable with the team before coding.

2. **`PROPERTY_ALIASES` completeness**: The alias list in `normalizer.py` was written based on known property names. Before launch, each team lead should verify that all their Notion database property names are covered. Missing aliases cause the bot to silently return `None` for that field instead of raising an error.
