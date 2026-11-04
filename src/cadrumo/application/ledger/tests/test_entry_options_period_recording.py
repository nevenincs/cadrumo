"""The periods the desktop fixtures serve are what the ledger's period read answers.

The window does no period arithmetic: it shows the periods ``ledger.entry-options``
serves. Its fixtures and tests therefore answer from a recording of that read,
kept in the entry-options recording beside the vocabularies, and these tests hold
the recording to the backend's own projection. Set
``CADRUMO_RECORD_ENTRY_OPTION_PERIODS`` to write it again.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from ....core.external_constants import OutputLanguage
from ..period_options import LedgerPeriodSpanRequest, LedgerPeriodsQuery, ledger_periods

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECORDING: Final = Path(__file__).resolve().parents[5] / (
    "native/desktop/frontend/src/dev/fixtures/ledgerEntryOptions.json"
)
_REFERENCE_DAY: Final = date(2026, 11, 4)
_EVERY_LANGUAGE_YEARS: Final = (2024, 2025, 2026, 2027)
_ENGLISH_YEARS: Final = (2003, 2011, 2012, 2019, 2020, 2023)
_PROBE_DAYS: Final = (
    date(2003, 7, 1),
    date(2024, 2, 29),
    date(2024, 12, 31),
    date(2025, 1, 1),
    date(2025, 2, 28),
    date(2026, 3, 31),
    date(2026, 4, 1),
    date(2026, 10, 15),
    date(2026, 11, 4),
    date(2026, 12, 31),
)
_PROBE_SPANS: Final = (
    (date(2026, 10, 1), date(2026, 10, 31)),
    (date(2026, 10, 5), date(2026, 10, 20)),
    (date(2026, 7, 1), date(2026, 9, 30)),
    (date(2026, 8, 15), date(2026, 11, 2)),
    (date(2026, 1, 1), date(2026, 12, 31)),
    (date(2025, 12, 30), date(2026, 1, 2)),
    (date(2024, 2, 29), date(2024, 2, 29)),
)
_PROBE_QUERY: Final = LedgerPeriodsQuery(
    days=_PROBE_DAYS,
)


def _projection(language: OutputLanguage, query: LedgerPeriodsQuery) -> dict[str, Any]:
    served = ledger_periods(query, reference_day=_REFERENCE_DAY, language=language)
    return json.loads(served.model_dump_json())


def _years() -> dict[str, dict[str, list[dict[str, Any]]]]:
    wanted = {OutputLanguage.EN.value: _EVERY_LANGUAGE_YEARS + _ENGLISH_YEARS}
    for language in OutputLanguage:
        wanted.setdefault(language.value, _EVERY_LANGUAGE_YEARS)
    return {
        language: {
            str(year): _projection(OutputLanguage(language), LedgerPeriodsQuery(year=year))["periods"]
            for year in sorted(years)
        }
        for language, years in sorted(wanted.items())
    }


def _recorded() -> dict[str, Any]:
    periods = _projection(OutputLanguage.EN, LedgerPeriodsQuery(year=_REFERENCE_DAY.year))
    probed = _projection(OutputLanguage.EN, _PROBE_QUERY)
    return {
        "reference_day": _REFERENCE_DAY.isoformat(),
        "annual_code": periods["annual_code"],
        "containing": periods["containing"],
        "years": _years(),
        "probes": {
            "days": probed["days"],
            "covering": [
                _projection(
                    OutputLanguage.EN,
                    LedgerPeriodsQuery(covering=LedgerPeriodSpanRequest(first_day=first, last_day=last)),
                )["covering"]
                for first, last in _PROBE_SPANS
            ],
        },
    }


def test_the_recorded_periods_are_what_the_backend_answers() -> None:
    stored = json.loads(_RECORDING.read_text(encoding="utf-8"))

    assert stored["periods"] == _recorded()


def test_the_recording_names_a_year_in_every_language() -> None:
    stored = json.loads(_RECORDING.read_text(encoding="utf-8"))["periods"]

    assert set(stored["years"]) == {language.value for language in OutputLanguage}
    for language, years in stored["years"].items():
        assert set(years) >= {str(year) for year in _EVERY_LANGUAGE_YEARS}, language


if os.environ.get("CADRUMO_RECORD_ENTRY_OPTION_PERIODS", "") != "":

    def test_record_the_periods() -> None:
        stored = json.loads(_RECORDING.read_text(encoding="utf-8"))
        stored["periods"] = _recorded()
        _RECORDING.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
