# Plan 0 — Project Setup
## Timedoor Project Assistant Bot

---

## 1. Overview

This plan scaffolds the entire monorepo before any module is implemented. It creates the folder structure, installs dependencies, defines shared data models used across all modules, sets up configuration files, and provides the `main.py` entry point.

**Every co-worker must complete this plan on their local machine before starting their module.**

No business logic is written here — only structure, models, and config.

---

## 2. File Structure

Every file to be created in this plan:

```
timedoor-project-assistant/
├── apps/
│   ├── bot/
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── models.py               ← shared data models used across all modules
│   │   │   ├── gateway/
│   │   │   │   └── __init__.py
│   │   │   ├── parser/
│   │   │   │   └── __init__.py
│   │   │   ├── router/
│   │   │   │   └── __init__.py
│   │   │   ├── fetcher/
│   │   │   │   └── __init__.py
│   │   │   ├── synthesizer/
│   │   │   │   └── __init__.py
│   │   │   └── config/
│   │   │       └── __init__.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── unit/
│   │   │   │   └── __init__.py
│   │   │   ├── integration/
│   │   │   │   └── __init__.py
│   │   │   └── e2e/
│   │   │       └── __init__.py
│   │   ├── main.py                     ← entry point (demo: bot only, production: bot + FastAPI)
│   │   └── requirements.txt            ← all dependencies
│   └── api/
│       └── .gitkeep                    ← Phase 2 placeholder, do not delete
├── config/
│   └── config.yaml                     ← all runtime configuration
├── .env.example                        ← template for secrets (committed)
├── .env                                ← actual secrets (never committed)
└── .gitignore
```

---

## 3. Implementation Steps

### Step 1 — Create the folder structure

Run these commands from the project root:

```bash
mkdir -p apps/bot/src/gateway
mkdir -p apps/bot/src/parser
mkdir -p apps/bot/src/router
mkdir -p apps/bot/src/fetcher
mkdir -p apps/bot/src/synthesizer
mkdir -p apps/bot/src/config
mkdir -p apps/bot/tests/unit
mkdir -p apps/bot/tests/integration
mkdir -p apps/bot/tests/e2e
mkdir -p apps/api
mkdir -p config

touch apps/bot/src/__init__.py
touch apps/bot/src/gateway/__init__.py
touch apps/bot/src/parser/__init__.py
touch apps/bot/src/router/__init__.py
touch apps/bot/src/fetcher/__init__.py
touch apps/bot/src/synthesizer/__init__.py
touch apps/bot/src/config/__init__.py
touch apps/bot/tests/__init__.py
touch apps/bot/tests/unit/__init__.py
touch apps/bot/tests/integration/__init__.py
touch apps/bot/tests/e2e/__init__.py
touch apps/api/.gitkeep
```

---

### Step 2 — Create `.gitignore`

**File**: `.gitignore`

```gitignore
# Secrets
.env

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

---

### Step 3 — Create `.env.example`

**File**: `.env.example`

```env
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Notion
NOTION_API_TOKEN=your_notion_integration_token_here

# Gemini (Google AI Studio — free tier for demo, paid API for production)
GEMINI_API_KEY=your_gemini_api_key_here
```

Copy this file to `.env` and fill in real values. Never commit `.env`.

---

### Step 4 — Create `config/config.yaml`

**File**: `config/config.yaml`

```yaml
discord:
  allowed_channels:
    - "REPLACE_WITH_CHANNEL_ID"     # e.g. #project-bot
  denied_channels: []
  allow_dms: true
  dm_require_server_membership: true
  timedoor_server_id: "REPLACE_WITH_SERVER_ID"

notion:
  databases:
    mobile_team: "REPLACE_WITH_NOTION_DB_ID"
    web_team: "REPLACE_WITH_NOTION_DB_ID"
    backend_team: "REPLACE_WITH_NOTION_DB_ID"

session:
  max_history: 5
  timeout_minutes: 30

cache:
  project_properties_ttl: 1800     # 30 min — Tier 1
  bug_counts_ttl: 300               # 5 min  — Tier 2
  changelog_ttl: 900                # 15 min — Tier 2
  doc_links_ttl: 3600               # 60 min — Tier 3 (doc links only)
  # credentials: no cache — always fetched fresh

llm:
  model: "gemini-2.0-flash"
  temperature: 0.2
  max_output_tokens: 1024

rate_limit:
  max_queries_per_user_per_minute: 5
```

---

### Step 5 — Create `apps/bot/requirements.txt`

**File**: `apps/bot/requirements.txt`

```
# Discord
discord.py>=2.3.2

# LangChain — thin adapter for MCP connection + Gemini wrapper only
# (Router logic in Module 3 is plain Python — LangChain does NOT orchestrate routing)
langchain>=0.3.0
langchain-google-genai>=2.0.0     # Gemini 2.0 Flash wrapper (used by Module 5)
langchain-mcp-adapters>=0.0.5     # Notion MCP connection (used by Module 4)

# LLM — Gemini SDK (used by Module 2 for intent classification via direct SDK)
google-generativeai>=0.8.0

# Notion
notion-client>=2.2.1

# MCP protocol SDK — required transitively by langchain-mcp-adapters
mcp>=1.0.0

# Config & environment
PyYAML>=6.0.1
python-dotenv>=1.0.0

# Fuzzy matching (Module 2 — Entity Extractor)
rapidfuzz>=3.9.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0

# Production only — uncomment when deploying to Railway
# fastapi>=0.111.0
# uvicorn>=0.30.0
```

Install with:
```bash
cd apps/bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### Step 6 — Create `src/models.py` — Shared Data Models

