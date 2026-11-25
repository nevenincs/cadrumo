"""The period questions the desktop's entry-options recording asks, and the ledger's period read's answers.

The window does no period arithmetic: it shows the periods ``ledger.entry-options``
serves, from a recording kept in the entry-options fixture beside the vocabularies.
The questions (the reference day, the years asked in every language and in English
only, and the probed days and spans) are committed in
``dev/fixtures/ledger-entry-option-questions/periods.json``. The producer and the test
both answer them here, through the ledger's own period read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ine_provincia_catalogue import ine_provincia_names
from ..entry_limits import ledger_entry_limits
from ..entry_options_operation import ledger_entry_options
from ..period_options import LedgerPeriodSpanRequest, LedgerPeriodsQuery, ledger_periods

QUESTIONS: Final = Path(__file__).resolve().parents[5] / "dev/fixtures/ledger-entry-option-questions/periods.json"

#: The families the window trims instead of recording: its own entry forms hold these lists.
TRIMMED_FAMILIES: Final = frozenset({"country", "currency", "m210_payer_mode", "m210_tipo_renta"})
_PROFILE: Final = UUID("31313131-3131-4131-8131-313131313131")
NOTE: Final = (
    "The registry-served families of `ledger.entry-options`, in the shape `aeat app ledger entry-options --json` "
    "emits, read from the pinned authority through the operation's own projection. The country, currency and M210 "
    "families are trimmed in the fixture instead. The provinces a counterparty can be stated in are the INE catalogue's, "
    "in code order, as `ledger.counterparty` serves them."
)


@dataclass(frozen=True, slots=True)
class PeriodQuestions:
    """What the recording asks the period read."""

    reference_day: date
    every_language_years: tuple[int, ...]
    english_years: tuple[int, ...]
    probe_days: tuple[date, ...]
    probe_spans: tuple[tuple[date, date], ...]


def parse_questions(document: dict[str, Any]) -> PeriodQuestions:
    """Read the period questions, refusing a missing or extra key."""
    expected = {"reference_day", "every_language_years", "english_years", "probe_days", "probe_spans"}
    if set(document) != expected:
        raise ValueError(f"period questions need exactly the keys {sorted(expected)}")
    return PeriodQuestions(
        reference_day=date.fromisoformat(document["reference_day"]),
        every_language_years=tuple(int(year) for year in document["every_language_years"]),
        english_years=tuple(int(year) for year in document["english_years"]),
        probe_days=tuple(date.fromisoformat(day) for day in document["probe_days"]),
        probe_spans=tuple(
            (date.fromisoformat(first), date.fromisoformat(last)) for first, last in document["probe_spans"]
        ),
    )


def committed_questions() -> PeriodQuestions:
    """The period questions committed for the recording."""
    return parse_questions(json.loads(QUESTIONS.read_text(encoding="utf-8")))


def _projection(language: OutputLanguage, query: LedgerPeriodsQuery, reference_day: date) -> dict[str, Any]:
    served = ledger_periods(query, reference_day=reference_day, language=language)
    return json.loads(served.model_dump_json())


def _years(questions: PeriodQuestions) -> dict[str, dict[str, list[dict[str, Any]]]]:
    wanted = {OutputLanguage.EN.value: questions.every_language_years + questions.english_years}
    for language in OutputLanguage:
        wanted.setdefault(language.value, questions.every_language_years)
    return {
        language: {
            str(year): _projection(OutputLanguage(language), LedgerPeriodsQuery(year=year), questions.reference_day)[
                "periods"
            ]
            for year in sorted(years)
        }
        for language, years in sorted(wanted.items())
    }


def recorded_periods(questions: PeriodQuestions) -> dict[str, Any]:
    """The ``periods`` section of the recording: the period read's answer to every question."""
    day = questions.reference_day
    periods = _projection(OutputLanguage.EN, LedgerPeriodsQuery(year=day.year), day)
    probed = _projection(OutputLanguage.EN, LedgerPeriodsQuery(days=questions.probe_days), day)
    return {
        "reference_day": day.isoformat(),
        "annual_code": periods["annual_code"],
        "containing": periods["containing"],
        "years": _years(questions),
        "probes": {
            "days": probed["days"],
            "covering": [
                _projection(
                    OutputLanguage.EN,
                    LedgerPeriodsQuery(covering=LedgerPeriodSpanRequest(first_day=first, last_day=last)),
                    day,
                )["covering"]
                for first, last in questions.probe_spans
            ],
        },
    }


def recording(questions: PeriodQuestions, operation: PinnedAuthorityOperation) -> dict[str, Any]:
    """The whole entry-options recording: the served vocabularies, classification rules, limits and periods."""
    served = ledger_entry_options(_PROFILE, operation=operation)
    return {
        "note": NOTE,
        "default_currency": served.default_currency,
        "families": [
            family.model_dump(mode="json") for family in served.families if family.family not in TRIMMED_FAMILIES
        ],
        "classifications": [item.model_dump(mode="json") for item in served.classifications],
        "limits": ledger_entry_limits().model_dump(mode="json"),
        "periods": recorded_periods(questions),
        "counterparty_provincias": [
            {"code": code, "name": name} for code, name in ine_provincia_names(authority=operation).items()
        ],
    }
