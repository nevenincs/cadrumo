"""Real-behaviour tests for the festivos / business-day substrate.

Every test grounds its expected value in an external authority — either
the BOE-published Resolución de fiestas laborales for that year (cited
by the governed holiday facts and re-cited inline here), the AEAT Calendario del
Contribuyente shift rule, or a structural / wiring / error-path
property. No test computes the expected adjusted date by re-applying
the shift formula to a freshly-invented date.

The BOE-cited fixed dates used as anchors:

* 2025-04-18 = Viernes Santo (national, BOE-A-2024-26935).
* 2025-05-01 = Fiesta del Trabajo (Thursday; national).
* 2025-11-01 = Todos los Santos (Saturday; national + weekend).
* 2025-12-25 = Navidad (Thursday; national).
* 2025-09-11 = Diada Nacional de Cataluña (CCAA ES-CT only).
* 2025-02-28 = Día de Andalucía (CCAA ES-AN only).
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.calendar_ccaa_catalogue import (
    require_calendar_ccaa,
    resolve_calendar_ccaa_catalogue,
)

from ....core.directory_scan import scan_directory
from ..errors import DeadlineValidationError
from ..festivos import (
    MODELOS_WITHOUT_SHIFT,
    CalendarCCAA,
    DeadlineHolidayCoverage,
    DeadlineShift,
    Holiday,
    HolidayCalendar,
    HolidayJurisdiction,
    is_business_day,
    load_holiday_calendar,
    next_business_day,
    shift_deadline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _calendar_ccaa(operation: PinnedAuthorityOperation, code: str) -> CalendarCCAA:
    """Project a test territory through the pinned calendar-territory fact."""
    return require_calendar_ccaa(code, effective_date=date(2025, 7, 1), authority=operation)


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
    ("diada-cataluna", date(2025, 9, 11), "ES-CT", 3, False),
    ("diada-madrid", date(2025, 9, 11), "ES-MD", 3, True),
    ("plain-tuesday", date(2025, 3, 4), "ES-MD", 1, True),
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
        "ES-MD",
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
        "ES-MD",
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
        "ES-MD",
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
        "ES-MD",
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
    """The 2025 governed calendar facts cite the AGE días inhábiles resolution BOE-A-2024-26935."""
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        assert calendar.year == 2025
        assert calendar.boe_ref == "resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo"
        assert calendar.boe_url is not None and "BOE-A-2024-26935" in calendar.boe_url


def test_load_calendar_2025_contains_boe_anchored_national_holidays() -> None:
    """The published 2025 national list per BOE-A-2024-26935 includes
    these fixed dates. The test asserts membership, not the total
    count, so future BOE corrections that add a single holiday do not
    fail the test for the wrong reason."""
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        national_dates = {h.holiday_date for h in calendar.national}
        for holiday_date in _NATIONAL_HOLIDAY_DATES_2025:
            assert holiday_date in national_dates


def test_load_calendar_2025_separates_national_from_ccaa() -> None:
    """The two holiday tuples never overlap by jurisdiction."""
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        assert all(h.jurisdiction is HolidayJurisdiction.NATIONAL for h in calendar.national)
        assert all(h.jurisdiction is HolidayJurisdiction.CCAA for h in calendar.ccaa)
        assert all(h.ccaa_code is None for h in calendar.national)
        assert all(h.ccaa_code is not None for h in calendar.ccaa)


def test_load_calendar_missing_year_raises_validation_error() -> None:
    """A year with no governed publication produces a recoverable error."""
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(
            DeadlineValidationError,
            match=r"1999|year|calendar|range",
        ),
    ):
        load_holiday_calendar(1999, operation=operation)


def test_load_calendar_is_stable_across_repeat_calls() -> None:
    """Repeat loads through one pinned operation describe the same calendar."""
    with bundled_indexed_authority().operation() as operation:
        first = load_holiday_calendar(2025, operation=operation)
        second = load_holiday_calendar(2025, operation=operation)
        assert first == second


# ---------------------------------------------------------------------------
# is_business_day predicate.
# ---------------------------------------------------------------------------


def test_business_day_predicate_cases() -> None:
    """Weekend, national, CCAA, weekday, and degraded-mode business-day cases."""
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        for case_id, probe, ccaa_code, expected_weekday, expected in _BUSINESS_DAY_CASES:
            assert probe.weekday() == expected_weekday, case_id
            selected_ccaa = None if ccaa_code is None else _calendar_ccaa(operation, ccaa_code)
            assert is_business_day(probe, calendar=calendar, ccaa_code=selected_ccaa) is expected, case_id


# ---------------------------------------------------------------------------
# next_business_day walk.
# ---------------------------------------------------------------------------


def test_next_business_day_cases() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        for case_id, probe, expected in _NEXT_BUSINESS_DAY_CASES:
            assert next_business_day(probe, calendar=calendar, ccaa_code=None) == expected, case_id


# ---------------------------------------------------------------------------
# shift_deadline — the operator-facing function.
# ---------------------------------------------------------------------------


def test_shift_deadline_basic_cases() -> None:
    """AEAT deadline-shift cases for business days, weekends, holidays, and OSS exceptions."""

    with bundled_indexed_authority().operation() as operation:
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
            selected_ccaa = _calendar_ccaa(operation, ccaa_code)
            result = shift_deadline(
                close_date,
                modelo=modelo,
                ccaa_code=selected_ccaa,
                operation=operation,
            )
            assert result.shifted is expected_shifted, case_id
            assert result.original_close_date == close_date, case_id
            assert result.adjusted_close_date == expected_adjusted, case_id
            if expected_shift_days is not None:
                assert result.shift_days == expected_shift_days, case_id
            for fragment in reason_fragments:
                assert fragment in result.shift_reason, case_id
            for jurisdiction in expected_jurisdictions:
                assert jurisdiction in result.jurisdictions, case_id


def _diada_calendar(operation: PinnedAuthorityOperation, *, verified: bool) -> HolidayCalendar:
    """A synthetic 2025 calendar holding only the Diada, verified or not for Cataluna."""
    catalonia = _calendar_ccaa(operation, "ES-CT")
    return HolidayCalendar(
        year=2025,
        boe_ref="synthetic-2025",
        ccaa=(
            Holiday(
                holiday_date=date(2025, 9, 11),
                jurisdiction=HolidayJurisdiction.CCAA,
                ccaa_code=catalonia,
                name="Diada",
            ),
        ),
        verified_territories=(catalonia,) if verified else (),
    )


def test_shift_deadline_handles_ccaa_holiday_when_residence_matches() -> None:
    """A verified Catalan Diada (Thursday 2025-09-11) moves a Catalan
    deadline to Friday 2025-09-12; a Madrid taxpayer with the same close
    date does not shift."""

    with bundled_indexed_authority().operation() as operation:
        diada = date(2025, 9, 11)
        calendar = _diada_calendar(operation, verified=True)
        catalan_result = shift_deadline(
            diada,
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-CT"),
            calendar=calendar,
            operation=operation,
        )
        assert catalan_result.shifted is True
        assert catalan_result.adjusted_close_date == date(2025, 9, 12)
        assert HolidayJurisdiction.CCAA in catalan_result.jurisdictions
        assert "Diada" in catalan_result.shift_reason
        assert catalan_result.coverage is DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY

        madrid_result = shift_deadline(
            diada,
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-MD"),
            calendar=calendar,
            operation=operation,
        )
        assert madrid_result.shifted is False
        assert madrid_result.adjusted_close_date == diada
        assert madrid_result.coverage is DeadlineHolidayCoverage.TERRITORY_UNVERIFIED


def test_unverified_regional_holiday_never_extends_a_deadline() -> None:
    """A regional holiday the registry has not verified keeps the earlier date and says so."""
    with bundled_indexed_authority().operation() as operation:
        result = shift_deadline(
            date(2025, 9, 11),
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-CT"),
            calendar=_diada_calendar(operation, verified=False),
            operation=operation,
        )
    assert result.shifted is False
    assert result.adjusted_close_date == date(2025, 9, 11)
    assert result.coverage is DeadlineHolidayCoverage.TERRITORY_UNVERIFIED


def test_unknown_territory_checks_national_holidays_only() -> None:
    with bundled_indexed_authority().operation() as operation:
        result = shift_deadline(
            date(2025, 9, 11),
            modelo="303",
            ccaa_code=None,
            calendar=_diada_calendar(operation, verified=True),
            operation=operation,
        )
    assert result.shifted is False
    assert result.coverage is DeadlineHolidayCoverage.NATIONAL_ONLY


def test_modelo_369_is_never_shifted_and_says_so() -> None:
    """AEAT keeps Modelo 369's close date even on a weekend (2025-10-18 is a Saturday)."""
    with bundled_indexed_authority().operation() as operation:
        result = shift_deadline(
            date(2025, 10, 18),
            modelo="369",
            ccaa_code=_calendar_ccaa(operation, "ES-CT"),
            calendar=_diada_calendar(operation, verified=True),
            operation=operation,
        )
    assert result.adjusted_close_date == date(2025, 10, 18)
    assert result.coverage is DeadlineHolidayCoverage.NOT_SHIFTED


