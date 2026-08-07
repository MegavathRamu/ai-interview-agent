"""Loads and indexes the 31-day curriculum for fast lookup by day number."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

with open(DATA_DIR / "curriculum.json") as f:
    _RAW = json.load(f)

COHORT_NAME: str = _RAW.get("cohort", "AI Cohort")
MODULES: List[Dict[str, Any]] = _RAW.get("modules", [])
CURRICULUM_DAYS: Dict[int, Dict[str, Any]] = {d["day"]: d for d in _RAW.get("days", [])}


def module_for_day(day: int) -> Optional[Dict[str, Any]]:
    for m in MODULES:
        lo, hi = m["days"]
        if lo <= day <= hi:
            return m
    return None
