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
    is_ambiguous: bool = False
    candidates: list[str] = field(default_factory=list)


@dataclass
class ParsedQuery:
    questions: list[QueryIntent]
    session_key: str                    # f"user:{user_id}_channel:{channel_id}"
    user_id: int
    channel_id: int
    history: list[dict] = field(default_factory=list)
    # Each dict: {"role": "user" | "assistant", "content": str}
    # Populated by Module 2 and used for synthesis context.



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


# ── Output of Module 5 (LLM Synthesizer) → input to Module 1 (Gateway) ───────

@dataclass
class BotResponse:
    content: str                        # final text to send to Discord
    language: str                       # "id" or "en"
    is_error: bool = False              # True if bot is reporting a failure
    is_credential: bool = False         # True if credential partial-reveal template used
