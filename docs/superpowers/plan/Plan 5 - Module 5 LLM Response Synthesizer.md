# Plan 5 — Module 5: LLM Response Synthesizer
## Timedoor Project Assistant Bot

---

## 1. Overview

**What it does**: Receives the list of `(QueryIntent, NotionResult)` pairs from Module 3 and converts them into a single natural language `BotResponse`. Handles special cases (ambiguity, not-found, session reset, credentials) via templates without a Gemini call. Batches all remaining standard queries into one Gemini synthesis call via LangChain. Runs a separate Gemini extraction call for credential queries to strip sensitive fields before formatting.

**Input**: `list[tuple[QueryIntent, NotionResult]]` from Module 3 + conversation history from `ParsedQuery.history`.

**Output**: `BotResponse` (defined in `src/models.py`) — passed to Module 1 (Discord Gateway).

**Position in build order**: Built fifth, after Module 6, 4, 3, and 2. Module 1 (Discord Gateway) is the last module built and wires everything together.

**Depends on**: Module 6 (`get_config()`, loggers), LangChain (`langchain-google-genai`) for Gemini synthesis and credential extraction calls.

**Depended on by**: Module 1 (Discord Gateway).

---

## 2. Models Update — `src/models.py`

**Before writing any code in this module, update `src/models.py`** to add `history` to `ParsedQuery`. Coordinate with all engineers before merging.

```python
@dataclass
class ParsedQuery:
    questions: list[QueryIntent]
    session_key: str
    user_id: int
    channel_id: int
    history: list[dict] = field(default_factory=list)
    # Each dict: {"role": "user" | "assistant", "content": str}
    # Populated by Module 2 from SessionStore before returning ParsedQuery.
    # Used by Module 5 to inject conversation context into the synthesis prompt.
```

Also update **Plan 4's `parse_message()`** to populate `history` in the returned `ParsedQuery`:

```python
parsed = ParsedQuery(
    questions=questions,
    session_key=session_key,
    user_id=user_id,
    channel_id=channel_id,
    history=[{"role": h.role, "content": h.content} for h in store.get_history(session_key)],
)
```

---

## 3. File Structure

```
apps/bot/src/synthesizer/
├── __init__.py         ← exports synthesize_response
├── gemini.py           ← LangChain Gemini wrapper (synthesis + extraction calls)
├── prompt.py           ← prompt builder, Notion data formatter for synthesis
└── formatters.py       ← template responses: credential, not-found, ambiguity, session_reset

apps/bot/tests/integration/
└── test_synthesizer.py ← integration tests for this module
```

---

## 4. Implementation Steps

### Step 1 — Implement `src/synthesizer/gemini.py`

Uses LangChain's `ChatGoogleGenerativeAI` for all Gemini calls in this module. This is where LangChain's Gemini wrapper is used — as decided, LangChain wraps Gemini here but does not orchestrate routing.

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage
from src.config import get_config, get_error_logger


_llm: ChatGoogleGenerativeAI | None = None


def get_llm() -> ChatGoogleGenerativeAI:
    ...

async def call_gemini(system_prompt: str, user_prompt: str) -> str:
    ...

async def call_gemini_extract_credentials(raw_page_content: str) -> dict:
    ...
```

**`get_llm()`**:
- Returns a module-level singleton `ChatGoogleGenerativeAI` instance
- Initialized with `model=config.llm.model`, `temperature=config.llm.temperature`, `max_output_tokens=config.llm.max_output_tokens`, `google_api_key=config.llm.api_key`
- Created on first call; reused thereafter

**`call_gemini(system_prompt, user_prompt)`**:
- Calls `get_llm().ainvoke([SystemMessage(system_prompt), HumanMessage(user_prompt)])`
- Returns `response.content` (str)
- On exception: logs via `get_error_logger()` with the error message; raises the exception so the caller can return a `BotResponse(is_error=True)`

**`call_gemini_extract_credentials(raw_page_content)`**:
- Dedicated call for credential extraction — separate from the synthesis call for security
- Uses `get_llm().with_structured_output(schema)` to enforce JSON output
- Prompt instructs Gemini to extract ONLY `server_host` and `environment` fields
- Returns `{"server_host": str | None, "environment": str | None}`
- Sensitive fields (passwords, tokens, API keys) are never passed back — the LLM is instructed to omit them
- On failure: returns `{"server_host": None, "environment": None}` with an error log

**Credential extraction prompt**:
```
From the following Notion page content, extract ONLY two fields:
1. server_host: the server host address or URL (e.g. "api.example.com" or "https://...")
2. environment: the environment name (e.g. "Production", "Staging", "Development")

