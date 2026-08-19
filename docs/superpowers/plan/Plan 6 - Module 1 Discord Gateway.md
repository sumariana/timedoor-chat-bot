# Plan 6 — Module 1: Discord Gateway
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: The outermost layer of the bot. Connects to Discord, listens for @mentions and DMs, enforces channel rules and rate limits, orchestrates the full request pipeline (Parser → Router → Synthesizer), formats the `BotResponse` as a Discord embed, and sends it back. Also updates the session after each successful response.

**Input**: Discord message events (`on_message`) from the Discord WebSocket gateway.

**Output**: Discord embed messages sent to the originating channel or DM.

**Position in build order**: Built last — wires all modules (2, 3, 5) together into a running bot.

**Depends on**: All modules — Module 6 (config), Module 2 (parser), Module 3 (router), Module 5 (synthesizer).

**Depended on by**: Nothing. This is the entry point.

---

## 2. File Structure

```
apps/bot/src/gateway/
├── __init__.py         ← exports create_bot
├── client.py           ← discord.py bot setup, on_message handler, pipeline orchestration
├── filters.py          ← channel allowlist/denylist logic, DM detector, membership checker
├── formatters.py       ← Discord embed builder (green/yellow/red color coding)
└── rate_limiter.py     ← per-user rate limiter (in-memory, N queries per minute)

apps/bot/tests/integration/
└── test_gateway.py     ← integration tests for this module
```

---

## 3. Implementation Steps

### Step 1 — Implement `src/gateway/rate_limiter.py`

Built first — `client.py` depends on it.

```python
import time
from collections import defaultdict, deque
from src.config import get_config


class RateLimiter:
    def is_allowed(self, user_id: int) -> bool: ...
    def _cleanup_old_entries(self, user_id: int, window_start: float) -> None: ...


_limiter = RateLimiter()

def get_rate_limiter() -> RateLimiter:
    ...
```

**`RateLimiter`**:
- Stores a `deque` of timestamps per `user_id` — each entry is when that user made a request
- `is_allowed(user_id)`:
  1. Compute `window_start = time.time() - 60` (1-minute rolling window)
  2. Remove entries older than `window_start` from the deque
  3. If `len(deque) >= config.rate_limit.max_queries_per_user_per_minute`: return `False`
  4. Append `time.time()` to the deque and return `True`
- Uses `defaultdict(deque)` — no explicit initialization needed per user

---

### Step 2 — Implement `src/gateway/filters.py`

```python
import discord
from src.config import get_config


def is_channel_allowed(channel: discord.abc.Messageable) -> bool:
    ...

def is_dm(message: discord.Message) -> bool:
    ...

async def is_timedoor_member(user: discord.User, bot: discord.Client) -> bool:
    ...
```

**`is_channel_allowed(channel)`**:
- Gets `config.discord.allowed_channels` and `config.discord.denied_channels`
- If `allowed_channels` is non-empty: return `True` only if `str(channel.id)` is in the list (allowlist mode)
- If `denied_channels` is non-empty: return `True` only if `str(channel.id)` is NOT in the list (denylist mode)
- If both are empty: return `True` (bot responds everywhere)
- If both are non-empty: allowlist takes priority

**`is_dm(message)`**:
- Returns `True` if `isinstance(message.channel, discord.DMChannel)`

**`is_timedoor_member(user, bot)`**:
- Fetches the configured Timedoor guild via `bot.get_guild(int(config.discord.timedoor_server_id))`
- Calls `guild.fetch_member(user.id)` — returns the member object if found
- Returns `True` if member found, `False` if `discord.NotFound` is raised
- Used for DM access control — non-members are rejected before any Notion data is accessed

---

### Step 3 — Implement `src/gateway/formatters.py`

```python
import discord
from src.models import BotResponse


COLOUR_SUCCESS    = discord.Colour.green()
COLOUR_CREDENTIAL = discord.Colour.yellow()
COLOUR_ERROR      = discord.Colour.red()


def build_embed(response: BotResponse, project_name: str | None = None) -> discord.Embed:
    ...

def build_rate_limit_embed(language: str = "id") -> discord.Embed:
    ...

def build_dm_rejected_embed() -> discord.Embed:
    ...

def build_channel_denied_embed(language: str = "id") -> discord.Embed:
    ...
```

**`build_embed(response, project_name)`**:
- Selects colour based on response state:
  - `is_error=True` → `COLOUR_ERROR` (red)
  - `is_credential=True` → `COLOUR_CREDENTIAL` (yellow)
  - Otherwise → `COLOUR_SUCCESS` (green)
