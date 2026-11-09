"""Shared paths for SurveyMathWorker editor Python scripts."""
from __future__ import annotations

import json
from pathlib import Path

# Content/Python → project root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SURVEY_ROOT = Path(r"G:\Stolen Hours\survey\Map_000100")
LOCAL_JSON = Path(__file__).resolve().parent


def survey_dir() -> Path:
    if SURVEY_ROOT.parent.exists() or Path(r"G:\Stolen Hours").exists():
        SURVEY_ROOT.mkdir(parents=True, exist_ok=True)
        return SURVEY_ROOT
    p = PROJECT_ROOT / "Saved" / "survey" / "Map_000100"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json(name: str) -> dict:
    for base in (survey_dir(), LOCAL_JSON):
        path = base / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"{name} not found — run: py -3.12 -m stolenhours.survey_math export")
