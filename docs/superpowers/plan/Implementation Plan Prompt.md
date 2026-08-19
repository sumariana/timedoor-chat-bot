# Implementation Plan Prompt — Timedoor Project Assistant Bot

## Instructions

Write an implementation plan for **Module [MODULE_NUMBER] — [MODULE_NAME]** of the Timedoor Project Assistant Bot. Follow the format and constraints below exactly. Do not propose architecture changes — all decisions are finalized.

---

## Project Context

**What it is**: An internal Discord chatbot that answers natural language queries about Timedoor's Notion workspace. Team members ask questions like "siapa PM project Inwan?" or "berapa bug open di staging mobile?" and the bot fetches the answer from Notion and responds via Gemini 2.0 Flash.

**Language**: Python 3.11+

**Finalized Tech Stack**:
- Discord interface: `discord.py`
- LLM: Gemini 2.0 Flash via `google-generativeai` SDK (NOT through LangChain)
- Notion structured data: Notion official Python client (`notion-client`)
- Notion unstructured data: Notion MCP server via `mcp` Python SDK (LangChain is used only as a thin adapter for this MCP connection if needed — it does NOT orchestrate routing)
- AI Orchestration: LangChain used minimally — only for MCP connection, not for routing logic
- Cache: in-memory dict with TTL (MVP); Redis in Phase 2
- Config: YAML file
- API server: FastAPI (production only, not demo phase)
- Testing: `pytest`
- Hosting: Railway (production), local machine (demo)

**Intent Classification**: LLM-based — a single structured Gemini call classifies intent, extracts project name, detects language, and splits multi-questions. Returns JSON. No regex/keyword rules.

**Intents**: `project_info`, `bug_query`, `bug_query_env`, `version_query`, `credential_query`, `doc_link_query`, `status_query`, `unknown`

**Notion Data Tiers**:
- Tier 1 (Notion API, 30min cache): project properties — Status, PM, Platform, Framework, Dates, URLs
- Tier 2 (Notion API multi-hop, 5–15min cache): Bug List sub-DB, Change Log sub-DB
- Tier 3 (Notion MCP, no cache): Credentials page, Docs, nested pages

**Credential policy**: host/URL shown in Discord; passwords/tokens/API keys never shown — Notion link appended instead.

**Session**: In-memory, keyed by `user_id + channel_id`, last 3–5 exchanges, 30min timeout, manual reset via `@bot reset`.

**DM support**: Enabled via config flag. Server membership check enforced before processing any DM.

---

## Monorepo Folder Structure

```
timedoor-project-assistant/
├── apps/
│   ├── bot/
│   │   ├── src/
│   │   │   ├── gateway/        ← Module 1
│   │   │   ├── parser/         ← Module 2
│   │   │   ├── router/         ← Module 3
│   │   │   ├── fetcher/        ← Module 4
│   │   │   ├── synthesizer/    ← Module 5
│   │   │   └── config/         ← Module 6
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── e2e/
│   │   ├── main.py
│   │   └── requirements.txt
│   └── api/                    ← Phase 2 placeholder, empty for now
├── config/
│   └── config.yaml
└── .env
```

---

## Module Build Order (for context — do not change)

| Order | Module |
|---|---|
| 1st | Module 6 — Config & Observability |
| 2nd | Module 4 — Data Fetcher |
| 3rd | Module 3 — Notion Data Router |
| 4th | Module 2 — Query Parser |
| 5th | Module 5 — LLM Response Synthesizer |
| 6th | Module 1 — Discord Gateway |

---

## PRD Module Reference

### Module 1 — Discord Gateway
Sub-components: Bot Auth & Connection, Channel Allow/Deny Filter, @Mention Event Listener, Typing Indicator, Response Formatter (Discord Embeds — green/red/yellow), Rate Limiter, Error Messenger, DM Channel Detector, Server Membership Verifier.

### Module 2 — Query Parser
Sub-components: 2a Session Manager (in-memory, `user_id+channel_id` key, 30min timeout), 2b Intent Classifier (LLM-based, returns JSON), 2c Entity Extractor & Fuzzy Matcher (code-side, after LLM extracts raw name), 2d Multi-Question Splitter (handled inside LLM call), 2e Language Detector (handled inside LLM call).

### Module 3 — Notion Data Router
Sub-components: Workspace DB Registry, Route Decision Engine (intent → tier), API Fast Path, MCP Fallback, Multi-hop Coordinator (Project DB → Page ID → Sub-DB), Property Name Normalizer, Null Fallback.

Routing rules:
- `project_info`, `status_query` → Tier 1
- `bug_query`, `bug_query_env`, `version_query` → Tier 2
- `credential_query` → Tier 3
- `doc_link_query` → Tier 2 first, MCP fallback
- `unknown` → graceful response, no Notion call