def test_shift_deadline_modelos_without_shift_constant_contains_369() -> None:
    """Regression guard for the OSS / IOSS exception list."""

    assert "369" in MODELOS_WITHOUT_SHIFT


def test_shift_deadline_accepts_externally_supplied_calendar() -> None:
    """Passing an explicit calendar bypasses the registry lookup. This
    is the path the deadline engine uses when it has already loaded the
    calendar for the schedule's year."""
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        tuesday = date(2025, 3, 4)
        result = shift_deadline(
            tuesday,
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-MD"),
            calendar=calendar,
            operation=operation,
        )
        assert result.shifted is False
        assert result.adjusted_close_date == tuesday


def test_shift_deadline_rejects_empty_modelo_string() -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(
            DeadlineValidationError,
            match=r"modelo|empty|blank",
        ),
    ):
        shift_deadline(date(2025, 3, 4), modelo="", ccaa_code=None, operation=operation)


def test_shift_deadline_records_holiday_refs_for_audit_trail() -> None:
    """The DeadlineShift carries the holiday names that caused the
    shift so operator-facing output can explain ``why``."""

    with bundled_indexed_authority().operation() as operation:
        diada = date(2025, 9, 11)
        result = shift_deadline(
            diada,
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-CT"),
            calendar=_diada_calendar(operation, verified=True),
            operation=operation,
        )
        assert "Diada" in result.holiday_refs


