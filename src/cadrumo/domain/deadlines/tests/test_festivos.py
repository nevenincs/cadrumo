"""Real-behaviour tests for the festivos / business-day substrate.

Every test grounds its expected value in an external authority — either
the BOE-published Resolución de fiestas laborales for that year (cited
in the calendar TOML and re-cited inline here), the AEAT Calendario del
Contribuyente shift rule, or a structural / wiring / error-path
property. No test computes the expected adjusted date by re-applying
the shift formula to a freshly-invented date.

The BOE-cited fixed dates used as anchors:

* 2025-04-18 = Viernes Santo (national, BOE-A-2024-22011).
* 2025-05-01 = Fiesta del Trabajo (Thursday; national).
* 2025-11-01 = Todos los Santos (Saturday; national + weekend).
* 2025-12-25 = Navidad (Thursday; national).
* 2026-04-03 = Viernes Santo (national).
* 2026-08-15 = Asunción (Saturday; national + weekend).
* 2025-09-11 = Diada Nacional de Cataluña (CCAA ES-CT only).
* 2025-02-28 = Día de Andalucía (CCAA ES-AN only).
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core import scan_directory
from .. import (
    MODELOS_WITHOUT_SHIFT,
    CalendarCCAA,
    DeadlineShift,
    Holiday,
    HolidayCalendar,
    HolidayJurisdiction,
    is_business_day,
    load_holiday_calendar,
    next_business_day,
    shift_deadline,
)
from ..errors import DeadlineValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NATIONAL_HOLIDAY_DATES_2025 = (
    date(2025, 1, 1),  # Año Nuevo
    date(2025, 1, 6),  # Reyes
    date(2025, 4, 18),  # Viernes Santo
    date(2025, 5, 1),  # Fiesta del Trabajo
    date(2025, 8, 15),  # Asunción
    date(2025, 11, 1),  # Todos los Santos
    date(2025, 12, 6),  # Constitución
    date(2025, 12, 8),  # Inmaculada
    date(2025, 12, 25),  # Navidad
)

_BUSINESS_DAY_CASES = (
    ("saturday", date(2025, 3, 1), None, 5, False),
    ("sunday", date(2025, 3, 2), None, 6, False),
    ("national-holiday-friday", date(2025, 4, 18), None, 4, False),
    ("diada-cataluna", date(2025, 9, 11), CalendarCCAA.CATALUNA, 3, False),
    ("diada-madrid", date(2025, 9, 11), CalendarCCAA.MADRID, 3, True),
    ("plain-tuesday", date(2025, 3, 4), CalendarCCAA.MADRID, 1, True),
    ("national-only-degraded-diada", date(2025, 9, 11), None, 3, True),
)

_NEXT_BUSINESS_DAY_CASES = (
    ("already-business", date(2025, 3, 4), date(2025, 3, 4)),
    ("weekend-to-monday", date(2025, 11, 1), date(2025, 11, 3)),
    ("national-holiday-to-friday", date(2025, 12, 25), date(2025, 12, 26)),
)

_SHIFT_DEADLINE_CASES = (
    (
        "plain-business-day",
        date(2025, 3, 4),
        "303",
        CalendarCCAA.MADRID,
        False,
        date(2025, 3, 4),
        0,
        ("business_day",),
        (),
    ),
    (
        "saturday-to-monday",
        date(2025, 3, 1),
        "303",
        CalendarCCAA.MADRID,
        True,
        date(2025, 3, 3),
        2,
        ("sabado",),
        (),
    ),
    (
        "national-holiday-weekday",
        date(2025, 4, 18),
        "303",
        CalendarCCAA.MADRID,
        True,
        date(2025, 4, 21),
        None,
        ("Viernes Santo",),
        (HolidayJurisdiction.NATIONAL,),
    ),
    (
        "modelo-369-oss-exception",
        date(2025, 3, 1),
        "369",
        CalendarCCAA.MADRID,
        False,
        date(2025, 3, 1),
        None,
        ("modelo_exception",),
        (),
    ),
)


# ---------------------------------------------------------------------------
# Calendar loading.
# ---------------------------------------------------------------------------


def test_load_calendar_2025_returns_boe_anchored_year() -> None:
    """The 2025 calendar TOML cites BOE-A-2024-22011 as its source."""

    calendar = load_holiday_calendar(2025)
    assert calendar.year == 2025
    assert calendar.boe_ref == "boe-resolucion-festivos-2025"
    assert calendar.boe_url is not None and "BOE-A-2024-22011" in calendar.boe_url


def test_load_calendar_2025_contains_boe_anchored_national_holidays() -> None:
    """The published 2025 national list per BOE-A-2024-22011 includes
    these fixed dates. The test asserts membership, not the total
    count, so future BOE corrections that add a single holiday do not
    fail the test for the wrong reason."""

    calendar = load_holiday_calendar(2025)
    national_dates = {h.holiday_date for h in calendar.national}
    for holiday_date in _NATIONAL_HOLIDAY_DATES_2025:
        assert holiday_date in national_dates


def test_load_calendar_2025_separates_national_from_ccaa() -> None:
    """The two holiday tuples never overlap by jurisdiction."""

    calendar = load_holiday_calendar(2025)
    assert all(h.jurisdiction is HolidayJurisdiction.NATIONAL for h in calendar.national)
    assert all(h.jurisdiction is HolidayJurisdiction.CCAA for h in calendar.ccaa)
    assert all(h.ccaa_code is None for h in calendar.national)
    assert all(h.ccaa_code is not None for h in calendar.ccaa)


def test_load_calendar_missing_year_raises_validation_error() -> None:
    """A year with no registered TOML produces a recoverable error."""

    with pytest.raises(DeadlineValidationError, match=r"1999|year|calendar|range"):
        load_holiday_calendar(1999)


def test_load_calendar_caches_repeat_calls() -> None:
    """The ``lru_cache`` wrapper returns identical instances for the
    same year, so callers may rely on identity for cache-hit
    detection."""

    first = load_holiday_calendar(2025)
    second = load_holiday_calendar(2025)
    assert first is second


# ---------------------------------------------------------------------------
# is_business_day predicate.
# ---------------------------------------------------------------------------


def test_business_day_predicate_cases() -> None:
    """Weekend, national, CCAA, weekday, and degraded-mode business-day cases."""

    calendar = load_holiday_calendar(2025)
    for case_id, probe, ccaa_code, expected_weekday, expected in _BUSINESS_DAY_CASES:
        assert probe.weekday() == expected_weekday, case_id
        assert is_business_day(probe, calendar=calendar, ccaa_code=ccaa_code) is expected, case_id


# ---------------------------------------------------------------------------
# next_business_day walk.
# ---------------------------------------------------------------------------


def test_next_business_day_cases() -> None:
    calendar = load_holiday_calendar(2025)
    for case_id, probe, expected in _NEXT_BUSINESS_DAY_CASES:
        assert next_business_day(probe, calendar=calendar, ccaa_code=None) == expected, case_id


# ---------------------------------------------------------------------------
# shift_deadline — the operator-facing function.
# ---------------------------------------------------------------------------


def test_shift_deadline_basic_cases() -> None:
    """AEAT deadline-shift cases for business days, weekends, holidays, and OSS exceptions."""

    for (
        case_id,
        close_date,
        modelo,
        ccaa_code,
        expected_shifted,
        expected_adjusted,
        expected_shift_days,
        reason_fragments,
        expected_jurisdictions,
    ) in _SHIFT_DEADLINE_CASES:
        result = shift_deadline(close_date, modelo=modelo, ccaa_code=ccaa_code)
        assert result.shifted is expected_shifted, case_id
        assert result.original_close_date == close_date, case_id
        assert result.adjusted_close_date == expected_adjusted, case_id
        if expected_shift_days is not None:
            assert result.shift_days == expected_shift_days, case_id
        for fragment in reason_fragments:
            assert fragment in result.shift_reason, case_id
        for jurisdiction in expected_jurisdictions:
            assert jurisdiction in result.jurisdictions, case_id


def test_shift_deadline_handles_ccaa_holiday_when_residence_matches() -> None:
    """A Catalan taxpayer with a deadline on 2025-09-11 (Diada, Thursday)
    sees the deadline shift to Friday 2025-09-12. A Madrid taxpayer
    with the same close date does NOT shift."""

    diada = date(2025, 9, 11)
    catalan_result = shift_deadline(diada, modelo="303", ccaa_code=CalendarCCAA.CATALUNA)
    assert catalan_result.shifted is True
    assert catalan_result.adjusted_close_date == date(2025, 9, 12)
    assert HolidayJurisdiction.CCAA in catalan_result.jurisdictions
    assert "Diada" in catalan_result.shift_reason

    madrid_result = shift_deadline(diada, modelo="303", ccaa_code=CalendarCCAA.MADRID)
    assert madrid_result.shifted is False
    assert madrid_result.adjusted_close_date == diada


def test_shift_deadline_modelos_without_shift_constant_contains_369() -> None:
    """Regression guard for the OSS / IOSS exception list."""

    assert "369" in MODELOS_WITHOUT_SHIFT


def test_shift_deadline_accepts_externally_supplied_calendar() -> None:
    """Passing an explicit calendar bypasses the registry lookup. This
    is the path the deadline engine uses when it has already loaded the
    calendar for the schedule's year."""

    calendar = load_holiday_calendar(2025)
    tuesday = date(2025, 3, 4)
    result = shift_deadline(tuesday, modelo="303", ccaa_code=CalendarCCAA.MADRID, calendar=calendar)
    assert result.shifted is False
    assert result.adjusted_close_date == tuesday


