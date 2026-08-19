# Plan 4 — Module 2: Query Parser
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: Receives raw Discord message text from Module 1, maintains per-user conversation history, runs a single Gemini call to classify intent + extract project name + detect language + split multi-questions, fuzzy-matches the extracted project name against known Notion projects, and returns a structured `ParsedQuery` to Module 3.

**Input**: Raw message text (str) + `user_id` (int) + `channel_id` (int) — from Module 1 (Discord Gateway).

**Output**: `ParsedQuery` (defined in `src/models.py`) — passed to Module 3 (Notion Data Router).

**Position in build order**: Built fourth, after Module 6 (Config), Module 4 (Data Fetcher), and Module 3 (Router). Module 1 (Discord Gateway) is built on top of this module.

**Depends on**: Module 6 (`get_config()`, loggers), Module 4 (new `list_all_project_names()` function — see Open Questions).

**Depended on by**: Module 1 (calls `parse_message`).

---

## 2. Models Update — `src/models.py`

**Before writing any code in this module, update `src/models.py`** to extend `QueryIntent` with two new fields and add `session_reset` as a valid intent. Coordinate with all engineers before merging.

```python
@dataclass
class QueryIntent:
    intent: str                         # project_info | bug_query | bug_query_env |
                                        # version_query | credential_query |
                                        # doc_link_query | status_query |
                                        # session_reset | unknown
    project_name: Optional[str]
    environment: Optional[str]
    language: str                       # "id" or "en"
    raw_question: str
    is_ambiguous: bool = False          # True if multiple projects matched raw_name
    candidates: list[str] = field(default_factory=list)  # populated when is_ambiguous=True
```

**`is_ambiguous` and `candidates`** allow Module 5 to detect when it should generate a clarification prompt instead of a Notion lookup. Module 3 must skip routing for any `QueryIntent` where `is_ambiguous=True` and pass it directly to Module 5.

---

## 3. File Structure

```
apps/bot/src/parser/
├── __init__.py         ← exports parse_message, add_to_session,
│                         update_session_project, clear_session,
│                         initialize_project_registry
├── session.py          ← in-memory session store (history + last project)
├── classifier.py       ← Gemini call → structured JSON (intent, entity, language, split)
└── matcher.py          ← rapidfuzz project name matching against Notion registry

apps/bot/tests/integration/
└── test_parser.py      ← integration tests for this module
```

---

## 4. Implementation Steps

### Step 1 — Implement `src/parser/session.py`

```python
import time
from dataclasses import dataclass, field
from src.config import get_config


@dataclass
class SessionMessage:
    role: str       # "user" or "assistant"
    content: str

@dataclass
class Session:
    history: list[SessionMessage] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)
    last_project: Optional[str] = None  # most recently resolved project name


class SessionStore:
    def make_key(self, user_id: int, channel_id: int) -> str: ...
    def get_history(self, session_key: str) -> list[SessionMessage]: ...
    def get_last_project(self, session_key: str) -> str | None: ...
    def add_exchange(self, session_key: str, user_msg: str, bot_response: str) -> None: ...
    def update_last_project(self, session_key: str, project_name: str) -> None: ...
    def clear(self, session_key: str) -> None: ...
    def _expire_if_needed(self, session_key: str) -> None: ...


_store = SessionStore()

def get_session_store() -> SessionStore:
    ...
```

**`make_key(user_id, channel_id)`**:
- Returns `f"user:{user_id}_channel:{channel_id}"`
- Consistent with the format defined in Plan 0's `ParsedQuery.session_key`

**`get_history(session_key)`**:
- Calls `_expire_if_needed` first
- Returns `session.history` if session exists, else empty list

**`get_last_project(session_key)`**:
- Calls `_expire_if_needed` first
- Returns `session.last_project` — the canonical name of the most recently resolved project
- Returns `None` if no project has been resolved yet in this session

**`add_exchange(session_key, user_msg, bot_response)`**:
- Appends two `SessionMessage` entries (user + assistant) to history
- Trims history to `config.session.max_history * 2` messages (each exchange = 2 messages)
- Updates `last_active` timestamp
- Creates a new session if one does not exist for this key

