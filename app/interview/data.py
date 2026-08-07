"""Loads the sample candidate roster from candidates.json, purely to power the
browser UI's candidate picker (see /api/candidates in main.py). The core
interview endpoint does not depend on this -- a real client is expected to
already have its own candidate object to send, per the technical spec.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

with open(DATA_DIR / "candidates.json") as f:
    _RAW = json.load(f)

_CANDIDATES: List[Dict[str, Any]] = _RAW.get("candidates", [])

CANDIDATES_BY_ID: Dict[str, Dict[str, Any]] = {c["member"]["id"]: c for c in _CANDIDATES if "member" in c}

CANDIDATE_SUMMARIES: List[Dict[str, str]] = [
    {"id": c["member"]["id"], "name": c["member"]["name"], "jobRole": c["member"]["jobRole"]}
    for c in _CANDIDATES
    if "member" in c
]