- Creates a `discord.Embed` with `description=response.content`
- Adds `title=f"Project: {project_name}"` if `project_name` is provided and response is not an error
- Keeps embed under Discord's 4096-character description limit — truncates with `"... (truncated)"` if needed

**`build_rate_limit_embed(language)`**:
- Red embed, fixed message
- Indonesian: `"Terlalu banyak pertanyaan. Coba lagi dalam 1 menit."`
- English: `"Too many requests. Please wait 1 minute before trying again."`

**`build_dm_rejected_embed()`**:
- Red embed
- Fixed message (always Indonesian since we can't detect language before processing):
  `"Maaf, bot ini hanya tersedia untuk anggota internal Timedoor. Silakan hubungi tim Timedoor jika kamu membutuhkan akses."`

**`build_channel_denied_embed(language)`**:
- Red embed: bot is not active in this channel
- Not sent to the user — this case is silently ignored (bot does not respond in disallowed channels)

---

### Step 4 — Implement `src/gateway/client.py`

The core of the module. Sets up the `discord.py` bot and the full request pipeline.

```python
import asyncio
import discord
from src.config import AppConfig, get_error_logger, get_latency_logger
from src.gateway.filters import is_channel_allowed, is_dm, is_timedoor_member
from src.gateway.formatters import (
    build_embed, build_rate_limit_embed, build_dm_rejected_embed,
)
from src.gateway.rate_limiter import get_rate_limiter
from src.parser import (
    parse_message, add_to_session, update_session_project,
    initialize_project_registry,
)
from src.router import route_query
from src.synthesizer import synthesize_response
import time


def create_bot(config: AppConfig) -> discord.Client:
    ...

async def _handle_message(message: discord.Message, bot: discord.Client) -> None:
    ...

async def _run_pipeline(message: discord.Message, bot: discord.Client) -> None:
    ...
```

**`create_bot(config)`**:
- Creates a `discord.Client` with `intents=discord.Intents.default()` + `message_content=True`
- Registers `on_ready` and `on_message` event handlers
- `on_ready`: logs bot username + calls `await initialize_project_registry()` to pre-load project names before accepting messages
- `on_message`: calls `_handle_message(message, bot)`
- Returns the configured client (does not start it — `main.py` calls `await bot.start(token)`)

**`_handle_message(message, bot)`** — pre-pipeline gate:

```
1. Ignore messages from the bot itself (message.author == bot.user)

2. Determine if message is a DM or a channel message:
   - DM: check config.discord.allow_dms
     - If allow_dms=False: ignore silently
     - If allow_dms=True: check is_timedoor_member(message.author, bot)
       - If not a member: send build_dm_rejected_embed(), stop
   - Channel: check if bot is @mentioned (bot.user in message.mentions)
     - If not @mentioned: ignore
     - Check is_channel_allowed(message.channel)
       - If not allowed: ignore silently

3. Check rate limit: get_rate_limiter().is_allowed(message.author.id)
   - If not allowed: reply with build_rate_limit_embed(), stop

4. Show typing indicator: async with message.channel.typing()

5. Call _run_pipeline(message, bot)
```

**`_run_pipeline(message, bot)`** — full request pipeline:

```
1. start_time = time.perf_counter()

2. parsed = await parse_message(
       message_text=message.content,
       user_id=message.author.id,
       channel_id=message.channel.id,
   )

3. results = await route_query(parsed)

4. response = await synthesize_response(
       results=results,
       history=parsed.history,
   )

5. resolved_project = _extract_resolved_project(results)

6. embed = build_embed(response, project_name=resolved_project)

7. await message.reply(embed=embed, mention_author=False)

8. If the request was NOT a session reset, persist to session:
   is_reset = any(intent.intent == "session_reset" for intent, _ in results)
   if not is_reset:
       add_to_session(
           user_id=message.author.id,
           channel_id=message.channel.id,
           user_message=message.content,
           bot_response=response.content,
       )
       # Only track last_project when the session is alive — reset explicitly clears it
       if resolved_project is not None:
           update_session_project(
               user_id=message.author.id,
               channel_id=message.channel.id,
               project_name=resolved_project,
           )

9. duration_ms = int((time.perf_counter() - start_time) * 1000)
    get_latency_logger().info(
        "request_complete",
        extra={
            "user_id": message.author.id,
            "duration_ms": duration_ms,
            "question_count": len(parsed.questions),
            "is_error": response.is_error,
        },
    )
```

On any exception in `_run_pipeline`: catch it, log via `get_error_logger()`, and send a generic error embed to the user — never let an unhandled exception silently drop the response.

**`_extract_resolved_project(results)`** — internal helper:
- Returns the first non-None `intent.project_name` from results where `intent.is_ambiguous=False`
- Returns `None` if all intents are ambiguous or project-less

---

### Step 5 — Export from `src/gateway/__init__.py`

```python
from src.gateway.client import create_bot
```

`main.py` only needs `create_bot`. All other gateway internals stay private.

---

## 4. Dependencies

No new packages required. All dependencies are already in `requirements.txt`.

| Package | Why |
|---|---|
| `discord.py` | Bot client, event system, embed formatting |

---

## 5. Integration Points

**`main.py` wires everything together**:

```python
import asyncio
import os
from dotenv import load_dotenv
from src.config import load_config, setup_logging
from src.gateway import create_bot

load_dotenv(dotenv_path="../../.env")

async def main() -> None:
    config = load_config(config_path="../../config/config.yaml")
    setup_logging(config)
    bot = create_bot(config)
    await bot.start(os.environ["DISCORD_BOT_TOKEN"])

if __name__ == "__main__":
    asyncio.run(main())
```

**Calls Module 2 (Query Parser)**:

```python
from src.parser import parse_message, add_to_session, update_session_project, initialize_project_registry

await initialize_project_registry()          # once at startup (on_ready)
parsed = await parse_message(text, uid, cid) # per message
add_to_session(uid, cid, user_msg, bot_msg)  # after reply
update_session_project(uid, cid, project)    # after reply if project resolved
```

**Calls Module 3 (Notion Data Router)**:

```python
from src.router import route_query

results = await route_query(parsed)
```

**Calls Module 5 (LLM Response Synthesizer)**:

```python
from src.synthesizer import synthesize_response

response = await synthesize_response(results=results, history=parsed.history)
```

---

## 6. Tests

**File**: `apps/bot/tests/integration/test_gateway.py`

All downstream modules (parser, router, synthesizer) are mocked. Tests verify gateway behavior only.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | Bot ignores its own messages | Nothing | `parse_message` never called when `message.author == bot.user` |
| T2 | Channel message without @mention is ignored | Nothing | `parse_message` never called |
| T3 | Message in denied channel is ignored silently | `is_channel_allowed` returns `False` | No reply sent; `parse_message` never called |
| T4 | Message in allowed channel triggers pipeline | All downstream modules | `parse_message`, `route_query`, `synthesize_response` each called once |
| T5 | Rate limit exceeded returns rate limit embed | `get_rate_limiter().is_allowed` returns `False` | Reply contains rate limit embed; `parse_message` never called |
| T6 | DM from Timedoor member processes normally | `is_timedoor_member` returns `True`; all downstream | Full pipeline runs; response sent as DM reply |
| T7 | DM from non-Timedoor member returns rejection embed | `is_timedoor_member` returns `False` | Rejection embed sent; `parse_message` never called |
| T8 | DMs disabled in config — DM is ignored | `config.discord.allow_dms = False` | No reply sent; `parse_message` never called |
| T9 | `is_error=True` response uses red embed | `synthesize_response` returns `BotResponse(is_error=True)` | Sent embed colour is red |
| T10 | `is_credential=True` response uses yellow embed | `synthesize_response` returns `BotResponse(is_credential=True)` | Sent embed colour is yellow |
| T11 | Successful response uses green embed | `synthesize_response` returns standard `BotResponse` | Sent embed colour is green |
| T12 | Session updated after successful reply | `add_to_session` + `update_session_project` | Both functions called with correct arguments after reply is sent |
| T13 | Pipeline exception sends error embed, does not raise | `route_query` raises an exception | Error embed sent to user; exception does not propagate |
| T14 | End-to-end latency logged after each request | Capture `tab.latency` logger | Log entry has `duration_ms`, `user_id`, `question_count`, `is_error` |
| T15 | `session_reset` response does NOT re-populate session | `synthesize_response` returns response for `session_reset` intent | `add_to_session` and `update_session_project` never called after reply is sent |

---

## 7. Open Questions

None — all decisions for this module are settled. The only pre-coding verification needed:

1. Confirm `discord.Intents.default()` is sufficient or if `discord.Intents.all()` is needed for DM membership checks in your Discord server configuration. Some servers require `GUILD_MEMBERS` intent for `guild.fetch_member()` to work — this must be enabled in the Discord Developer Portal for your bot application.
