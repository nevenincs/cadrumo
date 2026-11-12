"""The filing periods the ledger read serves, checked against calendar facts written out by hand."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime
from importlib.resources import files
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from ....core.external_constants import OutputLanguage
from ....core.operations import profile_operation_subject
from ....core.time.clock import frozen_clock
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ..entry_options_operation import (
    LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
    LedgerEntryOptionsExecutionResult,
    LedgerEntryOptionsExecutor,
    LedgerEntryOptionsRequest,
    ledger_entry_options,
)
from ..period_options import (
    MAX_PERIOD_LOOKUP_DAYS,
    LedgerPeriodProjection,
    LedgerPeriodSpanRequest,
    LedgerPeriodsProjection,
    LedgerPeriodsQuery,
    ledger_periods,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("41414141-4141-4141-8141-414141414141")

# What a calendar says, written out by hand rather than computed.
_QUARTERS_2026 = {
    "1T": ("2026-01-01", "2026-03-31"),
    "2T": ("2026-04-01", "2026-06-30"),
    "3T": ("2026-07-01", "2026-09-30"),
    "4T": ("2026-10-01", "2026-12-31"),
}
_MONTH_ENDS_2026 = ("31", "28", "31", "30", "31", "30", "31", "31", "30", "31", "30", "31")
_MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "es": [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ],
    "ca": [
        "Gener",
        "Febrer",
        "Març",
        "Abril",
        "Maig",
        "Juny",
        "Juliol",
        "Agost",
        "Setembre",
        "Octubre",
        "Novembre",
        "Desembre",
    ],
    "hu": [
        "Január",
        "Február",
        "Március",
        "Április",
        "Május",
        "Június",
        "Július",
        "Augusztus",
        "Szeptember",
        "Október",
        "November",
        "December",
    ],
}
_YEAR_WORD = {"en": "Year", "es": "Año", "ca": "Any", "hu": "Év"}


def _periods(year: int, language: OutputLanguage = OutputLanguage.EN) -> dict[str, LedgerPeriodProjection]:
    served = ledger_periods(LedgerPeriodsQuery(year=year), reference_day=date(year, 6, 15), language=language)
    return {row.period.code: row for row in served.periods}


def test_a_year_lists_the_year_its_quarters_and_its_months_in_that_order() -> None:
    served = ledger_periods(LedgerPeriodsQuery(year=2026), reference_day=date(2026, 6, 15))

    assert served.year == 2026
    assert served.annual_code == "0A"
    assert [row.period.code for row in served.periods] == [
        "0A",
        "1T",
        "2T",
        "3T",
        "4T",
        *(f"{month:02d}" for month in range(1, 13)),
    ]
    assert {row.period.filing_year for row in served.periods} == {2026}
    assert [row.kind for row in served.periods] == ["annual", *["quarterly"] * 4, *["monthly"] * 12]


def test_the_year_listed_is_the_year_of_the_reference_day_unless_one_is_asked() -> None:
    assert ledger_periods(LedgerPeriodsQuery(), reference_day=date(2031, 2, 3)).year == 2031
    assert ledger_periods(LedgerPeriodsQuery(year=2019), reference_day=date(2031, 2, 3)).year == 2019


def test_each_quarter_and_the_year_span_the_days_the_calendar_gives_them() -> None:
    rows = _periods(2026)

    for code, (first, last) in _QUARTERS_2026.items():
        assert (rows[code].first_day.isoformat(), rows[code].last_day.isoformat()) == (first, last)
    assert (rows["0A"].first_day, rows["0A"].last_day) == (date(2026, 1, 1), date(2026, 12, 31))


def test_each_month_ends_on_the_last_day_of_its_month() -> None:
    rows = _periods(2026)

    for month, last in enumerate(_MONTH_ENDS_2026, start=1):
        row = rows[f"{month:02d}"]
        assert row.first_day.isoformat() == f"2026-{month:02d}-01"
        assert row.last_day.isoformat() == f"2026-{month:02d}-{last}"


@pytest.mark.parametrize(
    ("year", "february_ends"),
    [(2024, 29), (2025, 28), (2000, 29), (1900, 28), (2100, 28)],
)
def test_february_ends_on_the_day_the_gregorian_calendar_gives_it(year: int, february_ends: int) -> None:
    assert _periods(year)["02"].last_day == date(year, 2, february_ends)


@pytest.mark.parametrize(
    ("year", "code", "previous", "following"),
    [
        (2026, "1T", (2025, "4T"), (2026, "2T")),
        (2026, "4T", (2026, "3T"), (2027, "1T")),
        (2026, "01", (2025, "12"), (2026, "02")),
        (2026, "12", (2026, "11"), (2027, "01")),
        (2026, "0A", (2025, "0A"), (2027, "0A")),
        (2026, "07", (2026, "06"), (2026, "08")),
    ],
)
def test_the_neighbours_of_a_period_step_across_year_ends(
    year: int, code: str, previous: tuple[int, str], following: tuple[int, str]
) -> None:
    row = _periods(year)[code]

    assert row.previous is not None
    assert row.next is not None
    assert (row.previous.filing_year, row.previous.code) == previous
    assert (row.next.filing_year, row.next.code) == following


def test_a_period_beyond_the_years_that_can_be_written_has_no_neighbour_there() -> None:
    last = _periods(9999)
    first = _periods(1000)

    assert last["4T"].next is None
    assert last["12"].next is None
    assert last["0A"].next is None
    assert first["1T"].previous is None
    assert first["01"].previous is None
    assert first["0A"].previous is None
    assert last["4T"].previous is not None
    assert first["1T"].next is not None


def test_stepping_forward_and_back_returns_to_the_period_started_from() -> None:
    rows = {year: _periods(year) for year in (2024, 2025, 2026, 2027)}
    for year, by_code in rows.items():
        for code, row in by_code.items():
            if row.next is not None and row.next.filing_year in rows:
                back = rows[row.next.filing_year][row.next.code].previous
                assert back is not None
                assert (back.filing_year, back.code) == (year, code)


@pytest.mark.parametrize(
    ("day", "year", "quarter", "month"),
    [
        (date(2026, 3, 31), 2026, "1T", "03"),
        (date(2026, 4, 1), 2026, "2T", "04"),
        (date(2026, 6, 30), 2026, "2T", "06"),
        (date(2026, 7, 1), 2026, "3T", "07"),
        (date(2026, 9, 30), 2026, "3T", "09"),
        (date(2026, 10, 1), 2026, "4T", "10"),
        (date(2025, 12, 31), 2025, "4T", "12"),
        (date(2026, 1, 1), 2026, "1T", "01"),
        (date(2024, 2, 29), 2024, "1T", "02"),
    ],
)
def test_the_periods_holding_a_day_follow_the_calendar_at_every_boundary(
    day: date, year: int, quarter: str, month: str
) -> None:
    served = ledger_periods(LedgerPeriodsQuery(days=(day,)), reference_day=date(2026, 6, 15))

    (found,) = served.days
    assert found.day == day
    assert [(p.filing_year, p.code) for p in (found.annual, found.quarterly, found.monthly)] == [
        (year, "0A"),
        (year, quarter),
        (year, month),
    ]


def test_the_days_asked_come_back_in_the_order_asked() -> None:
    asked = (date(2026, 12, 31), date(2026, 1, 1), date(2026, 6, 30))

    served = ledger_periods(LedgerPeriodsQuery(days=asked), reference_day=date(2026, 6, 15))

    assert tuple(found.day for found in served.days) == asked


def test_the_reference_day_names_the_periods_that_hold_it() -> None:
    served = ledger_periods(LedgerPeriodsQuery(), reference_day=date(2026, 11, 3))

    assert [(p.filing_year, p.code) for p in (served.containing.annual, served.containing.quarterly)] == [
        (2026, "0A"),
        (2026, "4T"),
    ]
    assert served.containing.monthly.code == "11"
    assert served.containing.day == date(2026, 11, 3)


@pytest.mark.parametrize(
    ("instant", "year", "quarter", "month"),
    [
        # 23:30 UTC on New Year's Eve is already 1 January in Madrid.
        (datetime(2025, 12, 31, 23, 30, tzinfo=UTC), 2026, "1T", "01"),
        (datetime(2025, 12, 31, 22, 30, tzinfo=UTC), 2025, "4T", "12"),
        # 22:30 UTC on 31 March is 00:30 on 1 April in Madrid, summer time.
        (datetime(2026, 3, 31, 22, 30, tzinfo=UTC), 2026, "2T", "04"),
        (datetime(2026, 3, 31, 21, 30, tzinfo=UTC), 2026, "1T", "03"),
    ],
)
def test_with_no_reference_day_the_default_period_holds_todays_date_in_spain(
    instant: datetime, year: int, quarter: str, month: str
) -> None:
    with frozen_clock(instant):
        served = ledger_periods(LedgerPeriodsQuery())

    assert served.year == year
    assert (served.containing.quarterly.filing_year, served.containing.quarterly.code) == (year, quarter)
    assert served.containing.monthly.code == month


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (date(2026, 3, 1), date(2026, 3, 31), (2026, "03")),
        (date(2026, 3, 5), date(2026, 3, 5), (2026, "03")),
        (date(2026, 1, 31), date(2026, 3, 1), (2026, "1T")),
        (date(2026, 1, 1), date(2026, 3, 31), (2026, "1T")),
        (date(2026, 3, 31), date(2026, 4, 1), (2026, "0A")),
        (date(2026, 1, 1), date(2026, 12, 31), (2026, "0A")),
        (date(2025, 12, 31), date(2026, 1, 1), None),
        (date(2024, 12, 31), date(2026, 1, 1), None),
    ],
)
def test_the_period_covering_a_span_is_the_shortest_one_that_holds_it(
    first: date, last: date, expected: tuple[int, str] | None
) -> None:
    served = ledger_periods(
        LedgerPeriodsQuery(covering=LedgerPeriodSpanRequest(first_day=first, last_day=last)),
        reference_day=date(2026, 6, 15),
    )

    assert served.covering is not None
    assert (served.covering.first_day, served.covering.last_day) == (first, last)
    found = served.covering.period
    assert (None if found is None else (found.filing_year, found.code)) == expected


def test_no_covering_is_served_unless_a_span_is_asked() -> None:
    assert ledger_periods(LedgerPeriodsQuery(), reference_day=date(2026, 6, 15)).covering is None


@pytest.mark.parametrize("language", list(OutputLanguage), ids=lambda language: language.value)
def test_every_period_is_named_in_the_language_asked(language: OutputLanguage) -> None:
    rows = _periods(2026, language)
    code = language.value

    assert rows["0A"].name_words == _YEAR_WORD[code]
    assert rows["0A"].label_words == "2026"
    for month, name in enumerate(_MONTHS[code], start=1):
        row = rows[f"{month:02d}"]
        assert row.name_words == name
        assert row.label_words == f"2026 · {name}"
    for quarter in ("1T", "2T", "3T", "4T"):
        assert rows[quarter].name_words == quarter
        assert rows[quarter].label_words == f"2026 · {quarter}"
    for row in rows.values():
        assert row.name_words_language is language
        assert row.label_words_language is language


def test_the_four_languages_word_the_year_and_every_month_differently_from_each_other() -> None:
    by_language = {language: _periods(2026, language) for language in OutputLanguage}

    for code in ("0A", *(f"{month:02d}" for month in range(1, 13))):
        words = [by_language[language][code].name_words for language in OutputLanguage]
        assert len(set(words)) >= 3, (code, words)


@pytest.mark.parametrize("locale", [language.value for language in OutputLanguage])
def test_every_period_word_is_authored_in_the_locale_catalogue(locale: str) -> None:
    catalogue = yaml.safe_load(
        files("cadrumo").joinpath("locales", locale, "application.yml").read_text(encoding="utf-8")
    )
    served = catalogue["application"]["ledger"]["periods"]["served"]

    assert set(served) == {
        "annual",
        "label",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
    assert all(isinstance(word, str) and word.strip() for word in served.values())


def test_a_day_in_a_year_no_period_can_be_named_for_is_refused_at_the_request() -> None:
    with pytest.raises(ValidationError):
        LedgerPeriodsQuery(days=(date(999, 1, 1),))
    with pytest.raises(ValidationError):
        LedgerPeriodSpanRequest(first_day=date(999, 1, 1), last_day=date(1000, 1, 1))
    with pytest.raises(ValidationError):
        LedgerEntryOptionsRequest(profile_id=_PROFILE, on_date=date(500, 1, 1))
    with pytest.raises(ValidationError):
        LedgerPeriodsQuery(year=999)


def test_a_span_that_ends_before_it_begins_is_refused() -> None:
    with pytest.raises(ValidationError):
        LedgerPeriodSpanRequest(first_day=date(2026, 3, 2), last_day=date(2026, 3, 1))


def test_the_days_a_request_may_ask_about_are_bounded() -> None:
    LedgerPeriodsQuery(days=(date(2026, 1, 1),) * MAX_PERIOD_LOOKUP_DAYS)
    with pytest.raises(ValidationError):
        LedgerPeriodsQuery(days=(date(2026, 1, 1),) * (MAX_PERIOD_LOOKUP_DAYS + 1))


def test_the_request_reads_its_period_questions_from_json() -> None:
    request = LedgerEntryOptionsRequest.model_validate_json(
        '{"profile_id": "41414141-4141-4141-8141-414141414141", "output_language": "hu",'
        ' "periods": {"year": 2025, "days": ["2026-03-31"],'
        ' "covering": {"first_day": "2026-01-02", "last_day": "2026-02-03"}}}'
    )

    assert request.output_language is OutputLanguage.HU
    assert request.periods.year == 2025
    assert request.periods.days == (date(2026, 3, 31),)
    assert request.periods.covering == LedgerPeriodSpanRequest(first_day=date(2026, 1, 2), last_day=date(2026, 2, 3))


def test_a_request_that_asks_for_no_period_gets_the_spanish_names_of_the_current_year() -> None:
    request = LedgerEntryOptionsRequest(profile_id=_PROFILE)

    assert request.output_language is OutputLanguage.ES
    assert request.periods == LedgerPeriodsQuery()


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


class _Operands:
    def __init__(self) -> None:
        self.stored: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        self.stored.append(value)
        return "ref"


class _Events:
    async def phase(self, name: str) -> None:
        del name


def test_the_entry_options_read_serves_the_periods_with_the_vocabularies(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cadrumo.application.ledger.entry_options_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    subject = profile_operation_subject(str(_PROFILE))
    payload = LedgerEntryOptionsRequest(
        profile_id=_PROFILE,
        on_date=date(2026, 1, 1),
        output_language=OutputLanguage.CA,
        periods=LedgerPeriodsQuery(year=2025, days=(date(2025, 12, 31),)),
    )
    request = OperationRequest[LedgerEntryOptionsRequest](
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID, subject_ref=subject, payload=payload
    )
    operands = _Operands()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="b" * 64, definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID, subject_ref=subject
        ),
        events=_Events(),
        operands=operands,
        authority_operation=operation,
    )

    asyncio.run(
        LedgerEntryOptionsExecutor(lambda _bucket, _operation: None).execute(
            request, cast(OperationExecutorContext, context)
        )
    )

    (stored,) = operands.stored
    assert isinstance(stored, LedgerEntryOptionsExecutionResult)
    periods = stored.result.periods
    assert isinstance(periods, LedgerPeriodsProjection)
    assert periods.year == 2025
    assert (periods.containing.quarterly.filing_year, periods.containing.quarterly.code) == (2026, "1T")
    (day,) = periods.days
    assert (day.quarterly.filing_year, day.quarterly.code) == (2025, "4T")
    assert {row.name_words_language for row in periods.periods} == {OutputLanguage.CA}
    assert next(row for row in periods.periods if row.period.code == "03").name_words == "Març"
    assert stored.result.families


def test_the_vocabularies_and_the_periods_are_one_projection_that_survives_the_wire(
    operation: PinnedAuthorityOperation,
) -> None:
    served = ledger_entry_options(
        _PROFILE,
        operation=operation,
        on_date=date(2026, 2, 3),
        periods=LedgerPeriodsQuery(days=(date(2026, 3, 31),)),
        language=OutputLanguage.HU,
    )

    restored = type(served).model_validate_json(served.model_dump_json())

    assert restored == served
    assert restored.periods.containing.day == date(2026, 2, 3)
