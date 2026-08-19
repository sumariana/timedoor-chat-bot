# Plan 1 — Module 6: Config & Observability
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: Loads all runtime configuration from `config/config.yaml` and `.env`, exposes a typed `AppConfig` object to every other module, and sets up three logging channels (latency, errors, audit).

**Input**: `config/config.yaml` (runtime settings) + `.env` (secrets)

**Output**: `AppConfig` singleton — a structured, typed Python object. All other modules import and call `get_config()` to access settings.

**Position in build order**: Built first — every other module depends on this one. Nothing else can be implemented until `load_config()` and the three loggers exist.

**Depends on**: Nothing.

**Depended on by**: All modules (1–5).

---

## 2. File Structure

```
apps/bot/src/config/
├── __init__.py          ← exports load_config, get_config, and the three logger getters
├── models.py            ← typed dataclass definitions for AppConfig and sub-configs
├── loader.py            ← reads config.yaml + .env, builds and caches AppConfig
└── logging.py           ← sets up latency logger, error tracker, and audit log

apps/bot/tests/integration/
└── test_config.py       ← integration tests for this module
```

---

## 3. Implementation Steps

### Step 1 — Define config models in `src/config/models.py`

Typed dataclasses that map 1:1 to the structure of `config/config.yaml`. All secrets (tokens, API keys) are injected from environment variables by the loader — they do not appear in the YAML file.

```python
from dataclasses import dataclass


@dataclass
class DiscordConfig:
    allowed_channels: list[str]
    denied_channels: list[str]
    allow_dms: bool
    dm_require_server_membership: bool
    timedoor_server_id: str
    token: str                          # injected from DISCORD_BOT_TOKEN env var


@dataclass
class NotionDatabases:
    mobile_team: str
    web_team: str
    backend_team: str


@dataclass
class NotionConfig:
    databases: NotionDatabases
    api_token: str                      # injected from NOTION_API_TOKEN env var


@dataclass
class SessionConfig:
    max_history: int
    timeout_minutes: int


@dataclass
class CacheConfig:
    project_properties_ttl: int         # seconds
    bug_counts_ttl: int
    changelog_ttl: int
    doc_links_ttl: int
    # credentials: no TTL — always fetched fresh, never cached


@dataclass
class LLMConfig:
    model: str
    temperature: float
    max_output_tokens: int
    api_key: str                        # injected from GEMINI_API_KEY env var


@dataclass
class RateLimitConfig:
    max_queries_per_user_per_minute: int


@dataclass
class AppConfig:
    discord: DiscordConfig
    notion: NotionConfig
    session: SessionConfig
    cache: CacheConfig
    llm: LLMConfig
    rate_limit: RateLimitConfig
```

**Constraints**:
- No defaults on required fields — a missing value must raise an error immediately at startup, not silently use a wrong value.
- Secrets are never stored in YAML. If a required env var is missing, raise `EnvironmentError` with a clear message naming the missing variable.

---

### Step 2 — Implement `src/config/loader.py`

```python
import os
import yaml
from dotenv import load_dotenv
from src.config.models import (
    AppConfig, DiscordConfig, NotionConfig, NotionDatabases,
    SessionConfig, CacheConfig, LLMConfig, RateLimitConfig
)

_config: AppConfig | None = None


def load_config(config_path: str = "../../config/config.yaml") -> AppConfig:
    ...

def get_config() -> AppConfig:
    ...
```

**`load_config(config_path)`**:
- Calls `load_dotenv()` to load `.env` into environment
- Reads and parses the YAML file at `config_path`
- Pulls secrets from environment variables: `DISCORD_BOT_TOKEN`, `NOTION_API_TOKEN`, `GEMINI_API_KEY`
- Raises `EnvironmentError` if any of the three required env vars are missing, with a message naming the missing variable
- Builds and returns `AppConfig` by mapping YAML keys to dataclass fields
- Caches the result in the module-level `_config` variable so subsequent calls are instant

**`get_config()`**:
- Returns the cached `_config`
- Raises `RuntimeError` if called before `load_config()` — prevents silent failures if a module forgets to initialize

**Edge cases**:
- YAML file not found → raise `FileNotFoundError` with the resolved path in the message
- YAML is malformed → let `yaml.YAMLError` propagate with its original message
- A required YAML key is missing (e.g., `notion.databases.mobile_team`) → raise `KeyError` with the missing key path

---

