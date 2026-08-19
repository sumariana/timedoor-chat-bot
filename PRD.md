# Product Requirements Document
## Timedoor Project Assistant Bot

---

**Document Version** : 1.3  
**Date**             : August 18, 2026  
**Author**           : Timedoor Internal  
**Project Type**     : Internal Business Improvement  
**Status**           : Draft — Ready for Review  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [Users & Stakeholders](#4-users--stakeholders)
5. [System Architecture Overview](#5-system-architecture-overview)
6. [Notion Data Classification](#6-notion-data-classification)
7. [Module Breakdown](#7-module-breakdown)
8. [Query Types & Behavior Examples](#8-query-types--behavior-examples)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Tech Stack](#10-tech-stack)
11. [Out of Scope (MVP)](#11-out-of-scope-mvp)
12. [MVP Success Criteria](#12-mvp-success-criteria)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Pre-Launch Dependencies](#14-pre-launch-dependencies)
15. [Future Phases](#15-future-phases)
16. [Testing Strategy](#16-testing-strategy)

---

## 1. Executive Summary

Timedoor Project Assistant Bot is an AI-powered Discord chatbot that serves as a conversational interface to Timedoor's Notion workspace. Team members across all departments — PM, Developer, QA, CS, and Sales — can query project information directly inside Discord using natural language, in both Indonesian and English, without manually navigating Notion.

The bot connects to Notion using a hybrid approach: structured database properties are fetched via the Notion API for speed and accuracy, while unstructured or inconsistently organized content is handled via the Notion MCP (Model Context Protocol), allowing the AI to navigate and read free-form pages intelligently.

---

## 2. Problem Statement

Project information at Timedoor is distributed across multiple Notion workspaces and pages per team (Mobile, Web, Backend). Team members frequently need to look up:

- Which tech stack or framework a project uses
- Who the current Project Manager is
- How many open bugs exist and their severity
- Server host addresses for a project
- Latest release version from the changelog

Currently this requires manually navigating Notion, knowing which team's workspace to look in, and often asking a colleague. This creates communication bottlenecks, slows down issue resolution, and delays client responses.

**The core pain**: information exists in Notion, but reaching it costs more time than it should.

---

## 3. Solution Overview

The bot listens for @mentions in configured Discord channels, and also accepts queries via **Direct Message (DM)**. When a user asks a question — or multiple questions at once — the bot:

1. Parses the message and identifies one or more query intents
2. Matches the referenced project name (with fuzzy matching for typos/shorthand)
3. Routes each query to the appropriate Notion data source (API or MCP)
4. Fetches the relevant data
5. Synthesizes a clear, numbered response via Gemini 2.0 Flash
6. Delivers the response in the same language as the user's query (Indonesian or English)

The bot maintains short-term conversation context (last 3–5 exchanges per user per channel) so follow-up questions resolve naturally without repeating the project name.

**Credential queries** are handled with a partial reveal policy: the bot surfaces non-sensitive fields (server host, URL) and appends a direct link to the full Notion credentials page. Raw passwords, tokens, and API keys are never displayed in Discord.

---

## 4. Users & Stakeholders

### Primary Users
| Role | Primary Use Cases |
|---|---|
| Project Manager (PM) | Check project status, PM assignment, release dates |
| Developer | Tech stack, server host, latest version, bug count |
| QA | Open bug count by environment, priority, or status |
| CS (Customer Support) | Project status, app store URLs, short description |
| Sales | Project category, platform, current status |

### Stakeholders
| Stakeholder | Interest |
|---|---|
| PM Leader | Productivity gain, reduced internal interruptions |
| Sparta Training Program Leads | Knowledge accessibility for new team members |

---

## 5. System Architecture Overview

```
Discord Server (Internal Only)
        │
        │ @mention event
        ▼
┌──────────────────────────────────────────────────────────┐
│                    Discord Gateway                        │
│         Channel filter → Rate limiter → Parser trigger   │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│                    Query Parser                           │
│    Session history → Intent classify → Entity extract    │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│                  Notion Data Router                       │
│    Structured? → Notion API    Unstructured? → MCP       │
└────────┬──────────────────────────────┬──────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐           ┌─────────────────────────┐
│   Notion API    │           │     Notion MCP Server   │
│ (fast, cached)  │           │ (LLM-navigated, slower) │
└─────────────────┘           └─────────────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        ▼
┌──────────────────────────────────────────────────────────┐
│               LLM Response Synthesizer                   │
│         Gemini 2.0 Flash — bilingual output              │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
            Discord Response
         (embed, numbered, formatted)
```

---

## 6. Notion Data Classification

Notion data is classified into three tiers that determine fetch strategy and expected response time.

### Tier 1 — Structured Database Properties
**Source**: Notion Database API  
**Response time**: Fast (2–4 seconds)  
**Accuracy**: 90–95%  
**Cacheable**: Yes

Examples:
- Project Name, Status, Platform, Category
- Project Manager (person property)
- Framework / Tech Stack
- Language, Dates, App Store URLs
- Firebase Status, Sentry, Maintenance Status

### Tier 2 — Structured Sub-Databases
**Source**: Notion Database API (multi-hop: Project Page → Sub-DB)  
**Response time**: Medium (3–6 seconds)  
**Accuracy**: 85–95%  
**Cacheable**: Yes (short TTL)

Examples:
- Bug List (count by Status, Priority, Environment)
- Change Log (latest version, recent releases)

### Tier 3 — Unstructured / Nested Pages
**Source**: Notion MCP (LLM-navigated page reading)  
**Response time**: Slow (8–15 seconds)  
**Accuracy**: 70–85% (depends on page content quality)  
**Cacheable**: No (credentials always fresh)

Examples:
- Credentials page (server host/URL extracted; full link returned)
- Design docs, Drive links
- Meeting notes, Maintenance notes
- QA files, Developer checklists

---

## 7. Module Breakdown

### Module 1 — Discord Gateway

**Purpose**: Manage the bot's connection to Discord, filter incoming events, and deliver responses.

**Sub-components**:

| Sub-component | Description |
|---|---|
| Bot Auth & Connection | Authenticate with Discord API using bot token; maintain persistent WebSocket connection |
| Channel Allow/Deny Filter | Check incoming message channel against backend-configured allowlist/denylist before processing |
| @Mention Event Listener | Detect when bot is @mentioned; extract message content for processing |
| Typing Indicator | Show "Bot is typing…" in Discord while processing (improves perceived responsiveness) |
| Response Formatter | Format bot output as Discord Embeds with color coding (green = success, red = error, yellow = partial result) |
| Ephemeral Handler | Future: deliver ephemeral responses for slash commands (Phase 2) |
| Rate Limiter | Prevent spam; limit to N queries per user per minute |
| Error Messenger | Return user-friendly error messages for timeouts, Notion API failures, and unknown queries |
| DM Channel Detector | Detect when a message arrives via `DMChannel` instead of a server text channel; route to DM handling flow |
| Server Membership Verifier | For DM messages, verify the sender is a member of the configured Timedoor Discord server; reject with a friendly message if not |

**Channel Configuration Behavior**:
- Admin sets allowed or denied channel IDs in backend config file
- Allowlist mode: bot only responds in listed channels
- Denylist mode: bot responds everywhere except listed channels
- No code redeploy required for channel changes

**DM Configuration Behavior**:
- DM access is toggled via `allow_dms` flag in backend config
- When enabled, all Timedoor server members may DM the bot directly — no @mention required in DMs
- Server membership check is enforced to prevent external users from accessing internal Notion data
- DM sessions use the same `user_id + channel_id` key as channel sessions (DM channel IDs are unique per user, so no collision)

---

### Module 2 — Query Parser

**Purpose**: Understand what the user is asking, maintain conversation history, and prepare structured query intent for the data router.

**Sub-components**:

#### 2a. Session Manager

| Sub-component | Description |
|---|---|
| Session Store | In-memory dictionary keyed by `user_id + channel_id`; stores last 3–5 message exchanges |
| Session Timeout | Clears session after 30 minutes of inactivity; configurable |
| History Injector | Prepends conversation history to LLM prompt for context resolution |
| Session Reset | Manual reset available via `@bot reset` command |

Session structure:
```
{
  "user:1234_channel:5678": {
    "history": [
      {"role": "user",      "content": "siapa PM project Inwan?"},
      {"role": "assistant", "content": "PM-nya adalah Cindy Felicia"},
      {"role": "user",      "content": "berapa bug yang open?"},
      {"role": "assistant", "content": "Ada 7 bug Open di Inwan"}
    ],
    "last_active": 1723500000
  }
}
```

#### 2b. Intent Classifier

Classifies each question (or sub-question in a multi-question message) into one of these intents:

| Intent | Example Query |
|---|---|
| `project_info` | "tech stack project X apa?", "siapa PM-nya?" |
| `bug_query` | "berapa open bug project X?", "ada bug urgent gak?" |
| `bug_query_env` | "bug di staging mobile ada berapa?" |
| `version_query` | "versi terbaru project X berapa?" |
| `credential_query` | "server project X dimana?", "database credentials X" |
| `doc_link_query` | "link design project X", "drive link X" |
| `status_query` | "status project X sekarang apa?" |
| `unknown` | Anything the classifier cannot map → graceful fallback |

#### 2c. Entity Extractor & Fuzzy Matcher

| Sub-component | Description |
|---|---|
| Project Name Extractor | Identify the project name from the query |
| Fuzzy Matcher | Match user input ("inwan", "orange care", "Inwan OC") against known project names using similarity scoring |
| Ambiguity Handler | If multiple projects match (score too close), bot asks: "Maksudnya Inwan (Orange Care) atau Inwan Bali?" |
| Cross-session Context | If no project mentioned in current message, inherit from most recent session history entry |

#### 2d. Multi-Question Splitter

- Detects numbered lists (`1. ... 2. ... 3. ...`) or comma-separated questions in a single message
- Splits into individual query intents
- Shares entity context across all sub-questions (if Q1 names a project, Q2–Q4 inherit it)
- Batches all sub-queries for single LLM synthesis call

#### 2e. Language Detector

- Detects message language (Indonesian / English)
- Passes language signal to LLM Synthesizer
- LLM responds in same language as the query

---

### Module 3 — Notion Data Router

**Purpose**: Determine which Notion data source to use for each query intent, and manage multi-hop navigation across databases and pages.

**Sub-components**:

| Sub-component | Description |
|---|---|
| Workspace DB Registry | Config file mapping team names to Notion Database IDs (Mobile, Web, Backend) |
| Route Decision Engine | Assigns each intent to Tier 1/2 (API) or Tier 3 (MCP) |
| API Fast Path | Sends structured query to Notion API client |
| MCP Fallback | Triggers Notion MCP navigation for unstructured queries or when API returns null |
| Multi-hop Coordinator | Manages sequential lookups: Project DB → Page ID → Sub-database ID → Query |
| Property Name Normalizer | Maps variant property names to canonical concepts (e.g., "Framework", "Tech Stack", "Stack" → `tech_stack`) |
| Null Fallback | If API returns empty and MCP also fails, route returns explicit "not found" signal |

**Routing logic**:
```
Intent received
  │
  ├── project_info, status_query  → Tier 1 (Notion API, project properties)
  │
  ├── bug_query, bug_query_env   → Tier 2 (Notion API, Bug List sub-DB)
  │
  ├── version_query              → Tier 2 (Notion API, Change Log sub-DB)
  │
  ├── credential_query           → Tier 3 (Notion MCP, credentials page)
  │                                then apply partial reveal policy
  │
  ├── doc_link_query             → Tier 2/3 (try API properties first,
  │                                fall back to MCP page navigation)
  │
  └── unknown                   → Return graceful "I don't understand" response
```

---

### Module 4 — Data Fetcher

**Purpose**: Execute actual data retrieval from Notion via API or MCP, and manage caching.

**Sub-components**:

#### 4a. Notion API Client

| Operation | Description |
|---|---|
| Project Search | Query project databases by name filter across all team DBs |
| Property Fetcher | Retrieve specific properties from a project database entry |
| Bug List Fetcher | Query Bug List sub-database filtered by Status; supports environment filter |
| Bug Count Aggregator | Count bugs grouped by Status (Open, In Progress, Re-Opened, Re-Test) |
| Change Log Fetcher | Query Change Log sub-database, sorted by date, return latest entry |

**Bug query behavior**:
- Default (no environment specified): count across ALL environment tabs combined
- Specific environment (e.g., "staging mobile"): filter to that tab only

#### 4b. Notion MCP Client

| Operation | Description |
|---|---|
| Workspace Search | Search entire workspace by project name keyword |
| Page Navigator | Navigate to project page; list child pages |
| Page Content Reader | Read free-form block content from a Notion page |
| Credential Extractor | Instruct LLM to extract server host/URL only; suppress passwords/tokens |
| Doc Link Finder | Locate Design Link, Drive Link from page content |

#### 4c. Cache Layer

| Data Type | TTL | Rationale |
|---|---|---|
| Project properties (Tier 1) | 30 minutes | Rarely changes mid-day |
| Bug counts (Tier 2) | 5 minutes | Can change frequently during active sprints |
| Change Log (Tier 2) | 15 minutes | Changes only on releases |
| Credentials (Tier 3) | No cache | Security — always read fresh from Notion |
| Doc links (Tier 3) | 60 minutes | Stable, rarely changes |

Cache implementation: in-memory dictionary for MVP; upgrade to Redis in Phase 2 for persistence across restarts.

---

### Module 5 — LLM Response Synthesizer

**Purpose**: Convert raw fetched data into clear, natural language answers using Gemini 2.0 Flash.

**Sub-components**:

| Sub-component | Description |
|---|---|
| Prompt Builder | Assembles system prompt + conversation history + retrieved data + user question |
| Multi-answer Formatter | Generates numbered responses matching the user's numbered questions |
| Language Instruction | Instructs LLM to respond in detected language (Indonesian or English) |
| Hallucination Guardrail | System prompt explicitly instructs: "Answer only using the provided data. Do not infer or invent information not present in the context." |
| Credential Formatter | Special template for credential responses: show host/URL, append Notion link, add security note |
| Not Found Handler | If data is null/empty, LLM responds with friendly "data not found" instead of guessing |
| Cost Guard | Prompt templates are optimized to minimize token usage; structured JSON is passed instead of raw page dumps |

**System prompt skeleton**:
```
You are Timedoor Project Assistant, an internal company bot.
Answer only using the data provided below. Do not guess or invent.
Respond in the same language as the user's message (Indonesian or English).
If data is missing, say so clearly — do not make up an answer.

[CONVERSATION HISTORY]
{history}

[RETRIEVED DATA]
{notion_data}

[USER QUESTION]
{user_message}
```

**Credential response template**:
```
Berikut informasi server untuk {project_name}:

Host / URL   : {server_host}
Environment  : {environment}

Untuk credentials lengkap (password, token, API key):
→ {notion_credentials_link}

Sensitive fields tidak ditampilkan di Discord demi keamanan.
```

---

### Module 6 — Configuration & Observability

**Purpose**: Allow admins to manage bot settings without code changes, and monitor bot health and usage.

**Sub-components**:

| Sub-component | Description |
|---|---|
| Channel Config Manager | JSON/YAML config file: list of allowed or denied Discord channel IDs |
| Notion DB Registry | Config file mapping team names to Notion Database IDs; add new teams here |
| LLM Config | Model name, temperature, max token settings |
| Cache Config | TTL values per data tier |
| Response Latency Logger | Log query type and response time per request |
| Error Tracker | Log Notion API errors, MCP failures, LLM errors with timestamp and query context |
| Query Audit Log | Log who asked what and when (no credential content logged) |
| Health Check Endpoint | FastAPI `/health` endpoint to verify bot + Notion + LLM connectivity — **production only**; not included in demo phase |

**Config file structure**:
```yaml
discord:
  allowed_channels:
    - "1234567890123456789"   # #project-bot
    - "9876543210987654321"   # #dev-team
  denied_channels:
    - "1111111111111111111"   # #general
  allow_dms: true
  dm_require_server_membership: true   # reject DMs from non-Timedoor users
  timedoor_server_id: "YOUR_SERVER_ID_HERE"

notion:
  databases:
    mobile_team: "notion-db-id-abc123"
    web_team:    "notion-db-id-def456"
    backend_team: "notion-db-id-ghi789"

session:
  max_history: 5
  timeout_minutes: 30

cache:
  project_properties_ttl: 1800   # 30 min
  bug_counts_ttl: 300            # 5 min
  changelog_ttl: 900             # 15 min

llm:
  model: "gemini-2.0-flash"
  temperature: 0.2
  max_output_tokens: 1024
```

---

## 8. Query Types & Behavior Examples

### Example 1 — Multi-question, single message (Indonesian)

**Input**:
```
@bot saya ada beberapa pertanyaan tentang project Inwan:
1. tech stack-nya apa?
2. siapa PM-nya?
3. saat ini bug yang open ada berapa?
4. versi terbaru berapa?
```

**Processing**:
- 4 intents: `project_info`, `project_info`, `bug_query`, `version_query`
- Project: Inwan (Orange Care) — matched via fuzzy search
- Tier 1: fetch Framework, PM properties
- Tier 2: count Bug List where Status = Open (all environments)
- Tier 2: fetch Change Log latest entry

**Output**:
```
Berikut informasi untuk Inwan (Orange Care):

1. Tech stack-nya adalah Flutter (Framework) + Android & iOS (Platform)
2. PM-nya adalah Cindy Felicia
3. Saat ini ada 7 bug berstatus Open (semua environment)
4. Versi terbaru: Android 3.4.0 / iOS 2.4.0 (dirilis 9 Juli 2026)
```

---

### Example 2 — Follow-up query using session context

**Exchange 1**:
```
User: @bot siapa PM project Inwan?
Bot:  PM-nya adalah Cindy Felicia.
```

**Exchange 2** (no project name repeated):
```
User: @bot berapa bug urgent yang open?
Bot:  Di Inwan (Orange Care), ada 2 bug berstatus Urgent dan Open.
      (OTP verification & Order Checkout issue)
```

Bot resolved "Inwan" from session history without re-asking.

---

### Example 3 — Credential query with partial reveal

**Input**:
```
@bot server credentials untuk project Inwan dimana?
```

**Output**:
```
Berikut informasi server untuk Inwan (Orange Care):

Host / URL   : api.inwan.com
Environment  : Production

Untuk credentials lengkap (password, token, API key):
→ https://notion.so/timedoor/inwan-credentials-xxxxx

Sensitive fields tidak ditampilkan di Discord demi keamanan.
```

---

### Example 4 — Bug query with specific environment

**Input**:
```
@bot bug open di staging mobile project Inwan ada berapa?
```

**Output**:
```
Di Inwan (Orange Care) — Staging Mobile:
Ditemukan 0 bug berstatus Open di environment ini.
```

---

### Example 5 — DM query (no @mention needed)

**Context**: User sends a private message directly to the bot.

**Input** (via DM):
```
berapa open bug di project Inwan staging mobile?
```

**Processing**:
- Bot detects `DMChannel`; verifies sender is a Timedoor server member → access granted
- Intent: `bug_query_env`, Project: Inwan, Environment: Staging Mobile
- Tier 2: query Bug List sub-DB

**Output** (private reply):
```
Di Inwan (Orange Care) — Staging Mobile:
Ditemukan 0 bug berstatus Open di environment ini.
```

No @mention required in DMs. Session context carries forward for follow-up questions within the same DM conversation.

---

### Example 6 — DM rejected (non-member)

**Context**: An external user (not in the Timedoor Discord server) sends a DM to the bot.

**Input** (via DM):
```
siapa PM project Inwan?
```

**Output** (private reply):
```
Maaf, bot ini hanya tersedia untuk anggota internal Timedoor.
Silakan hubungi tim Timedoor jika kamu membutuhkan akses.
```

Bot does not process the query or expose any Notion data.

---

### Example 7 — Unknown or ambiguous project

**Input**:
```
@bot tech stack project TM?
```

**Output**:
```
Saya menemukan beberapa project yang cocok dengan "TM":
1. TM Square
2. TM Bali

Project mana yang dimaksud?
```

---

## 9. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Response latency — structured query (Tier 1/2) | < 7 seconds |
| Response latency — unstructured query (Tier 3/MCP) | < 15 seconds |
| Data accuracy — structured data | ≥ 90% |
| Data accuracy — unstructured/MCP data | ≥ 70% |
| Monthly LLM API cost | < $10 USD |
| Bot uptime | ≥ 99% (Railway managed hosting) |
| Language support | Indonesian and English |
| Session context depth | 3–5 exchanges per user per channel |
| Session timeout | 30 minutes inactivity |
| Credential fields exposed in Discord | None (host/URL only) |

---

## 10. Tech Stack

### Demo Phase (local run)

| Layer | Technology | Rationale |
|---|---|---|
| Discord Interface | discord.py (Python 3.11+) | Mature Python Discord library; WebSocket gateway, no HTTP server needed |
| AI Orchestration | LangChain | Native Python support, MCP integration |
| LLM | Gemini 2.0 Flash — free tier (Google AI Studio) | Zero cost for demo; same provider as production, no migration needed |
| Notion Structured | Notion API (official Python client) | Fast, reliable for database queries |
| Notion Unstructured | Notion MCP Server | LLM-navigated page reading |
| Cache | In-memory dict | Simple for demo scale |
| Hosting | Local machine | Bot connects outward to Discord — no public server or tunnel required |
| Config | YAML config file | Human-readable, no code changes needed |
| Logging | Python logging → console | Sufficient for demo |

### Production Phase (Railway deploy)

| Layer | Technology | Rationale |
|---|---|---|
| Discord Interface | discord.py (Python 3.11+) | Same as demo |
| API Server | FastAPI — runs alongside discord.py via `asyncio.gather` | Health check endpoint for Railway uptime monitoring; foundation for Phase 2 admin APIs |
| AI Orchestration | LangChain | Same as demo |
| LLM | Gemini 2.0 Flash — paid API | Best cost-to-quality ratio; estimated < $10/month at internal usage scale |
| Notion Structured | Notion API (official Python client) | Same as demo |
| Notion Unstructured | Notion MCP Server | Same as demo |
| Cache | In-memory dict (MVP) → Redis (Phase 2) | Simple for MVP, scalable later |
| Hosting | Railway | Beginner-friendly, no spin-down, GitHub deploy |
| Config | YAML config file | Same as demo |
| Logging | Python logging + Railway dashboard | Sufficient for MVP scale |

---

## 11. Out of Scope (MVP)

| Feature | Reason Deferred |
|---|---|
| Writing / editing Notion data via Discord | Risk of accidental data corruption; read-only is safer for MVP |
| Full Role-Based Access Control (RBAC) | Complex to implement in 1 month; access rules need separate policy discussion |
| Google Sheets integration | Deferred to Phase 2; separate data access rules needed |
| PDF, image, voice input parsing | Multimodal complexity exceeds 1-month timeline |
| Slash commands (Discord) | @mention + natural language sufficient for MVP; slash commands in Phase 2 |
| Redis persistent session cache | In-memory sufficient for MVP; upgrade in Phase 2 |
| Proactive alerts / notifications | Bot is reactive only (responds to queries); push alerts are Phase 2 |
| Ephemeral responses | Requires slash commands; Phase 2 |
| FastAPI HTTP server | Not needed for bot functionality; added in production phase for health check and future admin APIs |

---

## 12. MVP Success Criteria

| Metric | Target |
|---|---|
| Structured query response time | < 7 seconds per query |
| Unstructured query response time | < 15 seconds per query |
| Data accuracy (structured) | ≥ 90% verified against live Notion |
| Monthly LLM cost | < $10 USD |
| Time saved per lookup | ≥ 40% reduction vs. manual Notion search |
| Weekly active users | Active usage across PM, Dev, QA, CS, Sales during trial |

---

## 13. Risks & Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Notion structure inconsistency** — Different teams use different property names for the same concepts | Medium accuracy drop | Property name normalizer in Data Router; pre-launch standardization of minimum required fields |
| 2 | **Data incompleteness** — PM or Dev leaves Notion properties empty | Bot returns "data not found" | Bot explicitly states when data is missing; does not guess |
| 3 | **Notion API / MCP rate limits** — High concurrent queries may cause delays | Latency increase | Caching layer reduces repeat API calls; rate limiter on Discord side prevents spam |
| 4 | **Token cost overrun** — Poorly structured MCP queries consume more tokens | Cost > $10/month | Structured API fast path for common queries; MCP only as fallback; prompt length caps |
| 5 | **Credential exposure risk** — Bot accidentally reveals sensitive fields | Security incident | Partial reveal policy enforced in LLM prompt and credential formatter; never cache credentials |
| 6 | **User habit persistence** — Team continues asking colleagues instead of using bot | Low adoption | Awareness campaign at launch; bot available in existing team channels |
| 7 | **Bot restart clears session history** | Minor UX disruption | Acceptable for MVP; Redis persistence in Phase 2 |
| 8 | **Unauthorized DM access** — External users outside Timedoor may attempt to query internal project data via DM | Security incident | Server membership check enforced before processing any DM; non-members receive a generic rejection with no data exposure |

---

## 14. Pre-Launch Dependencies

These are not development tasks — they are Notion and organizational tasks that must be completed before the bot launches.

| # | Task | Owner | Priority |
|---|---|---|---|
| 1 | Define minimum required property schema for all team project databases (Name, Status, Platform, PM, Tech Stack) | PM Leader + Team Leads | Critical |
| 2 | Audit and clean up existing project database entries to fill minimum required properties | Each team's PM | High |
| 3 | Ensure all project pages follow the same section template (Credentials, Bug List, Change Log) | Each team's PM | High |
| 4 | Obtain Notion API integration token with read access to all team workspaces | Admin | Critical |
| 5 | Set up Notion MCP server with appropriate workspace access | Developer | Critical |
| 6 | Create Discord bot application and obtain bot token | Admin | Critical |
| 7 | Identify Discord channel IDs for bot allowlist configuration | PM / Admin | Medium |

---

## 15. Future Phases

### Production Migration (Demo → Production)

When the supervisor approves the demo for production deployment:

| Change | Detail |
|---|---|
| Hosting | Move from local machine to Railway; bot runs 24/7 without depending on developer's laptop |
| FastAPI | Added alongside discord.py via `asyncio.gather` in the same process; exposes `/health` on port 8000 for Railway uptime monitoring |
| LLM | Switch from Gemini free tier to Gemini 2.0 Flash paid API; update API key in config |
| Logging | Python logging output routed to Railway dashboard instead of console |

No architectural changes required — demo and production share the same codebase. Migration is a config and deployment change only.

### Phase 2 (Post-MVP)

| Feature | Description |
|---|---|
| Slash commands + ephemeral responses | `/ask project:Inwan question:bug count` — response visible only to asker |
| Full RBAC | Discord role → Notion data access mapping (e.g., CS cannot see credentials) |
| Redis session persistence | Sessions survive bot restarts |
| Proactive bug alerts | Bot posts in `#dev-team` when new Urgent bug is added to Notion |
| FastAPI admin APIs | HTTP endpoints for managing channel config and database registry without editing YAML manually |
| Google Sheets integration | Sales data access after access rules are defined |
| Multi-workspace support | Expand beyond current teams |

### Phase 3 (Long-term)

| Feature | Description |
|---|---|
| Write-back to Notion | Update task status, add notes via Discord (with confirmation flow) |
| Voice query support | Discord voice channel integration |
| Analytics dashboard | Query volume, most-asked projects, response time trends |
| Mobile / Web admin panel | Visual config management for channels and database registry |

---

## 16. Testing Strategy

Testing follows a three-layer approach: unit tests for individual functions, integration tests after each module is completed, and E2E tests once all modules are connected. TDD (writing tests before code) is not required — tests are written alongside or immediately after each module.

---

### Test Types

| Type | Scope | When | Dependencies |
|---|---|---|---|
| Unit | Single function | During development, as needed | None — pure logic |
| Integration | One module at a time | After each module is complete | Mocked (Notion API, Discord, LLM) |
| E2E | Full system, all modules | After all modules are integrated | Real — live Discord, Notion, LLM |

**Tool**: `pytest` for all three layers.

---

### Integration Tests — Per Module

Run after each module is completed. All external dependencies are mocked so tests are fast and do not require live credentials.

| Module | What to test |
|---|---|
| Module 1 — Discord Gateway | Channel allowlist/denylist filter; DM detector; server membership check; rate limiter blocks repeated queries |
| Module 2 — Query Parser | Intent classifier maps query strings to correct intents; fuzzy matcher scores project names; multi-question splitter splits correctly; session context inherited across follow-ups |
| Module 3 — Notion Data Router | Each intent routes to the correct tier (API vs MCP); null result from API triggers MCP fallback |
| Module 4 — Data Fetcher | Cached result returned on second call within TTL; cache miss triggers fresh API call; credential queries bypass cache |
| Module 5 — LLM Synthesizer | Prompt assembled correctly from history + data + question; credential response uses partial reveal template; not-found data produces graceful message, not a guess |
| Module 6 — Config & Observability | YAML loads correctly; invalid channel ID handled gracefully; TTL values applied to correct data tiers |

---

### E2E Tests — Full System

Run after all modules are integrated, before handover to supervisor. Uses a **dedicated test bot token** and a **private test Discord server** — separate from the live bot. No mocks; the full stack runs end-to-end.

#### Test environment setup

| Item | Detail |
|---|---|
| Test bot token | Separate Discord bot application, not the production bot |
| Test Discord server | Private server with at least one text channel and one DM-capable member |
| Notion access | Same integration token as production; tests read from real Notion data |
| LLM | Live Gemini API (free tier sufficient for test volume) |

#### E2E test cases

Each test case maps directly to a Section 8 query example.

| # | Scenario | Input | Pass Condition |
|---|---|---|---|
| E2E-01 | Multi-question query | 4-part numbered message about a real project | Response is numbered 1–4; each answer matches live Notion data |
| E2E-02 | Follow-up session context | Q1 names a project; Q2 asks follow-up with no project name | Bot resolves project from session history without re-asking |
| E2E-03 | Credential query — partial reveal | Ask for server credentials | Response shows host/URL only; Notion link appended; no password/token in output |
| E2E-04 | Bug query with environment filter | Ask for bugs in a specific environment (e.g., Staging Mobile) | Response scoped to that environment only |
| E2E-05 | DM query — authorized user | Timedoor server member sends DM | Bot responds correctly; no @mention required |
| E2E-06 | DM query — unauthorized user | Non-member sends DM | Bot returns rejection message; no Notion data exposed |
| E2E-07 | Ambiguous project name | Short/partial project name that matches multiple projects | Bot returns clarification prompt listing matched projects |
| E2E-08 | Unknown intent | Unrecognizable query | Bot returns graceful "I don't understand" without guessing |
| E2E-09 | Bilingual response | Ask same query in Indonesian and English | Each response language matches the query language |
| E2E-10 | Session reset | Send `@bot reset`; ask follow-up with no project name | Bot does not resolve project from cleared session |

#### Pass criteria

All 10 E2E test cases must pass before the project is handed over to the supervisor.

---

*End of Document — PRD v1.3*