CRITICAL: Do NOT return any passwords, API keys, tokens, secret keys, or credentials.
If a field is not found in the content, return null for that field.

Return only JSON: {"server_host": "..." | null, "environment": "..." | null}

[PAGE CONTENT]
{raw_content}
```

---

### Step 2 — Implement `src/synthesizer/formatters.py`

Template-based responses that do NOT require a Gemini call. All templates respect the `language` parameter.

```python
def format_not_found(intent: QueryIntent, language: str) -> str:
    ...

def format_ambiguity(candidates: list[str], language: str) -> str:
    ...

def format_session_reset(language: str) -> str:
    ...

def format_credential_response(
    project_name: str,
    server_host: str | None,
    environment: str | None,
    notion_url: str | None,
    language: str,
) -> str:
    ...
```

**`format_not_found(intent, language)`**:
- Returns a friendly "data not found" message in the correct language
- Indonesian: `"Maaf, data untuk {project_name} tidak ditemukan di Notion."`
- English: `"Sorry, no data found for {project_name} in Notion."`
- If `project_name` is None: uses a generic "the requested project"

**`format_ambiguity(candidates, language)`**:
- Returns a clarification prompt listing the candidate project names
- Indonesian: `"Saya menemukan beberapa project yang cocok:\n1. ...\n2. ...\nProject mana yang dimaksud?"`
- English: `"I found multiple matching projects:\n1. ...\n2. ...\nWhich one did you mean?"`

**`format_session_reset(language)`**:
- Indonesian: `"Sesi percakapan sudah direset. Silakan mulai pertanyaan baru."`
- English: `"Conversation session has been reset. Feel free to start a new question."`

**`format_credential_response(project_name, server_host, environment, notion_url, language)`**:
- Applies the PRD's partial-reveal credential template
- Indonesian template:
  ```
  Berikut informasi server untuk {project_name}:

  Host / URL   : {server_host or "Tidak ditemukan"}
  Environment  : {environment or "Tidak diketahui"}

  Untuk credentials lengkap (password, token, API key):
  → {notion_url or "Cek langsung di Notion"}

  Sensitive fields tidak ditampilkan di Discord demi keamanan.
  ```
- English template:
  ```
  Server information for {project_name}:

  Host / URL   : {server_host or "Not found"}
  Environment  : {environment or "Unknown"}

  For full credentials (password, token, API key):
  → {notion_url or "Check Notion directly"}

  Sensitive fields are not shown in Discord for security.
  ```

---

### Step 3 — Implement `src/synthesizer/prompt.py`

```python
def build_system_prompt(language: str) -> str:
    ...

def build_user_prompt(
    results: list[tuple[QueryIntent, NotionResult]],
    history: list[dict],
) -> str:
    ...

def _format_history(history: list[dict]) -> str:
    ...

def _format_notion_data(results: list[tuple[QueryIntent, NotionResult]]) -> str:
    ...
```

**`build_system_prompt(language)`**:

```
You are Timedoor Project Assistant, an internal company bot.
Answer ONLY using the data provided in [RETRIEVED DATA].
Do NOT guess, invent, or infer information not present in the provided data.
If data for a question is null or missing, say so clearly — never make up an answer.
Respond in {language_instruction}.
If there are multiple questions, number your answers to match the question numbers.
Keep answers concise and factual.
```

Where `language_instruction` is `"Indonesian (Bahasa Indonesia)"` when `language=="id"`, else `"English"`.

**`build_user_prompt(results, history)`**:
- Calls `_format_history(history)` for the history section
- Calls `_format_notion_data(results)` for the data section
- Builds a numbered list of questions from `intent.raw_question`
- Returns the full user prompt string

**`_format_notion_data(results)`**:
- Converts each `(QueryIntent, NotionResult)` into a compact JSON-like entry
- Passes `result.data` as structured JSON, not raw page text (Cost Guard)
- Prefixes each entry with the question number for the LLM to correlate

Example output:
```
Question 1 (project_info — Inwan):
{"name": "Inwan (Orange Care)", "pm": "Cindy Felicia", "framework": "Flutter", "platform": "iOS & Android", "status": "Active"}