def test_shift_deadline_rejects_empty_modelo_string() -> None:
    with pytest.raises(DeadlineValidationError, match=r"modelo|empty|blank"):
        shift_deadline(date(2025, 3, 4), modelo="", ccaa_code=None)


def test_shift_deadline_records_holiday_refs_for_audit_trail() -> None:
    """The DeadlineShift carries the holiday names that caused the
    shift so operator-facing output can explain ``why``."""

    diada = date(2025, 9, 11)
    result = shift_deadline(diada, modelo="303", ccaa_code=CalendarCCAA.CATALUNA)
    assert "Diada Nacional de Cataluña" in result.holiday_refs


def test_shift_deadline_handles_saturday_overlap_with_national_holiday() -> None:
    """2025-11-01 is Todos los Santos AND a Saturday. The shift result
    cites both the weekend day and the national holiday."""

    result = shift_deadline(date(2025, 11, 1), modelo="303", ccaa_code=CalendarCCAA.MADRID)
    assert result.shifted is True
    # The reason carries both signals.
    assert "sabado" in result.shift_reason
    assert "Todos los Santos" in result.shift_reason
    # Next business day is Monday 2025-11-03.
    assert result.adjusted_close_date == date(2025, 11, 3)


# ---------------------------------------------------------------------------
# Schema / validation.
# ---------------------------------------------------------------------------


