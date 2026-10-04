import re
import time

from src.config import get_error_logger, get_latency_logger
from src.models import BotResponse, NotionResult, QueryIntent
from src.synthesizer.formatters import (
    format_ambiguity,
    format_credential_response,
    format_not_found,
    format_session_reset,
)
from src.synthesizer.gemini import call_gemini, call_gemini_extract_credentials
from src.synthesizer.prompt import build_system_prompt, build_user_prompt


def _split_numbered_response(raw_response: str, count: int) -> list[str]:
    if count == 1:
        return [raw_response.strip()]
    parts = re.split(r"(?:^|\n)\s*\d+[.)]\s*", raw_response.strip())
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) == count:
        return parts
    return [raw_response.strip()] + [""] * (count - 1)


def _error_response(language: str) -> BotResponse:
    return BotResponse(
        content=(
            "Maaf, terjadi kesalahan saat memproses pertanyaan Anda."
            if language == "id"
            else "Sorry, an error occurred while processing your question."
        ),
        language=language,
        is_error=True,
    )


async def synthesize_response(
    results: list[tuple[QueryIntent, NotionResult]],
    history: list[dict],
) -> BotResponse:
    language = results[0][0].language if results else "id"
    try:
        answers = [""] * len(results)
        standard_indices: list[int] = []
        is_credential_response = False

        for index, (intent, result) in enumerate(results):
            if intent.intent == "session_reset":
                answers[index] = format_session_reset(language)
            elif intent.is_ambiguous:
                answers[index] = format_ambiguity(intent.candidates, language)
            elif result.data is None:
                answers[index] = format_not_found(intent, language)
            elif intent.intent == "credential_query":
                content = result.data.get("content", "")
                extracted = await call_gemini_extract_credentials(content)
                answers[index] = format_credential_response(
                    intent.project_name,
                    extracted.get("server_host"),
                    extracted.get("environment"),
                    result.notion_url,
                    language,
                )
                is_credential_response = True
            else:
                standard_indices.append(index)

        if standard_indices:
            standard_pairs = [results[index] for index in standard_indices]
            start = time.perf_counter()
            raw_response = await call_gemini(
                build_system_prompt(language),
                build_user_prompt(standard_pairs, history),
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            try:
                get_latency_logger().info(
                    "gemini_synthesis",
                    extra={"duration_ms": duration_ms, "question_count": len(standard_pairs)},
                )
            except RuntimeError:
                pass
            for index, answer in zip(
                standard_indices,
                _split_numbered_response(raw_response, len(standard_indices)),
            ):
                answers[index] = answer

        content = answers[0] if len(answers) == 1 else "\n\n".join(
            f"{index}. {answer}" for index, answer in enumerate(answers, 1)
        )
        return BotResponse(content, language, False, is_credential_response)
    except Exception as exc:
        try:
            get_error_logger().error("Response synthesis failed: %s", exc, extra={"module": "synthesizer"})
        except RuntimeError:
            pass
        return _error_response(language)


__all__ = ["synthesize_response"]