**File**: `apps/bot/src/models.py`

This is the most important file in Plan 0. All modules import from here. Define it once — never duplicate these classes inside individual modules.

```python
from dataclasses import dataclass, field
from typing import Optional


# ── Output of Module 2 (Parser) ──────────────────────────────────────────────

@dataclass
class QueryIntent:
    intent: str                         # one of 7 intents or "unknown"
    project_name: Optional[str]         # raw name as extracted by LLM
    environment: Optional[str]          # only set for bug_query_env
    language: str                       # "id" or "en"
    raw_question: str                   # original sub-question text

@dataclass
class ParsedQuery:
    questions: list[QueryIntent]
    session_key: str                    # f"user:{user_id}_channel:{channel_id}"
    user_id: int
    channel_id: int


# ── Output of Module 4 (Data Fetcher) ────────────────────────────────────────

@dataclass
class NotionResult:
    data: Optional[dict]                # structured data returned; None if not found
    source: Optional[str]               # "api" or "mcp"; None if no fetch was attempted
    tier: Optional[int]                 # 1, 2, or 3; None if no fetch was attempted
    from_cache: bool
    notion_url: Optional[str]           # page URL — required for credential responses

    # Not-found convention:
    # - Project not found in any team DB → all fields None/False except from_cache=False
    # - API returned null (fetch attempted) → source="api", tier=1/2, data=None
    # - MCP fallback also returned null → source="mcp", tier=3, data=None
    # Consumers should primarily check `data is None` to detect not-found.


# ── Output of Module 5 (LLM Synthesizer) → input to Module 1 (Gateway) ──────

@dataclass
class BotResponse:
    content: str                        # final text to send to Discord
    language: str                       # "id" or "en"
    is_error: bool = False              # True if bot is reporting a failure
    is_credential: bool = False         # True if credential partial-reveal template used
```

---

### Step 7 — Create `apps/bot/main.py`

**File**: `apps/bot/main.py`

Demo phase only (local run). Production phase adds FastAPI via `asyncio.gather` — that is handled in a separate production migration step, not here.

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../../.env")


async def main() -> None:
    # Imports are deferred here so modules can be developed independently.
    # Replace each import with the real implementation as modules are completed.
    from src.config.loader import load_config
    from src.gateway.client import create_bot

    config = load_config(config_path="../../config/config.yaml")
    bot = create_bot(config)
    await bot.start(os.environ["DISCORD_BOT_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())
```

> `load_config` and `create_bot` do not exist yet — they will be implemented in Module 6 and Module 1 respectively. `main.py` will raise an ImportError until those modules are complete. This is expected.

---

## 4. Dependencies

All dependencies are listed in `requirements.txt` (Step 5). Summary:

| Package | Why |
|---|---|
| `discord.py` | Discord WebSocket gateway and event handling |
| `google-generativeai` | Gemini 2.0 Flash API calls |
| `notion-client` | Notion REST API for Tier 1 and Tier 2 data |
| `mcp` | Notion MCP server connection for Tier 3 data |
| `PyYAML` | Parse `config.yaml` |
| `python-dotenv` | Load `.env` secrets into environment |
| `rapidfuzz` | Fuzzy project name matching in Module 2 |
| `pytest` | All test layers (unit, integration, E2E) |
| `pytest-asyncio` | Async test support for discord.py coroutines |

---

## 5. Integration Points

`src/models.py` is the integration contract between all modules. The actual data flow through the system is:

```
Module 1 (Gateway) receives Discord message
   │
   ▼  raw text
Module 2 (Parser) → ParsedQuery
   │
   ▼  ParsedQuery
Module 3 (Router) — resolves project name, decides routing
   │
   ▼  calls Module 4 functions per intent
Module 4 (Fetcher) → NotionResult (per fetch)
   │
   ▼  returns NotionResult to Module 3
Module 3 (Router) → list[tuple[QueryIntent, NotionResult]]
   │
   ▼  paired list
Module 5 (Synthesizer) → BotResponse
   │
   ▼  BotResponse
Module 1 (Gateway) → formats & sends to Discord
```

**Inter-module handoff contracts**:

| From → To | Data structure |
|---|---|
| Module 1 → Module 2 | raw message text (str) + user_id, channel_id |
| Module 2 → Module 3 | `ParsedQuery` |
| Module 3 → Module 4 | function args (page_id, environment, etc.) — NOT a shared model |
| Module 4 → Module 3 | `NotionResult` |
| Module 3 → Module 5 | `list[tuple[QueryIntent, NotionResult]]` |
| Module 5 → Module 1 | `BotResponse` |

**If you need to add a field to any of these models, coordinate with the engineers on both sides of that handoff before changing `models.py`.**

---

## 6. Verification Checklist

Run this after completing Plan 0 to confirm the scaffold is correct:

```bash
# Confirm folder structure exists
find apps/bot/src -type d
find apps/bot/tests -type d

# Confirm Python packages install without errors
cd apps/bot
pip install -r requirements.txt

# Confirm models import cleanly
python -c "from src.models import ParsedQuery, NotionResult, BotResponse; print('OK')"

# Confirm config file is valid YAML
python -c "import yaml; yaml.safe_load(open('../../config/config.yaml')); print('OK')"
```

All four commands should complete without errors before any module work begins.

---

## 7. Open Questions

None — all decisions for project setup are finalized. If you hit an issue during setup, check:
1. Python version is 3.11 or higher (`python --version`)
2. `.env` file exists at the project root (not inside `apps/bot/`)
3. Virtual environment is activated before running pip commands
