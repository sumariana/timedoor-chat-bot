import time
from dataclasses import dataclass, field
from typing import Optional

from src.config import get_config


@dataclass
class SessionMessage:
    role: str
    content: str


@dataclass
class Session:
    history: list[SessionMessage] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)
    last_project: Optional[str] = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def make_key(self, user_id: int, channel_id: int) -> str:
        return f"user:{user_id}_channel:{channel_id}"

    def _expire_if_needed(self, session_key: str) -> None:
        session = self._sessions.get(session_key)
        if session is None:
            return
        timeout = get_config().session.timeout_minutes * 60
        if time.time() - session.last_active > timeout:
            del self._sessions[session_key]

    def get_history(self, session_key: str) -> list[SessionMessage]:
        self._expire_if_needed(session_key)
        session = self._sessions.get(session_key)
        return session.history if session else []

    def get_last_project(self, session_key: str) -> Optional[str]:
        self._expire_if_needed(session_key)
        session = self._sessions.get(session_key)
        return session.last_project if session else None

    def add_exchange(self, session_key: str, user_msg: str, bot_response: str) -> None:
        session = self._sessions.setdefault(session_key, Session())
        session.history.append(SessionMessage("user", user_msg))
        session.history.append(SessionMessage("assistant", bot_response))
        max_messages = get_config().session.max_history * 2
        session.history = session.history[-max_messages:]
        session.last_active = time.time()

    def update_last_project(self, session_key: str, project_name: str) -> None:
        session = self._sessions.setdefault(session_key, Session())
        session.last_project = project_name

    def clear(self, session_key: str) -> None:
        self._sessions.pop(session_key, None)


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
