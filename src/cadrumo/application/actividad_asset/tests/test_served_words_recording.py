"""The sentences the desktop fixtures serve for the register are what the register says.

The window words nothing of the register's: its fixtures look each reason, remedy,
handoff interval and left-out reason up in a recording of what the register said in
each language, kept in the desktop frontend's fixtures. This test holds every
recorded sentence equal to the register's own and records the questions the
fixtures could not answer. Set ``CADRUMO_ASSET_WORDS_UNRECORDED`` to a file of
questions, one JSON object per line, to answer them and refresh the recording, or
to ``all`` to answer again every question the recording holds.
"""

from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import pytest

from ....core.external_constants import OutputLanguage
from ..activity_asset_read_models import (
    ActivityAssetHandoffLeftOutReason,
    ActivityAssetReasonFact,
    ActivityAssetReasonFactKind,
)
from ..schedule_walk import M100GapKind
from ..served_words import left_out_entry, m100_gap_words, partial_words, reason_words, remedy_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECORDING: Final = Path(__file__).resolve().parents[5] / (
    "native/desktop/frontend/src/dev/fixtures/assetsServedWords.json"
)
_NOTE: Final = (
    "What the activity-asset register said for each reason with its facts, remedy, handoff interval and "
    "left-out reason the scenario fixtures ask about, in each language, keyed by exactly what was asked. "
    "Written and held equal to the register's own words by test_served_words_recording.py."
)


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
    raise AssertionError(f"unknown question kind {kind}")


def _answers(question_text: str) -> dict[str, str | None]:
    question = json.loads(question_text)
    return {language.value: _said(question, language) for language in OutputLanguage}


def _recording() -> dict[str, Any]:
    return json.loads(_RECORDING.read_text(encoding="utf-8"))


def test_every_recorded_sentence_is_what_the_register_says() -> None:
    recording = _recording()
    assert recording["entries"], "the recording is empty"
    for question_text, answers in recording["entries"].items():
        assert answers == _answers(question_text), question_text


def test_a_recorded_question_names_a_language_for_every_supported_one() -> None:
    for question_text, answers in _recording()["entries"].items():
        assert set(answers) == {language.value for language in OutputLanguage}, question_text


# Defined only when given the questions, since with none there is nothing to record.
if os.environ.get("CADRUMO_ASSET_WORDS_UNRECORDED", "") != "":

    def test_record_the_questions_the_fixtures_could_not_answer() -> None:
        recording = _recording() if _RECORDING.exists() else {"entries": {}}
        source = os.environ["CADRUMO_ASSET_WORDS_UNRECORDED"]
        asked = (
            list(recording["entries"])
            if source == "all"
            else [line for line in Path(source).read_text(encoding="utf-8").splitlines() if line.strip()]
        )
        entries = dict(recording["entries"])
        for question_text in asked:
            entries[question_text] = _answers(question_text)
        written = {"note": _NOTE, "entries": dict(sorted(entries.items()))}
        _RECORDING.write_text(json.dumps(written, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
