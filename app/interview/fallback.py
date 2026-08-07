"""Deterministic, template-based interview logic.

Used whenever the Claude API is unavailable (no credentials, network error,
refusal, malformed response, timeout, etc.) so the interview endpoint always
completes end-to-end -- never crashes or stalls just because an LLM call failed.
Still adapts to the candidate's signal and to the vagueness of their answers,
so the experience degrades gracefully rather than becoming a static quiz.
"""
from typing import Any, Dict, List

_VAGUE_MARKERS = (
    "don't know",
    "dont know",
    "not sure",
    "no idea",
    "don't remember",
    "dont remember",
    "no clue",
    "n/a",
    "skip",
    "pass",
    "not familiar",
    "not aware",
    "no experience",
    "haven't used",
    "havent used",
    "never used",
    "not something i",
    "don't understand",
    "dont understand",
    "no context",
    # Phrases where the candidate is asking the interviewer for help rather
    # than answering -- a strong signal they don't know the material, even
    # when the message is long enough to pass the length check below.
    "can i learn",
    "can you teach",
    "can you explain",
    "could you explain",
    "teach me",
    "explain it to me",
    "help me understand",
    "what do you mean",
)

_PROBES_BY_TYPE = {
    "BUILD": "What would break first if the input volume grew 10x, and how would you detect it before your users did?",
    "SHIP_IT": "If you were shipping that to production today, what's the one thing you'd change first?",
    "AI_CORE": "How would you validate that this actually improved outcomes, rather than just feeling better?",
    "LEARN": "Can you give a concrete example from your own project where this concept actually mattered?",
    "OPTIMIZE": "What was the measurable before/after, and how did you know the change genuinely helped?",
    "SETUP": "What's one failure mode of that setup you'd want monitoring or alerting on?",
    "CAPSTONE": "Which part of the system are you least confident about, and why?",
}

_CATEGORY_HINT = {
    "mastered": "passed on the first try",
    "shaky": "passed after multiple attempts",
    "struggled": "did not pass this mission",
    "skipped": "skipped this mission",
    "generic": "no recorded attempt for this mission",
}


def _first_objective(item: Dict[str, Any]) -> str:
    objs = item.get("objectives") or []
    return objs[0] if objs else f"the core ideas behind {item['title']}"


def _is_vague(answer: str) -> bool:
    a = (answer or "").strip().lower()
    if len(a) < 15:
        return True
    return any(v in a for v in _VAGUE_MARKERS)


def fallback_question(item: Dict[str, Any]) -> str:
    title = item["title"]
    category = item["category"]
    tools = item.get("tools") or []
    tool_str = ", ".join(tools[:3]) if tools else "the tools involved"
    obj = _first_objective(item).rstrip(".")

    if category == "mastered":
        return (
            f'You completed "{title}" on your first attempt, so let\'s go deep. '
            f"Walk me through how you tackled {obj.lower()}. What tradeoffs did {tool_str} force on you, "
            f"and how would your approach change if the scale of the problem grew 100x?"
        )
    if category == "shaky":
        return (
            f'You passed "{title}" after a few attempts. What tripped you up initially, and how would you now '
            f"explain to a teammate, in your own words, {obj.lower()}?"
        )
    if category == "struggled":
        return (
            f'Your records show "{title}" didn\'t pass. Let\'s build up from fundamentals -- '
            f"can you explain, in your own words, {obj.lower()}? There's no wrong answer here, "
            f"I just want to understand how you think about it."
        )
    if category == "skipped":
        return (
            f'I see "{title}" was skipped during the cohort. Have you come across {tool_str} in any other context? '
            f"Even at a high level, what's your understanding of {obj.lower()}?"
        )
    return (
        f'Let\'s talk about "{title}" from the curriculum. Can you explain {obj.lower()} '
        f"and why it matters for a production AI system?"
    )


def fallback_followup(answer: str, item: Dict[str, Any]) -> str:
    title = item["title"]
    if _is_vague(answer):
        return (
            f'No worries -- let\'s simplify. In plain terms, what problem was "{title}" solving, '
            f"and why would a team care about it in a real system?"
        )
    probe = _PROBES_BY_TYPE.get(
        item.get("type"),
        "Can you go one level deeper -- what's a tradeoff or edge case you had to think through?",
    )
    return probe


def fallback_feedback(candidate: Dict[str, Any], transcript: List[Any], plan: List[dict]) -> Dict[str, Any]:
    member = candidate.get("member", {}) or {}
    name = member.get("name", "The candidate")

    by_day = {p["day"]: p for p in plan}
    strengths: List[str] = []
    gaps: List[str] = []
    seen_days = set()

    for entry in transcript:
        day = entry.day
        if day in seen_days:
            continue
        seen_days.add(day)
        item = by_day.get(day, {})
        title = entry.title
        answer = entry.answer or ""
        substantive = len(answer.strip()) >= 60 and not _is_vague(answer)
        category = item.get("category", "generic")

        if substantive and category in ("mastered", "shaky"):
            strengths.append(f"Solid, specific grasp of {title} (Day {day})")
        elif substantive and category == "generic":
            strengths.append(f"Engaged thoughtfully with {title} (Day {day})")
        elif category in ("struggled", "skipped") or not substantive:
            gaps.append(f"Needs reinforcement on {title} (Day {day}) -- {_CATEGORY_HINT.get(category, '')}".rstrip(" -"))

    has_real_strength = bool(strengths)
    if not strengths:
        strengths.append("Engaged with every question and completed the full interview")
    if not gaps:
        gaps.append("No major gaps surfaced in this session -- consider a deeper follow-on technical round")

    next_steps = [
        f"Revisit {p['title']} (Day {p['day']}) and be ready to explain it without notes"
        for p in plan
        if p.get("category") in ("struggled", "skipped")
    ][:3]
    if not next_steps:
        next_steps = [
            "Practice articulating system design tradeoffs out loud, not just describing what was built",
            "Prepare a 2-minute walkthrough of the capstone project for a non-technical stakeholder",
        ]

    tone = "strong" if len(strengths) >= len(gaps) else "developing"
    topics_preview = ", ".join(p["title"] for p in plan[:3])
    ellipsis = "..." if len(plan) > 3 else ""
    if has_real_strength:
        lead_strength = (
            strengths[0]
            .replace("Solid, specific grasp of ", "")
            .replace("Engaged thoughtfully with ", "")
            .split(" (")[0]
        )
        strength_clause = f", with the clearest strength around {lead_strength}"
    else:
        strength_clause = ", though answers stayed brief and made it hard to gauge depth on any one topic"
    summary = (
        f"{name} completed a {len(plan)}-topic technical interview covering {topics_preview}{ellipsis}. "
        f"Overall responses showed {tone} command of the material{strength_clause}."
    )

    return {
        "summary": summary,
        "strengths": strengths[:5],
        "gaps": gaps[:5],
        "next": next_steps[:5],
    }
