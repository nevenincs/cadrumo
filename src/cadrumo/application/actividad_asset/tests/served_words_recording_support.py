"""The questions the desktop's register-words recording asks, and what the register says to each.

The window words nothing of the register's: its fixtures look each reason, remedy,
handoff interval and left-out reason up in a recording keyed by exactly what was
asked. The questions are committed under ``dev/fixtures/assets-served-words-questions``,
one question text per line, as the frontend's capture writes them. The producer and
the test both answer them here, through the register's own words.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from ....core.external_constants import OutputLanguage
from ..activity_asset_read_models import (
    ActivityAssetHandoffLeftOutReason,
    ActivityAssetReasonFact,
    ActivityAssetReasonFactKind,
)
from ..schedule_walk import M100GapKind
from ..served_words import left_out_entry, m100_gap_words, partial_words, reason_words, remedy_words

_REPOSITORY: Final = Path(__file__).resolve().parents[5]
RECORDING: Final = _REPOSITORY / "native/desktop/frontend/src/dev/fixtures/assetsServedWords.json"
QUESTIONS: Final = _REPOSITORY / "dev/fixtures/assets-served-words-questions/questions.jsonl"
NOTE: Final = (
    "What the activity-asset register said for each reason with its facts, remedy, handoff interval and "
    "left-out reason the scenario fixtures ask about, in each language, keyed by exactly what was asked. "
    "Written by scripts/assets_served_words.py from dev/fixtures/assets-served-words-questions."
)


def parse_questions(lines: Iterable[str]) -> tuple[str, ...]:
    """Read question lines, refusing a line that is not a question object or a question asked twice."""
    asked: list[str] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if not isinstance(json.loads(line), dict):
            raise ValueError(f"question line {number}: a question is a JSON object")
        if line in asked:
            raise ValueError(f"question line {number}: the question is asked twice")
        asked.append(line)
    return tuple(asked)


def committed_questions() -> tuple[str, ...]:
    """The questions committed for the recording."""
    return parse_questions(QUESTIONS.read_text(encoding="utf-8").splitlines())


def _said(question: dict[str, Any], language: OutputLanguage) -> str | None:
    kind = question["kind"]
    if kind == "reason":
        facts = tuple(
            ActivityAssetReasonFact(
                key=fact["key"], value=fact["value"], kind=ActivityAssetReasonFactKind(fact["kind"])
            )
            for fact in question["facts"]
        )
        return reason_words(question["key"], facts, language)
    if kind == "remedy":
        return remedy_words(question["field_key"], language)
    if kind == "gap":
        accrued = question["accrued"]
        return m100_gap_words(
            M100GapKind(question["gap_kind"]),
            name=question["name"],
            covered_from=date.fromisoformat(question["covered_from"]),
            covered_through=date.fromisoformat(question["covered_through"]),
            accrued=None if accrued is None else Decimal(accrued),
            language=language,
        )
    if kind == "partial":
        return partial_words(question["count"], language)
    if kind == "left_out":
        ids = tuple(f"asset-{at}" for at, _ in enumerate(question["names"]))
        names = {asset_id: name for asset_id, name in zip(ids, question["names"], strict=True) if name is not None}
        return left_out_entry(ActivityAssetHandoffLeftOutReason(question["reason"]), ids, names, language).words
    raise ValueError(f"unknown question kind {kind}")


def answers(question_text: str) -> dict[str, str | None]:
    """What the register says to one question, in every language."""
    question = json.loads(question_text)
    return {language.value: _said(question, language) for language in OutputLanguage}


def recording(questions: Iterable[str]) -> dict[str, Any]:
    """The recording: every committed question beside the register's words for it."""
    return {"note": NOTE, "entries": {question: answers(question) for question in sorted(questions)}}
