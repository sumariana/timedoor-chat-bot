# Module Breakdown
## Timedoor Project Assistant Bot

---

## Module 1 — Discord Gateway
- Bot authentication & persistent connection to Discord
- Channel allow/deny filter (backend-configurable, no redeploy needed)
- @mention event listener & message extractor
- "Bot is typing…" indicator while processing
- Response formatter (Discord Embeds with color coding)
- Rate limiter — prevent spam queries per user
- User-friendly error messages (timeout, not found, API failure)

---

## Module 2 — Query Parser

### 2a. Session Manager
- Stores last 3–5 message exchanges per user per channel
- Session resets after 30 minutes of inactivity
- Injects conversation history into every LLM prompt
- Supports manual reset via `@bot reset` command

### 2b. Intent Classifier
- Classifies each question into one of these intents:
  - `project_info` — tech stack, PM, status, platform
  - `bug_query` — open bug count (all environments)
  - `bug_query_env` — bug count for a specific environment
  - `version_query` — latest version from changelog
  - `credential_query` — server host/URL + Notion link
  - `doc_link_query` — design link, drive link, docs
  - `status_query` — current project status
  - `unknown` — graceful fallback response

### 2c. Entity Extractor & Fuzzy Matcher
- Extracts project name from user query
- Fuzzy matching handles typos and shorthand ("inwan", "orange care", "Inwan OC")
- Asks for clarification if multiple projects match
- Inherits project context from session history if not mentioned

### 2d. Multi-Question Splitter
- Detects numbered lists or comma-separated questions in one message
- Splits into individual query intents
- Shares project context across all sub-questions
- Batches all sub-queries into a single LLM synthesis call

### 2e. Language Detector
- Detects message language (Indonesian or English)
- Bot always responds in the same language as the user's query

---

## Module 3 — Notion Data Router
- Workspace database registry — maps each team to their Notion Database ID
- Routes each intent to the correct data source:
  - **Tier 1** → Notion API (project properties — fast, cached)
  - **Tier 2** → Notion API multi-hop (Bug List, Change Log sub-databases)
  - **Tier 3** → Notion MCP (credentials, docs, unstructured pages — slower)
- Property name normalizer — maps variant names to one concept ("Framework", "Tech Stack", "Stack" → same)
- Falls back to MCP if API returns empty or null
- Returns explicit "not found" signal if both paths fail

---

## Module 4 — Data Fetcher

### 4a. Notion API Client
- Project property fetcher (Status, PM, Platform, Framework, Dates, URLs)
- Bug List fetcher — count by Status, with optional environment filter
- Change Log fetcher — retrieves latest release entry sorted by date

### 4b. Notion MCP Client
- Workspace search by project name keyword
- Page navigator — finds child pages (Credentials, Docs, Notes)
- Page content reader — reads free-form text blocks
- Credential extractor — pulls server host/URL only; suppresses passwords & tokens

### 4c. Cache Layer
| Data | Cache Duration |
|---|---|
| Project properties | 30 minutes |
| Bug counts | 5 minutes |
| Change Log | 15 minutes |
| Credentials | No cache (always fresh) |
| Doc links | 60 minutes |

---

## Module 5 — LLM Response Synthesizer
- Prompt builder — combines system prompt + history + retrieved data + user question
- Multi-answer formatter — numbered output matching the user's numbered questions
- Language instruction — LLM responds in the user's detected language
- Hallucination guardrail — LLM only uses retrieved data, never invents answers
- "Data not found" handler — friendly message when Notion data is missing
- Credential formatter — shows host/URL + Notion link + security note; never exposes passwords
- Token optimizer — passes structured JSON, not raw page dumps, to minimize LLM cost

---

## Module 6 — Configuration & Observability
- Channel config manager — YAML file to set allowed/denied Discord channel IDs
- Notion DB registry — config file to add new team databases without code changes
- LLM settings — model, temperature, max token cap
- Cache TTL settings — configurable per data type
- Response latency logger — tracks response time per query type
- Error tracker — logs Notion API, MCP, and LLM failures with context
- Query audit log — records who asked what and when (no credential content logged)
- Health check endpoint (`/health`) — verifies Discord, Notion, and LLM connectivity
