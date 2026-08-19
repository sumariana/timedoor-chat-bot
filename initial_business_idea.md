## **1\. Project Information**

**Project Title** 		: Timedoor Project Assistant Bot

**Project Type (Pick 1 ☑ )**  
☑ Internal Business Improvement  
☐ New Business / Product Innovation

## **2\. Project Overview** 

What are you building?

| Building an AI-powered Discord chatbot that centralizes project information for Timedoor by integrating directly with Notion Databases via the Notion API. The bot enables team members (PMs, Developers, QA, CS, and Sales) to query structured project metadata, such as tech stacks (Laravel, WordPress, Gurin, etc.), project URLs, open bug counts, and task statuses directly within Discord using natural language, eliminating manual search and scattered documentation overhead.  |
| :---- |

## **3\. Business Problem** 

What problem does it solve? Who experiences it? Why is it important?

| Currently, project information at Timedoor is scattered across various Notion pages and databases. Team members across multiple departments waste valuable time manually searching for routine project details or repeatedly escalating questions to colleagues. This disorganization creates communication bottlenecks, slows down issue resolution, and delays responses to client inquiries. |
| :---- |

## **4\. Solution Overview**

How will it solve the problem? 

| Timedoor Project Assistant uses a backend service connecting Discord with Notion Databases using the Notion API and a cost-efficient Retrieval-Augmented Generation (RAG) pipeline. When a user asks a question in Discord, the backend queries the structured Notion Database via API to retrieve precise JSON data. The AI then synthesizes this raw data into clear, natural language responses delivered directly to the Discord channel within seconds.  |
| :---- |

## **5\. Users & Stakeholders** 

| Users | Stakeholder |
| :---- | :---- |
| PM Developer QA CS Sales | PM Leader  Sparta Training Program Leads  |

## **6\. Expected Value** 

Choose 1 based on the type

If **Internal Project** (Sample)

| Category | Expected Benefit |
| :---- | :---- |
| Productivity | Cuts time spent searching for project details from minutes to seconds, speeding up daily team syncs and client replies.  |
| Cost Saving | Reduces operational overhead by minimizing repetitive information lookup, unnecessary internal discussions, and delays during project issue escalation.  Highly cost-efficient AI pipeline; reading structured JSON via API minimizes token consumption and operational costs.  |
| Quality Improvement | Provides consistent, up-to-date project information from centralized data sources, reducing miscommunication and errors caused by outdated or scattered documentation. |
| Employee Experience | Removes repetitive administrative lookup tasks, allowing developers and PMs to focus on core delivery.  |
| Other (Add as much as possible) | Improves cross-department knowledge sharing by providing instant access to project information through Discord, reducing dependency on specific team members and preserving organizational knowledge. |

## 

## **7\. Scope (1-Month MVP)**

Included Features:

| Feature List | Platform / Tech Stack |
| :---- | :---- |
| 1\. Natural Language Project Query Module (Tech stack, project URL, bug counts) 2\. Live Data Fetching Module (Open bug counts, task list status) 3\. Cost-Optimized RAG Engine & API Response Caching  | Bot Interface (Discord API / Discord.js) Backend Service (Python / FastAPI / LangChain) Data Integrations (Notion API) AI LLM Engine (OpenAI GPT, Google Gemini API) |

| Feature List | Why Out of Scope |
| :---- | :---- |
| 1\. Direct Data Editing/Updating via Discord 2\. Unstructured File & Voice Input Parsing (PDFs, Images, Audio) 3\. Granular Role-Based Access Control (RBAC) 4\. Google Sheets & Sensitive Sales Data Integration | 1-month MVP timeframe; focus is strictly on read-only retrieval to prevent accidental data corruption. Complex multimodal processing requires more than 1 month. High technical complexity; deferred to post-MVP phase. Deferred to Phase 2 per reviewer feedback to lower MVP complexity and resolve sales data access rules first.  |

## 

## **8\. MVP Success Criteria** 

How will success be measured?

| Response Latency: Bot delivers accurate responses in Discord within 7 seconds per query. Data Accuracy: Achieves over 90% factual accuracy on technical project data verified against live Notion sources. Time Efficiency: Reduces average time spent looking up project information by at least 40% across participating teams. User Adoption: Weekly active usage by team members across PM, Dev, CS, and Sales roles during the trial period. |
| :---- |

**9\. Risks & Assumptions**

Only 5 bullets maximum. 

1. **Risk 1 (Data Incompleteness):** If required Notion Database properties are left empty by PMs, the AI will report missing data.

2. **Risk 2 (API Rate Limits):** High concurrent requests to the Notion API may cause minor response delays (mitigated by backend caching).

3. **Risk 3 (Token Cost Control):** Unoptimized prompt sizes could raise LLM costs as the Notion Database grows (mitigated by fetching structured JSON instead of full page dumps).

4. **Risk 4 (Data Access Exposure):** Absence of granular Discord user role filtering could expose non-public fields (mitigated by excluding sensitive sales data in Phase 1).

5. **Risk 5 (User Habit Persistence):** Team members continuing old habits of asking colleagues directly instead of querying the Discord bot.

## **10\. AI Integration (Optional)**

Will AI be used?

☐ No AI  
☑ Yes

AI Capability

| Uses Retrieval-Augmented Generation (RAG) powered by a lightweight LLM (Gemini Flash / GPT-4o-mini). It interprets natural language queries from Discord, fetches targeted JSON data from Notion Databases via the Notion API, and synthesizes raw database records into clear, human-readable answers.  |
| :---- |

Business Purpose: 

| To convert static Notion project databases into an interactive, conversational assistant. This minimizes internal search time, eliminates repetitive context-switching, and streamlines cross-departmental communication in Discord without incurring heavy AI operational costs.  |
| :---- |

## 

## 

## 

## 

## 

## 

## 

## **Summary of Changes** 

**1\. Scope Reduction (Phase 1 Focus)**

* **Removed Google Sheets & Sales Data Integration:** Deferred to Phase 2 to lower overall technical complexity for the 1-month MVP and address data security/access rules first.  
* **Focused Strictly on Notion Databases:** Project scope is now concentrated entirely on retrieving structured project metadata (Tech stacks, server details, bug counts, task statuses) via Notion Database APIs.

**2\. Technical Architecture Refinement**

* **Shifted from Unstructured Text to JSON API Querying:** Replaced generic text-scraping RAG with targeted JSON retrieval from structured Notion Database properties. This guarantees high response accuracy (\>90%) and prevents AI hallucinations.

**3\. Cost Control & Efficiency**

* **Added AI Cost Efficiency Target:** Added a success metric keeping monthly LLM API costs strictly under **$10/month** by using cost-effective models (Gemini Flash / GPT-4o-mini) and backend caching.

**4\. Risk Assessment & Out-of-Scope Updates**

* Updated **Section 7 (Out of Scope)** and **Section 9 (Risks & Assumptions)** to explicitly reflect the exclusion of Google Sheets, data completeness dependencies, and LLM token optimization strategies.