**`update_last_project(session_key, project_name)`**:
- Called by Module 1 after a successful query so future follow-up questions can inherit the project
- Only updates `last_project` — does not modify history

**`clear(session_key)`**:
- Deletes the session entirely — called when user sends `@bot reset`
- Silently does nothing if session does not exist

**`_expire_if_needed(session_key)`**:
- If `time.time() - session.last_active > config.session.timeout_minutes * 60`, delete the session
- Called at the start of `get_history` and `get_last_project` so expired sessions are cleaned up lazily

---

### Step 2 — Implement `src/parser/classifier.py`

Makes a single structured Gemini call using the `google-generativeai` SDK directly. The direct SDK is used here (not LangChain's wrapper) because this call needs strict JSON schema enforcement (`response_mime_type="application/json"`), which is simpler with the native SDK.

```python
import json
import google.generativeai as genai
from src.config import get_config


CLASSIFICATION_PROMPT = """..."""  # see below


async def classify_message(
    user_message: str,
    history: list[dict],
) -> tuple[str, list[dict]]:
    """
    Returns (language, questions).
    language: "id" or "en"
    questions: list of dicts with keys: intent, project_name, environment, raw_question
    """
    ...


def _build_history_text(history: list[dict]) -> str:
    ...
```

**`CLASSIFICATION_PROMPT`**:

```
You are an intent classifier for the Timedoor Project Assistant — an internal company chatbot.

Given a user message (in Indonesian or English), your job is to:
1. Detect the language of the message
2. Split it into individual questions if the message contains multiple
3. For each question, identify the intent and extract the project name

Return ONLY valid JSON in this exact structure:
{
  "language": "id" | "en",
  "questions": [
    {
      "intent": "...",
      "project_name": "..." | null,
      "environment": "..." | null,
      "raw_question": "..."
    }
  ]
}

INTENT DEFINITIONS:
- project_info    : tech stack, PM, platform, framework, dates, app store URLs, category
- bug_query       : bug count without specifying an environment
- bug_query_env   : bug count for a specific environment (e.g. staging mobile, dev admin)
- version_query   : latest version or release from changelog
- credential_query: server host, URL, database credentials
- doc_link_query  : design link, Figma link, Google Drive link, documentation
- status_query    : current project status (active, maintenance, done)
- unknown         : cannot determine intent

ENVIRONMENT VALUES (only for bug_query_env):
Use these exact strings: dev_mobile, dev_admin, staging_mobile, staging_admin,
production_mobile, production_admin

RULES:
- Extract project_name exactly as the user typed it — do not correct spelling
- If no project is mentioned, set project_name to null
- If a question references "it" or "that project", set project_name to null (context is resolved in code)
- Split numbered lists (1. ... 2. ... 3. ...) and comma-separated questions into separate items
- raw_question should contain the original text for that specific sub-question

[CONVERSATION HISTORY]
{history}

[USER MESSAGE]
{user_message}
```

**`classify_message(user_message, history)`**:
- Configures Gemini with `get_config().llm.api_key` and `get_config().llm.model`
- Sets `response_mime_type="application/json"` for guaranteed JSON output
- Fills in `{history}` using `_build_history_text(history)` and `{user_message}`
- Parses the JSON response
- Returns `(language, questions_list)`
- On JSON parse error or API failure: logs via `get_error_logger()`, returns `("id", [{"intent": "unknown", "project_name": None, "environment": None, "raw_question": user_message}])` as safe fallback

**`_build_history_text(history)`**:
- Formats `list[dict]` of `{"role": str, "content": str}` into a readable string
- Returns `"(no previous conversation)"` if history is empty

---

### Step 3 — Implement `src/parser/matcher.py`

```python
from rapidfuzz import process, fuzz
from typing import Optional


_registry: list[str] = []


async def initialize_project_registry() -> None:
    ...

def fuzzy_match_project(
    raw_name: str,
    threshold: float = 70.0,
    ambiguity_gap: float = 10.0,
) -> tuple[Optional[str], list[str]]:
    ...
```

**`initialize_project_registry()`**:
- Called once at bot startup, before Module 1 starts accepting messages
- Imports `list_all_project_names` from Module 4 (new function — see Section 5)
- Fetches all project names across all team databases and stores in `_registry`
- Logs the count via `get_error_logger()` so startup can be verified

**`fuzzy_match_project(raw_name, threshold, ambiguity_gap)`**:
- Uses `rapidfuzz.process.extract(raw_name, _registry, scorer=fuzz.WRatio, limit=5)`
- If the top match score ≥ `threshold` AND the gap between 1st and 2nd place ≥ `ambiguity_gap`: confident single match → return `(top_match_name, [])`
- If top score ≥ `threshold` AND gap < `ambiguity_gap`: multiple close matches → return `(None, [match1, match2, ...])`
- If top score < `threshold`: no match → return `(None, [])`
- If `_registry` is empty (startup not done yet): return `(None, [])` with a warning log

---

### Step 4 — Implement main flow in `src/parser/__init__.py`

```python
from src.parser.session import get_session_store
from src.parser.classifier import classify_message
from src.parser.matcher import fuzzy_match_project, initialize_project_registry
from src.models import ParsedQuery, QueryIntent
from src.config import get_audit_logger


async def parse_message(
    message_text: str,
    user_id: int,
    channel_id: int,
) -> ParsedQuery:
    ...

def add_to_session(
    user_id: int,
    channel_id: int,
    user_message: str,
    bot_response: str,
) -> None:
    ...

def update_session_project(
    user_id: int,
    channel_id: int,
    project_name: str,
) -> None:
    ...

def clear_session(user_id: int, channel_id: int) -> None:
    ...
```

**`parse_message(message_text, user_id, channel_id)`**:

Full step-by-step logic:

```
1. Strip the bot @mention from message_text → clean_text
2. Make session_key via store.make_key(user_id, channel_id)
3. If clean_text.strip().lower() == "reset":
     → store.clear(session_key)
     → return ParsedQuery with a single "session_reset" QueryIntent
4. Get history = store.get_history(session_key)
5. Get last_project = store.get_last_project(session_key)
6. Call classify_message(clean_text, history_dicts) → (language, raw_questions)
7. For each raw_question in raw_questions:
     a. raw_name = raw_question["project_name"]
     b. If raw_name is not None:
          → matched, candidates = fuzzy_match_project(raw_name)
          → if matched: project_name = matched, is_ambiguous = False, candidates = []
          → if candidates: project_name = None, is_ambiguous = True, candidates = candidates
          → if neither: project_name = raw_name, is_ambiguous = False (pass raw to Module 3)
     c. If raw_name is None:
          → project_name = last_project (inherit from session)
          → is_ambiguous = False, candidates = []
     d. Build QueryIntent with all fields
8. Write audit log: user_id, channel_id, intents, project names (no content)
9. Return ParsedQuery(
     questions=questions,
     session_key=session_key,
     user_id=user_id,
     channel_id=channel_id,
     history=[{"role": h.role, "content": h.content} for h in history],
     # history is populated here so Module 5 receives it without a second call
   )
```

**`add_to_session(user_id, channel_id, user_message, bot_response)`**:
- Delegates to `store.add_exchange(key, user_message, bot_response)`
- Called by Module 1 after the bot successfully sends a response

**`update_session_project(user_id, channel_id, project_name)`**:
- Delegates to `store.update_last_project(key, project_name)`
- Called by Module 1 after Module 3 resolves an ambiguous or raw project name to a canonical one

**`clear_session(user_id, channel_id)`**:
- Delegates to `store.clear(key)`

---

## 5. Dependencies

| Package | Already in `requirements.txt` | Why used here |
|---|---|---|
| `google-generativeai` | Yes | Direct Gemini SDK for structured JSON classification call |
| `rapidfuzz` | Yes | Fuzzy project name matching |
| `logging` | stdlib | Audit log via Module 6 |

No new packages needed.

**New function required in Module 4** — add to `apps/bot/src/fetcher/notion_api.py`:

```python
async def list_all_project_names() -> list[str]:
    """
    Queries all team databases and returns a flat list of all project names.
    Called once at startup by Module 2's matcher.initialize_project_registry().
    """
```

This function queries each team database with no filter (or paginates through all pages) and collects the `Name` property value from each. Also export it from `src/fetcher/__init__.py`.

---

## 6. Integration Points

**Called by Module 1 (Discord Gateway)**:

```python
from src.parser import (
    parse_message,
    add_to_session,
    update_session_project,
    clear_session,
    initialize_project_registry,
)

# At bot startup — before accepting messages
await initialize_project_registry()

# On each incoming message
parsed: ParsedQuery = await parse_message(message_text, user_id, channel_id)

# After bot sends response
add_to_session(user_id, channel_id, user_message, bot_response)

# After Module 3 resolves a project name (Module 1 receives this from Module 5 output)
update_session_project(user_id, channel_id, resolved_project_name)
```

**Outputs to Module 3 (Notion Data Router)**:

```python
from src.router import route_query

results = await route_query(parsed_query)
```

Module 3 must handle the `is_ambiguous=True` case: skip routing for that intent and return a `NotionResult(data={"ambiguous": True, "candidates": [...]}, source=None, tier=None, from_cache=False, notion_url=None)` so Module 5 generates a clarification prompt.

**Audit log emitted here** (via Module 6):

```python
get_audit_logger().info(
    "query_parsed",
    extra={
        "user_id": user_id,
        "channel_id": channel_id,
        "intents": [q.intent for q in parsed.questions],
        "projects": [q.project_name for q in parsed.questions],
        # never log raw_question or session history content
    },
)
```

---

## 7. Tests

**File**: `apps/bot/tests/integration/test_parser.py`

Gemini API is mocked in all tests — no live LLM calls.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | Single-intent Indonesian query parsed correctly | Gemini call returns `{"language":"id","questions":[{"intent":"project_info","project_name":"Inwan",...}]}` | `ParsedQuery` has 1 `QueryIntent` with `intent="project_info"`, `language="id"` |
| T2 | Multi-question message split into separate intents | Gemini returns 4 questions | `ParsedQuery.questions` has 4 items in the same order as the input |
| T3 | Fuzzy match resolves "inwan oc" → canonical name | `_registry` contains "Inwan (Orange Care)" | `QueryIntent.project_name` equals "Inwan (Orange Care)" |
| T4 | Ambiguous project name sets `is_ambiguous=True` | `_registry` has "Inwan (Orange Care)" and "Inwan Bali" both scoring similarly | `QueryIntent.is_ambiguous=True`, `candidates` has both options |
| T5 | Project name inherited from session when not mentioned | Previous session has `last_project="Inwan"` | `QueryIntent.project_name="Inwan"` even though message doesn't name it |
| T6 | `@bot reset` clears session and returns `session_reset` intent | Nothing | Session cleared; `ParsedQuery` has 1 intent of `"session_reset"` |
| T7 | Session expires after timeout | `time.time()` advanced past `timeout_minutes * 60` | `get_history()` returns empty list after expiry |
| T8 | Session history trimmed to `max_history` exchanges | Nothing | After 6 exchanges with `max_history=5`, only 5 most recent stored |
| T9 | Gemini API failure returns graceful `unknown` fallback | Gemini call raises exception | `ParsedQuery` has 1 `QueryIntent` with `intent="unknown"`; no exception raised |
| T10 | Audit log emitted with correct fields | Capture `tab.audit` logger output | Log contains `user_id`, `channel_id`, `intents`, `projects`; no raw message content |
| T11 | English query returns `language="en"` | Gemini returns `"language":"en"` | `QueryIntent.language="en"` |

---

## 8. Open Questions

1. **`list_all_project_names()` in Module 4**: Plan 2 needs to be updated to add this function to `notion_api.py` and export it from `src/fetcher/__init__.py`. If the engineer for Module 4 is different, coordinate with them before starting Step 3 of this plan.

2. **Fuzzy match thresholds**: The `threshold=70.0` and `ambiguity_gap=10.0` defaults are starting values. Test against real Timedoor project names before finalizing — names that are very short (e.g., "TM") may produce too many false positives at 70.0. Consider raising to 80.0 for short names.

3. **Ambiguity handling in Module 3**: Module 3's `route_query` must skip routing for `is_ambiguous=True` intents. This is not yet in Plan 3. Confirm with Plan 3's engineer that they will add this check before either module is coded.