### Module 4 — Data Fetcher
Sub-components: 4a Notion API Client (project search, property fetch, bug count, changelog), 4b Notion MCP Client (workspace search, page navigator, content reader, credential extractor), 4c Cache Layer (in-memory dict, TTL per tier).

Cache TTLs: project properties 30min, bug counts 5min, changelog 15min, credentials no cache, doc links 60min.

### Module 5 — LLM Response Synthesizer
Sub-components: Prompt Builder, Multi-answer Formatter, Language Instruction, Hallucination Guardrail, Credential Formatter, Not Found Handler, Cost Guard (pass structured JSON not raw page dumps).

### Module 6 — Configuration & Observability
Sub-components: Channel Config Manager, Notion DB Registry, LLM Config, Cache Config, Response Latency Logger, Error Tracker, Query Audit Log, Health Check Endpoint (production only).

---

## Required Plan Format

Write the plan using exactly this structure:

### 1. Overview
What this module does, what it receives as input, what it returns as output, and which other modules it depends on or is depended on by.

### 2. File Structure
List every file to be created inside `apps/bot/src/[module_folder]/` and `apps/bot/tests/`. One line per file with a short description of what it contains.

### 3. Implementation Steps
Numbered steps in the order they should be coded. Each step must include:
- What to implement (class name, function name, or file)
- The function signature(s) — include type hints
- A 1–2 sentence description of what it does
- Any constraints or edge cases to handle

### 4. Dependencies
List all external packages this module needs (add to `requirements.txt`). For each: package name, version pin or `latest`, and why it's needed.

### 5. Integration Points
How this module connects to adjacent modules. Include the exact function calls or data structures passed between modules.

### 6. Tests
List the integration tests to write in `apps/bot/tests/integration/`. For each test: what it tests, what is mocked, and what the pass condition is.

### 7. Open Questions
Any decisions not yet made that the implementing engineer must resolve before starting. Keep this section short — only genuine blockers.

---

## How to Use This Prompt

1. Replace `[MODULE_NUMBER]` and `[MODULE_NAME]` at the top with the module you are assigned.
2. Paste the entire prompt into Claude (claude.ai or Claude Code).
3. Submit your plan for review before writing any code.

**Plans can be written in any order — you do not need to follow the build order.**
The build order below only applies when coding starts, not when writing plans.

Once all plans are submitted, the lead engineer will compare Section 5 (Integration Points) across all plans and resolve any mismatches before coding begins.

**Coding must follow this build order:**

| Order | Module |
|---|---|
| 1st | Module 6 — Config & Observability |
| 2nd | Module 4 — Data Fetcher |
| 3rd | Module 3 — Notion Data Router |
| 4th | Module 2 — Query Parser |
| 5th | Module 5 — LLM Response Synthesizer |
| 6th | Module 1 — Discord Gateway |

**Module assignments:**

| Module | Engineer |
|---|---|
| Module 3 — Notion Data Router | |
| Module 4 — Data Fetcher | |
| Module 5 — LLM Response Synthesizer | |
| Module 6 — Config & Observability | |

> Plan 0 (Project Setup) will be written separately by the lead engineer and shared before coding starts.
> Fill in engineer names in the table above before distributing this file.

---

## Claude Code CLI — Ready-to-Use Prompts

Open your terminal, navigate to the project root, and paste the prompt for your assigned module directly into Claude Code CLI.

**Plan 1 — Module 6 (Config & Observability)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 6 — Config & Observability. This is Plan 1 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 1 - Module 6 Config and Observability.md
```

**Plan 2 — Module 4 (Data Fetcher)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 4 — Data Fetcher. This is Plan 2 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 2 - Module 4 Data Fetcher.md
```

**Plan 3 — Module 3 (Notion Data Router)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 3 — Notion Data Router. This is Plan 3 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 3 - Module 3 Notion Data Router.md
```

**Plan 4 — Module 2 (Query Parser)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 2 — Query Parser. This is Plan 4 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 4 - Module 2 Query Parser.md
```

**Plan 5 — Module 5 (LLM Response Synthesizer)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 5 — LLM Response Synthesizer. This is Plan 5 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 5 - Module 5 LLM Response Synthesizer.md
```

**Plan 6 — Module 1 (Discord Gateway)**
```
Read @docs/superpowers/plan/Implementation Plan Prompt.md and also read @docs/superpowers/specs/PRD.md for full context.

Using the format defined in the Implementation Plan Prompt, write an implementation plan for Module 1 — Discord Gateway. This is Plan 6 in our plan numbering sequence.

Save the output to docs/superpowers/plan/Plan 6 - Module 1 Discord Gateway.md
```
