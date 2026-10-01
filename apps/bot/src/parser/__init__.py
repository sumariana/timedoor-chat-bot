import re

from src.config import get_audit_logger
from src.models import ParsedQuery, QueryIntent
from src.parser.classifier import classify_message
from src.parser.matcher import fuzzy_match_project, initialize_project_registry
from src.parser.session import get_session_store

_MENTION_PATTERN = re.compile(r"<@!?\d+>")


def _strip_mention(message_text: str) -> str:
    return _MENTION_PATTERN.sub("", message_text).strip()


async def parse_message(message_text: str, user_id: int, channel_id: int) -> ParsedQuery:
    store = get_session_store()
    clean_text = _strip_mention(message_text)
    session_key = store.make_key(user_id, channel_id)

    if clean_text.strip().lower() == "reset":
        store.clear(session_key)
        return ParsedQuery(
            questions=[QueryIntent("session_reset", None, None, "en", clean_text)],
            session_key=session_key,
            user_id=user_id,
            channel_id=channel_id,
        )

    history = store.get_history(session_key)
    last_project = store.get_last_project(session_key)
    history_dicts = [{"role": item.role, "content": item.content} for item in history]

    language, raw_questions = await classify_message(clean_text, history_dicts)

    questions: list[QueryIntent] = []
    for raw_question in raw_questions:
        raw_name = raw_question.get("project_name")
        is_ambiguous = False
        candidates: list[str] = []

        if raw_name:
            matched, match_candidates = fuzzy_match_project(raw_name)
            if matched:
                project_name = matched
            elif match_candidates:
                project_name = None
                is_ambiguous = True
                candidates = match_candidates
            else:
                project_name = raw_name
        else:
            project_name = last_project

        questions.append(
            QueryIntent(
                intent=raw_question.get("intent", "unknown"),
                project_name=project_name,
                environment=raw_question.get("environment"),
                language=language,
                raw_question=raw_question.get("raw_question", clean_text),
                is_ambiguous=is_ambiguous,
                candidates=candidates,
            )
        )

    try:
        get_audit_logger().info(
            "query_parsed",
            extra={
                "user_id": user_id,
                "channel_id": channel_id,
                "intents": [q.intent for q in questions],
                "projects": [q.project_name for q in questions],
            },
        )
    except RuntimeError:
        pass

    return ParsedQuery(
        questions=questions,
        session_key=session_key,
        user_id=user_id,
        channel_id=channel_id,
        history=[{"role": item.role, "content": item.content} for item in store.get_history(session_key)],
    )


def add_to_session(user_id: int, channel_id: int, user_message: str, bot_response: str) -> None:
    store = get_session_store()
    store.add_exchange(store.make_key(user_id, channel_id), user_message, bot_response)


def update_session_project(user_id: int, channel_id: int, project_name: str) -> None:
    store = get_session_store()
    store.update_last_project(store.make_key(user_id, channel_id), project_name)


def clear_session(user_id: int, channel_id: int) -> None:
    store = get_session_store()
    store.clear(store.make_key(user_id, channel_id))


__all__ = [
    "parse_message",
    "add_to_session",
    "update_session_project",
    "clear_session",
    "initialize_project_registry",
]
