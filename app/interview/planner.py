"""Builds a personalized interview question plan from a candidate's mission history.

Selection strategy:
- Candidates who passed a mission on the first try get harder, deeper questions on
  that topic (they demonstrated mastery).
- Candidates who passed only after multiple attempts get "verify understanding"
  questions (did they actually learn it, or just muscle through it?).
- Candidates who explicitly failed a mission (passed: false) get foundational
  questions, asked kindly.
- Candidates who skipped a mission get an awareness-level question rather than an
  assumption of mastery.
- If a candidate's mission log doesn't yield enough distinct days (very sparse
  profiles), the plan is padded with generic, widely-covered curriculum days so
  every interview still spans at least 4 distinct days / 8 questions.
"""
from typing import Any, Dict, List, Set

# Days nearly every candidate profile touches, used to pad sparse profiles.
GENERIC_FALLBACK_DAYS = [12, 1, 31, 22, 8, 27, 16, 7, 10, 23]

DEFAULT_TARGET_LEN = 6
DEFAULT_MIN_LEN = 4


def _categorize(missions: List[dict]):
    mastered, shaky, struggled, skipped = [], [], [], []
    for m in missions:
        if not isinstance(m, dict) or "day" not in m:
            continue
        if m.get("skipped"):
            skipped.append(m)
        elif m.get("passed") is True:
            if (m.get("attempts") or 1) <= 1:
                mastered.append(m)
            else:
                shaky.append(m)
        elif m.get("passed") is False:
            struggled.append(m)
        # missions with no passed/skipped info are ignored -- not enough signal
    return mastered, shaky, struggled, skipped


def _take(items: List[dict], n: int, seen: Set[int]) -> List[dict]:
    out = []
    for m in items:
        if len(out) >= n:
            break
        if m["day"] in seen:
            continue
        out.append(m)
        seen.add(m["day"])
    return out


def _classify_one(m: dict) -> str:
    if m.get("generic"):
        return "generic"
    if m.get("skipped"):
        return "skipped"
    if m.get("passed") is True:
        return "mastered" if (m.get("attempts") or 1) <= 1 else "shaky"
    if m.get("passed") is False:
        return "struggled"
    return "generic"


def build_plan(
    candidate: Dict[str, Any],
    curriculum_days: Dict[int, dict],
    target_len: int = DEFAULT_TARGET_LEN,
    min_len: int = DEFAULT_MIN_LEN,
) -> List[Dict[str, Any]]:
    missions = candidate.get("missions") or []
    mastered, shaky, struggled, skipped = _categorize(missions)

    seen: Set[int] = set()
    picks: List[dict] = []
    # Aim for a diverse mix: strong topics, weak topics, shaky topics, skipped topics.
    picks += _take(mastered, 2, seen)
    picks += _take(struggled, 2, seen)
    picks += _take(shaky, 2, seen)
    picks += _take(skipped, 2, seen)

    # Fill any remaining slots up to target_len from whatever's left, priority order.
    for pool in (mastered, shaky, struggled, skipped):
        if len(picks) >= target_len:
            break
        picks += _take(pool, target_len - len(picks), seen)

    # Guarantee the floor even for candidates with very sparse mission logs.
    for day in GENERIC_FALLBACK_DAYS:
        if len(picks) >= max(min_len, target_len):
            break
        if day in seen or day not in curriculum_days:
            continue
        picks.append({"day": day, "title": curriculum_days[day]["title"], "generic": True})
        seen.add(day)

    picks = picks[:target_len]

    plan: List[Dict[str, Any]] = []
    for m in picks:
        day = m["day"]
        cd = curriculum_days.get(day, {})
        plan.append(
            {
                "day": day,
                "title": cd.get("title", m.get("title", f"Day {day}")),
                "type": cd.get("type", "BUILD"),
                "tools": cd.get("tools", []),
                "objectives": cd.get("objectives", []),
                "category": _classify_one(m),
                "attempts": m.get("attempts"),
            }
        )
    # Keep the plan in day order so the interview flows chronologically through the cohort.
    plan.sort(key=lambda p: p["day"])
    return plan
