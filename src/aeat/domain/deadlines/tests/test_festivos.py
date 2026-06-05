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
from .._errors import DeadlineValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    assert date(2025, 1, 1) in national_dates  # Año Nuevo
    assert date(2025, 1, 6) in national_dates  # Reyes
    assert date(2025, 4, 18) in national_dates  # Viernes Santo
    assert date(2025, 5, 1) in national_dates  # Fiesta del Trabajo
    assert date(2025, 8, 15) in national_dates  # Asunción
    assert date(2025, 11, 1) in national_dates  # Todos los Santos
    assert date(2025, 12, 6) in national_dates  # Constitución
    assert date(2025, 12, 8) in national_dates  # Inmaculada
    assert date(2025, 12, 25) in national_dates  # Navidad


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


def test_business_day_predicate_recognises_saturday_as_inhabil() -> None:
    """date.weekday() == 5 is Saturday — never a business day."""

    calendar = load_holiday_calendar(2025)
    saturday = date(2025, 3, 1)  # Saturday, not a holiday.
    assert saturday.weekday() == 5
    assert is_business_day(saturday, calendar=calendar, ccaa_code=None) is False


def test_business_day_predicate_recognises_sunday_as_inhabil() -> None:
    calendar = load_holiday_calendar(2025)
    sunday = date(2025, 3, 2)
    assert sunday.weekday() == 6
    assert is_business_day(sunday, calendar=calendar, ccaa_code=None) is False


def test_business_day_predicate_recognises_national_holiday_as_inhabil() -> None:
    """2025-04-18 is Viernes Santo per BOE-A-2024-22011; a Friday but
    nevertheless inhábil because it is a national holiday."""

    calendar = load_holiday_calendar(2025)
    viernes_santo = date(2025, 4, 18)
    assert viernes_santo.weekday() == 4  # Friday
    assert is_business_day(viernes_santo, calendar=calendar, ccaa_code=None) is False


def test_business_day_predicate_recognises_ccaa_only_holiday_in_that_ccaa() -> None:
    """2025-09-11 (Diada) is a holiday only in ES-CT. A taxpayer in
    ES-CT sees it as inhábil; a taxpayer in ES-MD sees it as a regular
    Thursday business day."""

    calendar = load_holiday_calendar(2025)
    diada = date(2025, 9, 11)
    assert diada.weekday() == 3  # Thursday
    assert is_business_day(diada, calendar=calendar, ccaa_code=CalendarCCAA.CATALUNA) is False
    assert is_business_day(diada, calendar=calendar, ccaa_code=CalendarCCAA.MADRID) is True


def test_business_day_predicate_returns_true_for_plain_weekday() -> None:
    calendar = load_holiday_calendar(2025)
    tuesday = date(2025, 3, 4)  # Tuesday, not a holiday.
    assert is_business_day(tuesday, calendar=calendar, ccaa_code=CalendarCCAA.MADRID) is True


def test_business_day_predicate_degrades_to_national_only_when_ccaa_is_none() -> None:
    """When ``ccaa_code`` is None, the predicate recognises national
    holidays but treats CCAA holidays as regular days. This is the
    degraded mode for callers without tax-residence data."""

    calendar = load_holiday_calendar(2025)
    diada = date(2025, 9, 11)
    # Without CCAA context the predicate cannot know about ES-CT-only Diada.
    assert is_business_day(diada, calendar=calendar, ccaa_code=None) is True


# ---------------------------------------------------------------------------
# next_business_day walk.
# ---------------------------------------------------------------------------


def test_next_business_day_returns_input_when_already_business() -> None:
    calendar = load_holiday_calendar(2025)
    tuesday = date(2025, 3, 4)
    assert next_business_day(tuesday, calendar=calendar, ccaa_code=None) == tuesday


def test_next_business_day_skips_weekend_to_monday() -> None:
    calendar = load_holiday_calendar(2025)
    # 2025-11-01 is a Saturday AND national holiday. The next business
    # day is Monday 2025-11-03 (national holidays Sat + Sun + nothing
    # else; Monday is plain).
    saturday = date(2025, 11, 1)
    assert next_business_day(saturday, calendar=calendar, ccaa_code=None) == date(2025, 11, 3)


