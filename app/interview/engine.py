"""Interview state machine: turns a candidate profile into a plan, then walks
through main question -> follow-up -> next topic until the plan is exhausted,
at which point it produces structured feedback.
"""
import logging
from typing import Any, Dict, Optional

from . import llm
from .curriculum import CURRICULUM_DAYS
from .planner import build_plan
from .state import Session, TranscriptEntry, store

logger = logging.getLogger("interview.engine")

PLAN_TARGET_LEN = 6
MAX_EMPTY_ANSWERS_PER_TOPIC = 2


def normalize_candidate(raw: Any) -> Dict[str, Any]:
    """Accepts the shape described in the spec ({"member", "missions", "signals"})
    but degrades gracefully for a few plausible variants a client might send."""
    if not isinstance(raw, dict):
        raise ValueError("'candidate' must be an object")
    if "member" in raw:
        candidate = dict(raw)
        candidate.setdefault("missions", [])
        candidate.setdefault("signals", {})
        return candidate
    if isinstance(raw.get("candidates"), list) and raw["candidates"]:
        # Client sent the whole candidates.json wrapper instead of one entry.
        first = raw["candidates"][0]
        if isinstance(first, dict) and "member" in first:
            return normalize_candidate(first)
    if "id" in raw and "name" in raw:
        # Client sent flattened member fields at the top level.
        return {
            "member": raw,
            "missions": raw.get("missions", []) or [],
            "signals": raw.get("signals", {}) or {},
        }
    raise ValueError(
        "Unrecognized candidate schema -- expected an object with a 'member' field "
        "matching candidates.json."
    )


def start_session(session_id: str, raw_candidate: Any) -> Dict[str, Any]:
    candidate = normalize_candidate(raw_candidate)
    plan = build_plan(candidate, CURRICULUM_DAYS, target_len=PLAN_TARGET_LEN)

    session = Session(session_id=session_id, candidate=candidate, plan=plan)
    first_item = plan[0]
    question_text = llm.generate_question(candidate, first_item, transcript=[], is_first=True)
    session.pending = TranscriptEntry(
        day=first_item["day"],
        title=first_item["title"],
        category=first_item["category"],
        kind="main",
        question=question_text,
    )
    store.set(session_id, session)
    return {"reply": question_text, "done": False}


def _finish_interview(session: Session) -> Dict[str, Any]:
    feedback = llm.generate_feedback(session.candidate, session.transcript, session.plan)
    session.done = True
    session.feedback = feedback
    session.pending = None
    store.set(session.session_id, session)
    return {"reply": "Thanks for walking me through all of that -- interview completed.", "done": True, "feedback": feedback}


def _advance_to_next_topic(session: Session) -> Dict[str, Any]:
    session.plan_index += 1
    session.phase = "main"
    session.empty_answer_count = 0
    if session.plan_index >= len(session.plan):
        return _finish_interview(session)

    item = session.plan[session.plan_index]
    question_text = llm.generate_question(session.candidate, item, transcript=session.transcript, is_first=False)
    session.pending = TranscriptEntry(
        day=item["day"],
        title=item["title"],
        category=item["category"],
        kind="main",
        question=question_text,
    )
    store.set(session.session_id, session)
    return {"reply": question_text, "done": False}


def handle_turn(session_id: str, message: Optional[str]) -> Dict[str, Any]:
    session = store.get(session_id)
    if session is None:
        return {
            "error": "not_found",
            "reply": "I don't have an active interview for this session. Start a new interview by sending your candidate profile.",
            "done": True,
        }

    if session.done:
        return {
            "reply": "This interview has already been completed. Thanks again for your time!",
            "done": True,
            "feedback": session.feedback,
        }

    text = (message or "").strip()
    item = session.plan[session.plan_index]

    if not text:
        session.empty_answer_count += 1
        if session.empty_answer_count >= MAX_EMPTY_ANSWERS_PER_TOPIC:
            if session.pending is not None:
                session.pending.answer = "(no answer provided)"
                session.transcript.append(session.pending)
            return _advance_to_next_topic(session)
        store.set(session_id, session)
        return {"reply": "Take your time -- could you share your thoughts, even a partial answer?", "done": False}

    session.empty_answer_count = 0
    if session.pending is not None:
        session.pending.answer = text
        session.transcript.append(session.pending)

    if session.phase == "main":
        followup_text = llm.generate_followup(session.candidate, item, session.pending.question, text, session.transcript)
        session.pending = TranscriptEntry(
            day=item["day"],
            title=item["title"],
            category=item["category"],
            kind="followup",
            question=followup_text,
        )
        session.phase = "followup"
        store.set(session_id, session)
        return {"reply": followup_text, "done": False}

    return _advance_to_next_topic(session)