def test_shift_deadline_handles_saturday_overlap_with_national_holiday() -> None:
    """2025-11-01 is Todos los Santos AND a Saturday. The shift result
    cites both the weekend day and the national holiday."""

    with bundled_indexed_authority().operation() as operation:
        result = shift_deadline(
            date(2025, 11, 1),
            modelo="303",
            ccaa_code=_calendar_ccaa(operation, "ES-MD"),
            operation=operation,
        )
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
    with bundled_indexed_authority().operation() as operation:
        shift = shift_deadline(date(2025, 3, 4), modelo="303", ccaa_code=None, operation=operation)
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

    with bundled_indexed_authority().operation() as operation:
        members = resolve_calendar_ccaa_catalogue(effective_date=date(2025, 7, 1), authority=operation).choices
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
    """Only ``cadrumo.domain.deadlines.festivos`` owns festivos /
    business-day semantics. Any other module defining functions with
    these names is a duplicate that re-introduces drift."""

    from pathlib import Path

    # parents[5], not [4]: tests -> <area> -> domain -> cadrumo -> src -> repo.
    # [4] lands on `src/`, so `src/cadrumo` beneath it is `src/src/cadrumo`,
    # which does not exist -- and `scan_directory(require_root=False)` returns
    # empty rather than raising, so this gate swept 0 of 5,907 files and passed.
    repo_root = Path(__file__).resolve().parents[5]
    source_root = repo_root / "src" / "cadrumo"
    canonical_module = source_root / "domain" / "deadlines" / "festivos.py"

    canonical_symbols = (
        "load_holiday_calendar",
        "is_business_day",
        "next_business_day",
        "shift_deadline",
    )

    for py_file in scan_directory(source_root, pattern="*.py", recursive=True, require_root=True):
        if py_file == canonical_module:
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for symbol in canonical_symbols:
            assert f"def {symbol}" not in text, (
                f"shadow festivos implementation detected: "
                f"{py_file} defines `def {symbol}`; the canonical "
                f"owner is `cadrumo.domain.deadlines.festivos`."
            )


def test_no_hardcoded_festivos_table_in_cli() -> None:
    """The CLI tree must not embed a hardcoded calendar table. The
    ``entrypoints/cli/`` source tree owns no holiday list; the
    calendar is resolved only through governed holiday facts."""

    from pathlib import Path

    # parents[5], not [4]: tests -> <area> -> domain -> cadrumo -> src -> repo.
    # [4] lands on `src/`, so `src/cadrumo` beneath it is `src/src/cadrumo`,
    # which does not exist -- and `scan_directory(require_root=False)` returns
    # empty rather than raising, so this gate swept 0 of 5,907 files and passed.
    repo_root = Path(__file__).resolve().parents[5]
    cli_root = repo_root / "src" / "cadrumo" / "entrypoints" / "cli"

    forbidden_dates = (
        "2025-01-01",
        "2025-12-25",
        "Viernes Santo",
        "Día de la Constitución",
    )

    for py_file in scan_directory(cli_root, pattern="*.py", recursive=True, require_root=True):
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_dates:
            assert needle not in text, (
                f"hardcoded festivos data detected in CLI file {py_file}: "
                f"`{needle}`. Holiday data must live in governed facts and "
                f"reach the CLI through "
                f"`cadrumo.domain.deadlines`."
            )


def test_a_published_year_is_loaded_once_per_generation_pin() -> None:
    """One calendar view shifts many deadlines of a year against the same publication."""
    with bundled_indexed_authority().operation() as operation:
        first = load_holiday_calendar(2025, operation=operation)
        assert load_holiday_calendar(2025, operation=operation) is first
    with bundled_indexed_authority().operation() as later:
        assert load_holiday_calendar(2025, operation=later) == first


def test_a_refused_year_is_never_cached_as_a_calendar() -> None:
    with bundled_indexed_authority().operation() as operation:
        for _ in range(2):
            with pytest.raises(DeadlineValidationError):
                load_holiday_calendar(1999, operation=operation)