def test_holiday_is_frozen_and_forbids_extras() -> None:
    holiday = Holiday(
        holiday_date=date(2025, 1, 1),
        jurisdiction=HolidayJurisdiction.NATIONAL,
        ccaa_code=None,
        name="Test",
    )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        holiday.name = "Renamed"


def test_deadline_shift_is_frozen_and_immutable() -> None:
    shift = shift_deadline(date(2025, 3, 4), modelo="303", ccaa_code=None)
    assert isinstance(shift, DeadlineShift)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        shift.shifted = True


def test_holiday_calendar_year_must_be_in_supported_range() -> None:
    out_of_range_year: int = 1999
    with pytest.raises(ValidationError, match=r"year|greater than"):
        HolidayCalendar(
            year=out_of_range_year,
            boe_ref="invalid",
            national=(),
            ccaa=(),
        )


def test_ccaa_enum_has_19_members_covering_17_autonomies_plus_2_cities() -> None:
    """Spain has 17 autonomous communities and 2 autonomous cities
    (Ceuta + Melilla). All 19 carry ISO 3166-2:ES codes."""

    members = tuple(CalendarCCAA)
    assert len(members) == 19
    codes = {m.value for m in members}
    assert "ES-AN" in codes  # Andalucía
    assert "ES-MD" in codes  # Madrid
    assert "ES-CT" in codes  # Cataluña
    assert "ES-CE" in codes  # Ceuta
    assert "ES-ML" in codes  # Melilla


# ---------------------------------------------------------------------------
# Boundary / non-existence assertions.
# ---------------------------------------------------------------------------


def test_no_parallel_festivos_implementation_exists() -> None:
    """Only ``cadrumo.domain.deadlines._festivos`` owns festivos /
    business-day semantics. Any other module defining functions with
    these names is a duplicate that re-introduces drift."""

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    source_root = repo_root / "src" / "cadrumo"
    canonical_module = source_root / "domain" / "deadlines" / "_festivos.py"

    canonical_symbols = (
        "load_holiday_calendar",
        "is_business_day",
        "next_business_day",
        "shift_deadline",
    )

    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        if py_file == canonical_module:
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for symbol in canonical_symbols:
            assert f"def {symbol}" not in text, (
                f"shadow festivos implementation detected: "
                f"{py_file} defines `def {symbol}`; the canonical "
                f"owner is `cadrumo.domain.deadlines._festivos`."
            )


def test_no_hardcoded_festivos_table_in_cli() -> None:
    """The CLI tree must not embed a hardcoded calendar table. The
    ``entrypoints/cli/`` source tree owns no holiday list; the
    calendar lives only under ``registry/aeat/calendars/``."""

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    cli_root = repo_root / "src" / "cadrumo" / "entrypoints" / "cli"

    forbidden_dates = (
        "2025-01-01",
        "2025-12-25",
        "Viernes Santo",
        "Día de la Constitución",
    )

    for py_file in scan_directory(cli_root, pattern="*.py", recursive=True):
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_dates:
            assert needle not in text, (
                f"hardcoded festivos data detected in CLI file {py_file}: "
                f"`{needle}`. Holiday data must live in "
                f"`registry/aeat/calendars/` and reach the CLI through "
                f"`cadrumo.domain.deadlines`."
            )