### Step 3 — Implement `src/config/logging.py`

Three named loggers, each writing to its own log channel. All use Python's built-in `logging` module — no external logging library needed for MVP.

```python
import logging
from src.config.models import AppConfig


def setup_logging(config: AppConfig) -> None:
    ...

def get_latency_logger() -> logging.Logger:
    ...

def get_error_logger() -> logging.Logger:
    ...

def get_audit_logger() -> logging.Logger:
    ...
```

**`setup_logging(config)`**:
- Must be called once at startup, immediately after `load_config()`
- Configures three named loggers:

| Logger name | Purpose | Log fields |
|---|---|---|
| `tab.latency` | Response time per query | timestamp, intent, project_name, duration_ms, source (api/mcp) |
| `tab.errors` | API/LLM failures | timestamp, error_type, module, message, query_context |
| `tab.audit` | Who asked what and when | timestamp, user_id, channel_id, intent, project_name |

- Demo phase: all three log to console (`StreamHandler`)
- Production phase: log to console (Railway captures stdout)
- Log format: `%(asctime)s [%(name)s] %(levelname)s — %(message)s`

**`get_latency_logger()` / `get_error_logger()` / `get_audit_logger()`**:
- Return the corresponding named logger
- Raise `RuntimeError` if `setup_logging()` has not been called yet

**Constraint — audit logger**:
The audit log must never contain credential content. When logging a `credential_query` intent, log only the intent name and project name — never the fetched data. This is enforced by only logging the `QueryIntent` fields (from `src/models.py`), not `NotionResult`.

---

### Step 4 — Export from `src/config/__init__.py`

```python
from src.config.loader import load_config, get_config
from src.config.logging import setup_logging, get_latency_logger, get_error_logger, get_audit_logger
```

All other modules import from `src.config` directly:
```python
from src.config import get_config, get_error_logger
```

---

## 4. Dependencies

No new packages required beyond what is already in `requirements.txt`.

| Package | Already in requirements.txt | Why used here |
|---|---|---|
| `PyYAML` | Yes | Parse `config/config.yaml` |
| `python-dotenv` | Yes | Load `.env` into environment |
| `logging` | Python stdlib | Three log channels |

---

## 5. Integration Points

All modules consume this module. The two functions they call are:

**`get_config() -> AppConfig`** — used by every module to read settings:

```python
# Example usage in Module 4 (Data Fetcher)
from src.config import get_config

config = get_config()
ttl = config.cache.bug_counts_ttl
token = config.notion.api_token
```

**`get_error_logger() / get_latency_logger() / get_audit_logger()`** — used by modules to write logs:

```python
# Example usage in Module 3 (Router)
from src.config import get_error_logger

logger = get_error_logger()
logger.error("Notion API returned null", extra={"module": "router", "project": "Inwan"})
```

**`main.py` initialization sequence** — must call both functions in this order before starting the bot:

```python
from src.config import load_config, setup_logging

config = load_config(config_path="../../config/config.yaml")
setup_logging(config)
# then start the bot
```

---

## 6. Tests

**File**: `apps/bot/tests/integration/test_config.py`

All tests use a temporary test config file and test `.env` values — never the real `config.yaml` or production secrets.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | Valid config loads without error | Nothing — reads a fixture `config.yaml` | `AppConfig` object returned; all fields populated with correct types |
| T2 | Missing env var raises clear error | Remove one env var (e.g., `DISCORD_BOT_TOKEN`) from test environment | `EnvironmentError` raised; message names the missing variable |
| T3 | Missing YAML file raises FileNotFoundError | Point `load_config()` at a non-existent path | `FileNotFoundError` raised; message includes the attempted path |
| T4 | `get_config()` before `load_config()` raises RuntimeError | Nothing | `RuntimeError` raised with a message indicating initialization is required |
| T5 | Cache TTL values load as integers, not strings | Nothing | `config.cache.bug_counts_ttl` equals `300` (int), not `"300"` (str) |
| T6 | `get_error_logger()` before `setup_logging()` raises RuntimeError | Nothing | `RuntimeError` raised |
| T7 | All three loggers write without error after setup | StreamHandler output captured | Log entries appear in output; no exception raised |

---

## 7. Open Questions

None — all decisions for this module are settled. The only thing to confirm before coding: make sure the `.env` file exists at the project root with all three required keys filled in, otherwise T2 will fail to isolate correctly if the real env var happens to be set in the shell.