Question 2 (bug_query — Inwan):
{"total": 7, "by_status": {"Open": 4, "In Progress": 2, "Re-Opened": 1}, "environment": null}
```

**`_format_history(history)`**:
- Formats `list[dict]` into readable text
- Returns `"(no previous conversation)"` if empty

---

### Step 4 — Implement main flow in `src/synthesizer/__init__.py`

```python
from src.synthesizer.gemini import call_gemini, call_gemini_extract_credentials
from src.synthesizer.prompt import build_system_prompt, build_user_prompt
from src.synthesizer.formatters import (
    format_not_found, format_ambiguity,
    format_session_reset, format_credential_response,
)
from src.models import QueryIntent, NotionResult, BotResponse
from src.config import get_error_logger, get_latency_logger
import time


async def synthesize_response(
    results: list[tuple[QueryIntent, NotionResult]],
    history: list[dict],
) -> BotResponse:
    ...
```

**`synthesize_response(results, history)`** — full flow:

```
1. language = results[0][0].language if results else "id"
2. answers = [""] * len(results)
   standard_indices = []
   is_credential_response = False

3. Pass 1 — handle special cases (no Gemini call):
   for i, (intent, result) in enumerate(results):
     if intent.intent == "session_reset":
       answers[i] = format_session_reset(language)
     elif intent.is_ambiguous:
       answers[i] = format_ambiguity(intent.candidates, language)
     elif result.data is None:
       answers[i] = format_not_found(intent, language)
     elif intent.intent == "credential_query":
       extracted = await call_gemini_extract_credentials(result.data["content"])
       answers[i] = format_credential_response(
           project_name=intent.project_name,
           server_host=extracted["server_host"],
           environment=extracted["environment"],
           notion_url=result.notion_url,
           language=language,
       )
       is_credential_response = True
     else:
       standard_indices.append(i)

4. Pass 2 — batch all standard intents in ONE Gemini synthesis call:
   if standard_indices:
     standard_pairs = [results[i] for i in standard_indices]
     system_prompt = build_system_prompt(language)
     user_prompt = build_user_prompt(standard_pairs, history)
     start = time.perf_counter()
     raw_response = await call_gemini(system_prompt, user_prompt)
     duration_ms = int((time.perf_counter() - start) * 1000)
     get_latency_logger().info(
         "gemini_synthesis",
         extra={"duration_ms": duration_ms, "question_count": len(standard_pairs)},
     )
     # Split numbered response back into individual answers
     individual = _split_numbered_response(raw_response, len(standard_pairs))
     for i, answer in zip(standard_indices, individual):
       answers[i] = answer

5. Combine:
   if len(answers) == 1:
     content = answers[0]
   else:
     content = "\n\n".join(f"{i+1}. {a}" for i, a in enumerate(answers))

6. Return BotResponse(
     content=content,
     language=language,
     is_error=False,
     is_credential=is_credential_response,
   )
```

**Error handling**: Wrap the entire function body in try/except. On any unhandled exception, log via `get_error_logger()` and return:
```python
BotResponse(
    content="Maaf, terjadi kesalahan saat memproses pertanyaan Anda." if language == "id"
            else "Sorry, an error occurred while processing your question.",
    language=language,
    is_error=True,
    is_credential=False,
)
```

**`_split_numbered_response(raw_response, count)`** — internal helper:
- If `count == 1`: return `[raw_response.strip()]`
- If `count > 1`: split on `\n1.`, `\n2.`, etc. pattern and return individual parts
- If splitting fails or produces wrong count: return the full response as the first answer and empty strings for the rest — never raise an exception

---

## 5. Dependencies

| Package | Already in `requirements.txt` | Why used here |
|---|---|---|
| `langchain-google-genai` | Yes | `ChatGoogleGenerativeAI` Gemini wrapper for synthesis and extraction calls |
| `langchain` | Yes | `SystemMessage`, `HumanMessage` schema types |

No new packages needed.

---

## 6. Integration Points

**Called by Module 1 (Discord Gateway)**:

```python
from src.synthesizer import synthesize_response
from src.models import BotResponse

