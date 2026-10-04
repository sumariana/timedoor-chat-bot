import json

import google.generativeai as genai

from src.config import get_config, get_error_logger

CLASSIFICATION_PROMPT = """You are an intent classifier for the Timedoor Project Assistant — an internal company chatbot.

Given a user message (in Indonesian or English), your job is to:
1. Detect the language of the message
2. Split it into individual questions if the message contains multiple
3. For each question, identify the intent and extract the project name

Return ONLY valid JSON in this exact structure:
{{
  "language": "id" | "en",
  "questions": [
    {{
      "intent": "...",
      "project_name": "..." | null,
      "environment": "..." | null,
      "raw_question": "..."
    }}
  ]
}}

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
"""

_FALLBACK_QUESTION = {
    "intent": "unknown",
    "project_name": None,
    "environment": None,
    "raw_question": "",
}


def _build_history_text(history: list[dict]) -> str:
    if not history:
        return "(no previous conversation)"
    return "\n".join(f"{item['role']}: {item['content']}" for item in history)


async def classify_message(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    try:
        config = get_config().llm
        genai.configure(api_key=config.api_key)
        model = genai.GenerativeModel(config.model)
        prompt = CLASSIFICATION_PROMPT.format(
            history=_build_history_text(history), user_message=user_message
        )
        response = await model.generate_content_async(
            prompt,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_output_tokens,
                "response_mime_type": "application/json",
            },
        )
        parsed = json.loads(response.text)
        return parsed["language"], parsed["questions"]
    except Exception as exc:
        try:
            get_error_logger().error("classify_message failed: %s", exc, extra={"module": "parser"})
        except RuntimeError:
            pass
        fallback = dict(_FALLBACK_QUESTION)
        fallback["raw_question"] = user_message
        return "id", [fallback]
