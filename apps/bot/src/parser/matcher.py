from typing import Optional

from rapidfuzz import fuzz, process

from src.config import get_error_logger
from src.fetcher import list_all_project_names

_registry: list[str] = []


async def initialize_project_registry() -> None:
    global _registry
    _registry = await list_all_project_names()
    try:
        get_error_logger().info(
            "Project registry initialized with %d projects", len(_registry), extra={"module": "parser"}
        )
    except RuntimeError:
        pass


def fuzzy_match_project(
    raw_name: str,
    threshold: float = 70.0,
    ambiguity_gap: float = 10.0,
) -> tuple[Optional[str], list[str]]:
    if not _registry:
        try:
            get_error_logger().warning("Project registry is empty", extra={"module": "parser"})
        except RuntimeError:
            pass
        return None, []

    matches = process.extract(raw_name, _registry, scorer=fuzz.WRatio, limit=5)
    if not matches or matches[0][1] < threshold:
        return None, []

    top_score = matches[0][1]
    if top_score == 100:
        return matches[0][0], []

    close = [name for name, score, _ in matches if top_score - score < ambiguity_gap]
    if len(close) > 1:
        return None, close
    return matches[0][0], []
