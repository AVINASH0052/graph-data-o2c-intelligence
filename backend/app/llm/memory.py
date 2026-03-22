"""
LLM memory: per-session conversation history (last N turns).
"""
from collections import deque

_sessions: dict[str, deque] = {}
MAX_TURNS = 5


def get_history(session_id: str) -> list[dict]:
    return list(_sessions.get(session_id, deque()))


def add_turn(session_id: str, role: str, content: str):
    if session_id not in _sessions:
        _sessions[session_id] = deque(maxlen=MAX_TURNS * 2)
    _sessions[session_id].append({"role": role, "content": content})


def clear_session(session_id: str):
    _sessions.pop(session_id, None)
