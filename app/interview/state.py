"""In-memory session state for the interview endpoint.

The technical spec requires the endpoint to maintain state per sessionId across
independent HTTP requests, with no persistence requirement. An in-process dict
guarded by a lock is sufficient and keeps the deployment dependency-free.
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptEntry:
    day: int
    title: str
    category: str
    kind: str  # "main" | "followup"
    question: str
    answer: Optional[str] = None


@dataclass
class Session:
    session_id: str
    candidate: Dict[str, Any]
    plan: List[Dict[str, Any]]
    plan_index: int = 0
    phase: str = "main"  # "main" | "followup"
    transcript: List[TranscriptEntry] = field(default_factory=list)
    pending: Optional[TranscriptEntry] = None
    done: bool = False
    feedback: Optional[Dict[str, Any]] = None
    empty_answer_count: int = 0
    created_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(session_id)

    def set(self, session_id: str, session: Session) -> None:
        with self._lock:
            self._sessions[session_id] = session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


store = SessionStore()