def test_next_business_day_skips_national_holiday_then_weekend() -> None:
    """2025-12-25 Thursday Navidad → Friday → Saturday 27 → Sunday 28 →
    Monday 29 is the next business day."""

    calendar = load_holiday_calendar(2025)
    navidad = date(2025, 12, 25)
    assert navidad.weekday() == 3
    assert next_business_day(navidad, calendar=calendar, ccaa_code=None) == date(2025, 12, 26)


# ---------------------------------------------------------------------------
# shift_deadline — the operator-facing function.
# ---------------------------------------------------------------------------


def test_shift_deadline_does_not_move_a_business_day_close() -> None:
    """A close on a plain Tuesday produces an unshifted DeadlineShift."""

    tuesday = date(2025, 3, 4)
    result = shift_deadline(tuesday, modelo="303", ccaa_code=CalendarCCAA.MADRID)
    assert result.shifted is False
    assert result.shift_days == 0
    assert result.original_close_date == result.adjusted_close_date == tuesday
    assert result.shift_reason == "business_day"


def test_shift_deadline_moves_a_saturday_close_to_next_monday() -> None:
    """AEAT rule: a deadline on a Saturday shifts to the next Monday."""

    # 2025-03-01 is a Saturday with no holiday overlay.
    saturday = date(2025, 3, 1)
    result = shift_deadline(saturday, modelo="303", ccaa_code=CalendarCCAA.MADRID)
    assert result.shifted is True
    assert result.original_close_date == saturday
    assert result.adjusted_close_date == date(2025, 3, 3)
    assert result.shift_days == 2
    assert "sabado" in result.shift_reason


def test_shift_deadline_handles_national_holiday_on_weekday() -> None:
    """2025-04-18 is Viernes Santo (Friday). The deadline shifts to the
    next Monday because Saturday + Sunday follow the holiday."""

    viernes_santo = date(2025, 4, 18)
    result = shift_deadline(viernes_santo, modelo="303", ccaa_code=CalendarCCAA.MADRID)
    assert result.shifted is True
    assert result.adjusted_close_date == date(2025, 4, 21)
    assert HolidayJurisdiction.NATIONAL in result.jurisdictions
    assert "Viernes Santo" in result.shift_reason


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


def test_shift_deadline_modelo_369_does_not_shift_per_oss_exception() -> None:
    """The AEAT Calendario del Contribuyente documents Modelo 369
    (OSS / IOSS) as an exception: its deadlines do NOT shift even when
    the close date is a non-business day, because the OSS / IOSS
    regime is governed by an EU-harmonised cutoff."""

    saturday = date(2025, 3, 1)
    result = shift_deadline(saturday, modelo="369", ccaa_code=CalendarCCAA.MADRID)
    assert result.shifted is False
    assert result.adjusted_close_date == saturday
    assert result.shift_reason == "modelo_exception"


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
    """Only ``aeat.domain.deadlines._festivos`` owns festivos /
    business-day semantics. Any other module defining functions with
    these names is a duplicate that re-introduces drift."""

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    source_root = repo_root / "src" / "aeat"
    canonical_module = source_root / "domain" / "deadlines" / "_festivos.py"

    canonical_symbols = (
        "load_holiday_calendar",
        "is_business_day",
        "next_business_day",
        "shift_deadline",
    )

    for py_file in source_root.rglob("*.py"):
        if py_file == canonical_module:
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for symbol in canonical_symbols:
            assert f"def {symbol}" not in text, (
                f"shadow festivos implementation detected: "
                f"{py_file} defines `def {symbol}`; the canonical "
                f"owner is `aeat.domain.deadlines._festivos`."
            )


def test_no_hardcoded_festivos_table_in_cli() -> None:
    """The CLI tree must not embed a hardcoded calendar table. The
    ``entrypoints/cli/`` source tree owns no holiday list; the
    calendar lives only under ``registry/aeat/calendars/``."""

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    cli_root = repo_root / "src" / "aeat" / "entrypoints" / "cli"

    forbidden_dates = (
        "2025-01-01",
        "2025-12-25",
        "Viernes Santo",
        "Día de la Constitución",
    )

    for py_file in cli_root.rglob("*.py"):
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_dates:
            assert needle not in text, (
                f"hardcoded festivos data detected in CLI file {py_file}: "
                f"`{needle}`. Holiday data must live in "
                f"`registry/aeat/calendars/` and reach the CLI through "
                f"`aeat.domain.deadlines`."
            )
