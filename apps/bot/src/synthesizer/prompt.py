import json

from src.models import NotionResult, QueryIntent


def build_system_prompt(language: str) -> str:
    instruction = "Indonesian (Bahasa Indonesia)" if language == "id" else "English"
    return (
        "You are Timedoor Project Assistant, an internal company bot.\n"
        "Answer ONLY using the data provided in [RETRIEVED DATA].\n"
        "Do NOT guess, invent, or infer information not present in the provided data.\n"
        "If data for a question is null or missing, say so clearly — never make up an answer.\n"
        f"Respond in {instruction}.\n"
        "If there are multiple questions, number your answers to match the question numbers.\n"
        "Keep answers concise and factual."
    )


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(no previous conversation)"
    return "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history)


def _format_notion_data(results: list[tuple[QueryIntent, NotionResult]]) -> str:
    entries = []
    for index, (intent, result) in enumerate(results, 1):
        entries.append(
            f"Question {index} ({intent.intent} — {intent.project_name or 'unknown'}):\n"
            f"{json.dumps(result.data, ensure_ascii=False, default=str)}"
        )
    return "\n\n".join(entries)


def build_user_prompt(
    results: list[tuple[QueryIntent, NotionResult]],
    history: list[dict],
) -> str:
    questions = "\n".join(
        f"{index}. {intent.raw_question}" for index, (intent, _) in enumerate(results, 1)
    )
    return (
        "[CONVERSATION HISTORY]\n"
        f"{_format_history(history)}\n\n"
        "[QUESTIONS]\n"
        f"{questions}\n\n"
        "[RETRIEVED DATA]\n"
        f"{_format_notion_data(results)}"
    )