response: BotResponse = await synthesize_response(
    results=router_results,          # list[tuple[QueryIntent, NotionResult]] from Module 3
    history=parsed_query.history,    # list[dict] from ParsedQuery.history
)

# Module 1 checks response fields:
response.content        # str — send this to Discord
response.language       # "id" or "en"
response.is_error       # bool — use red embed color if True
response.is_credential  # bool — use yellow embed color if True
                        # (green embed color for all other successful responses)
```

**Consumes Module 3 output**:

Module 5 reads these `NotionResult` fields to determine rendering path:

| Condition | Rendering path |
|---|---|
| `result.data is None` and `source is None` | Project not found — `format_not_found()` |
| `result.data is None` and `source is not None` | Fetch attempted but empty — `format_not_found()` |
| `result.data == {"ambiguous": True, "candidates": [...]}` | Clarification needed — `format_ambiguity()` |
| `intent.intent == "credential_query"` and `result.data is not None` | Credential extraction + `format_credential_response()` |
| `intent.intent == "session_reset"` | `format_session_reset()` |
| Everything else | Standard synthesis via `call_gemini()` |

**Consumes Module 6 (Config & Observability)**:

```python
from src.config import get_config, get_error_logger, get_latency_logger

config = get_config()
# config.llm.model, config.llm.temperature, config.llm.max_output_tokens, config.llm.api_key

get_latency_logger().info("gemini_synthesis", extra={"duration_ms": ..., "question_count": ...})
get_error_logger().error("Gemini call failed", extra={"module": "synthesizer", ...})
```

---

## 7. Tests

**File**: `apps/bot/tests/integration/test_synthesizer.py`

All Gemini calls are mocked — no live LLM calls.

| # | Test | What is mocked | Pass condition |
|---|---|---|---|
| T1 | Single `project_info` query returns synthesized content | `call_gemini` returns mock answer | `BotResponse.content` equals mocked answer; `is_error=False` |
| T2 | Multi-question batches into one `call_gemini` call | `call_gemini` | `call_gemini` called exactly once regardless of question count |
| T3 | `credential_query` calls extraction, NOT synthesis | `call_gemini_extract_credentials` returns `{"server_host": "api.x.com", "environment": "Production"}` | `call_gemini` never called; `BotResponse.content` contains "api.x.com"; `is_credential=True` |
| T4 | `result.data is None` returns not-found without Gemini call | Nothing | `call_gemini` never called; content contains "not found" / "tidak ditemukan" |
| T5 | Ambiguous result returns clarification without Gemini call | Nothing | `call_gemini` never called; content contains candidate names |
| T6 | `session_reset` intent returns reset message without Gemini call | Nothing | `call_gemini` never called; content matches reset template |
| T7 | Indonesian query (`language="id"`) gets Indonesian system prompt | Capture system prompt passed to `call_gemini` | System prompt contains "Indonesian (Bahasa Indonesia)" |
| T8 | Mixed batch: one standard + one credential handled correctly | `call_gemini` + `call_gemini_extract_credentials` | `call_gemini` called once (for standard); `call_gemini_extract_credentials` called once (for credential); final content has both answers |
| T9 | Gemini synthesis failure returns `is_error=True` BotResponse | `call_gemini` raises exception | `BotResponse.is_error=True`; content is the error message template; no exception propagated |
| T10 | Latency log emitted after synthesis call | Capture `tab.latency` logger | Log entry has `duration_ms` and `question_count` fields |
| T11 | Hallucination guardrail: system prompt contains "do not guess" instruction | Capture system prompt | System prompt contains the guardrail instruction |
| T12 | Credential response never shows raw page content | `call_gemini_extract_credentials` returns `{"server_host": "api.x.com", "environment": "Staging"}` | `BotResponse.content` does not contain any key from `result.data["content"]` |

---

## 8. Open Questions

1. **`_split_numbered_response` parsing**: The strategy for splitting Gemini's numbered output back into individual answers depends on how consistently Gemini formats its responses. Test with real multi-question prompts before finalizing the regex/split pattern. If Gemini consistently uses `\n\n1.` style, a simple split works. If not, a more robust parser may be needed.

2. **Credential extraction failure UX**: If `call_gemini_extract_credentials` returns `{"server_host": None, "environment": None}` (extraction failed), the credential formatter shows "Not found" for both fields but still appends the Notion link. Confirm this is acceptable behavior — the user can always click the link to see the full page.
