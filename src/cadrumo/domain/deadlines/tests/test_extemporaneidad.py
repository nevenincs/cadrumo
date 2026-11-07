"""Tests for extemporaneidad detection and Art. 27.2 LGT recargo computation.

External authority: Ley 58/2003 (LGT) Art. 27.2, post-Ley 11/2021
amendment.  Surcharge escalation:

  - 1% plus a further 1% per COMPLETED month of delay, with no intereses de
    demora for the first 12 months. A fractional (incomplete) month does NOT
    count ("por cada mes completo de retraso").
  - Once 12 completed months elapse: 15% plus intereses de demora.

The tests drive the domain functions with calendar dates and assert against
the Ley 58/2003 statutory text, not against a day-bracket approximation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.errors import RegistrySnapshotError
from ...calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_supported_filing_years,
)
from ..festivos import DeadlineHolidayCoverage
from ..filing_window_projection import AuthoredFilingWindow, ProjectedFilingWindow
from ..plazo import resolve_filing_window
from ..recargo import (
    build_recovery_for_overdue,
    completed_months_late,
    load_recargo_bands,
    resolve_recargo_band,
)
from .withdrawn_deadline_window_authority import withdrawn_deadline_window_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Art. 27.2 LGT — completed-month surcharge schedule
# ---------------------------------------------------------------------------


def test_after_12_months_overdue_yields_15_pct_plus_interest(operation: PinnedAuthorityOperation) -> None:
    """Plazo closed 2024-11-30; presented 2026-05-27 → 17 completed months.

    External authority: Ley 58/2003 Art. 27.2 (post-Ley 11/2021). Once 12
    completed months have elapsed the recargo is 15% plus intereses de demora.
    The completed-month count is derived from the two calendar dates.
    """
    plazo_closes_on = date(2024, 11, 30)
    reference_today = date(2026, 5, 27)
    months = completed_months_late(plazo_closes_on, reference_today)
    # Nov 30 2024 → May 27 2026: 17 completed months (the May-30 anniversary is
    # not yet reached on May 27), well beyond the 12-month interest threshold.
    assert months == 17

    bands = load_recargo_bands(operation=operation)
    band = resolve_recargo_band(months, bands)

    assert band.id == "after_12_months"
    assert band.surcharge_pct == Decimal("15.00")
    assert band.interest_applies is True
    assert "ley-58-2003" in band.legal_ref


def test_after_12_months_recovery_payload(operation: PinnedAuthorityOperation) -> None:
    """build_recovery_for_overdue past 12 completed months → 15% + interest."""
    recovery = build_recovery_for_overdue(
        closes_on=date(2024, 11, 30),
        reference_today=date(2026, 5, 27),
        modelo="303",
        period=Period.from_year_and_code(2024, "4T"),
        operation=operation,
    )
    assert recovery is not None
    assert recovery.still_filable is True
    assert recovery.recargo_band.id == "after_12_months"
    assert recovery.recargo_band.interest_applies is True
    assert recovery.recargo_band.surcharge_pct == Decimal("15.00")
    assert "next_command" not in type(recovery).model_fields


def test_zero_completed_months_no_interest(operation: PinnedAuthorityOperation) -> None:
    """Filed late but within the first incomplete month → 1% recargo, no interest.

    External authority: Ley 58/2003 Art. 27.2 post-Ley 11/2021 — the 1% base
    applies before any month is completed.
    """
    bands = load_recargo_bands(operation=operation)
    band = resolve_recargo_band(0, bands)
    assert band.surcharge_pct == Decimal("1.00")
    assert band.interest_applies is False


def test_four_completed_months_no_interest(operation: PinnedAuthorityOperation) -> None:
    """4 completed months → 1% base + 4% = 5% recargo, no interest (Art. 27.2)."""
    bands = load_recargo_bands(operation=operation)
    band = resolve_recargo_band(4, bands)
    assert band.surcharge_pct == Decimal("5.00")
    assert band.interest_applies is False


def test_ten_completed_months_no_interest(operation: PinnedAuthorityOperation) -> None:
    """10 completed months → 1% base + 10% = 11% recargo, no interest (Art. 27.2)."""
    bands = load_recargo_bands(operation=operation)
    band = resolve_recargo_band(10, bands)
    assert band.surcharge_pct == Decimal("11.00")
    assert band.interest_applies is False


# ---------------------------------------------------------------------------
# resolve_filing_window — registry integration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("year", PublishedGovernedFactSource().supported_filing_years().years)
def test_resolve_filing_window_returns_the_m130_first_quarter_date(year: int) -> None:
    """M130 Q1 closes_on is registered and resolvable for every supported year.

    M130 (pagos fraccionados IRPF estimación directa) has deadline
    windows registered in the canonical TOML.  The resolver
    must return a non-None date for the Q1 window.
    """
    resolution = resolve_filing_window("130", year, Period.from_year_and_code(year, "1T"))
    window = None if resolution is None else resolution.dated_window
    assert window is not None
    closes_on = window.closes_on
    assert isinstance(closes_on, date)
    # M130 Q1 typically closes on 20 April (AEAT plazo trimestral).
    assert closes_on.year == year
    assert closes_on.month in (4, 5)  # April/May for Q1 plazo


def test_resolve_filing_window_refuses_an_unknown_modelo() -> None:
    """An id that is not a modelo REFUSES; it is not "deadline data unavailable".

    ``None`` is reserved for the two causes the contract names -- no window for
    the year, or a non-matching period token -- and callers continue without a
    close date on it. An absent modelo is a different class of fact, and
    production only reaches here through the ``Modelo`` enum, so the id can only
    come from a caller bug or unvalidated input. Degrading gracefully would give
    that caller no deadline, and the extemporaneidad computed from it would drop
    the recargo silently.
    """
    with pytest.raises(RegistrySnapshotError, match=r"modelo '999' is not present in the calculation registry"):
        resolve_filing_window("999", 2026, Period.from_year_and_code(2026, "1T"))


def test_resolve_filing_window_wrong_period_returns_none() -> None:
    """A period not registered for this modelo+year returns None."""
    result = resolve_filing_window("130", 2026, Period.from_year_and_code(2026, "1P"))
    assert result is None


def test_resolve_filing_window_annual_period() -> None:
    """M100 annual period '0A' resolves to a date in the correct year."""
    resolution = resolve_filing_window("100", 2024, Period.from_year_and_code(2024, "0A"))
    window = None if resolution is None else resolution.dated_window
    assert window is not None
    closes_on = window.closes_on
    assert closes_on is not None
    # M100 2024 anual plazo: AEAT opens April, closes June 30 2025.
    assert closes_on.year == 2025
    assert closes_on.month == 6


@pytest.mark.parametrize(
    ("modelo", "filing_year"),
    (("180", 2023),),
)
def test_resolve_filing_window_annual_period_does_not_borrow_a_future_window(
    modelo: str,
    filing_year: int,
) -> None:
    """An unauthored annual tax year must not resolve its successor's deadline.

    The year is made unauthored by withdrawing its windows from the published
    generation, so the case does not wait on a real gap that authoring closes.
    Its successor keeps its own window, and that is the window a borrowing
    lookup would hand back.
    """
    period = Period.from_year_and_code(filing_year, "0A")
    successor = Period.from_year_and_code(filing_year + 1, "0A")
    with withdrawn_deadline_window_operation(modelo_id=modelo, filing_year=filing_year) as withdrawn:
        assert resolve_filing_window(modelo, filing_year + 1, successor, authority=withdrawn) is not None, (
            "the successor declares no window, so there is nothing to borrow and this proves nothing"
        )
        assert resolve_filing_window(modelo, filing_year, period, authority=withdrawn) is None


def test_resolve_filing_window_below_the_supported_floor_answers_its_own_year_only() -> None:
    """A tax year below the floor answers the window authored for it or ``None``, never a later window.

    The answer is a value at any distance from the floor: the envelope decides
    what can be filed, not what the law dated, so no envelope refusal escapes.
    """
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    for filing_year in (supported_years.floor - 1, FOUR_DIGIT_YEAR_FIRST):
        answer = resolve_filing_window("100", filing_year, Period.from_year_and_code(filing_year, "0A"))
        assert answer is None or isinstance(answer, AuthoredFilingWindow)
        assert answer is None or answer.window.filing_year == filing_year


# ---------------------------------------------------------------------------
# Modelo 210 IRNR presentation windows (Orden EHA/3316/2010 art 5). Since the
# per-devengo regime the registry keys fixed annual plazos on canonical 0A and
# scopes each one by resultado and tipo de renta; no quarter token exists.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quarter", ("1T", "2T", "3T", "4T"))
def test_resolve_filing_window_m210_declares_no_quarter_window(quarter: str) -> None:
    """M210 quarter tokens have no window: none is fabricated from the old trimestral plazo."""
    assert resolve_filing_window("210", 2025, Period.from_year_and_code(2025, quarter)) is None


def test_resolve_filing_window_m210_arrendamiento_a_ingresar_closes_on_20_january() -> None:
    """Arrendamiento a ingresar for 2025 devengos closes 2026-01-20.

    Orden EHA/3316/2010 art 5.c).1 as worded by Orden HAC/56/2024, which applies from
    2024 devengos. The April window of Orden HAC/623/2026 applies only from 2026 devengos.
    """
    resolution = resolve_filing_window(
        "210",
        2025,
        Period.from_year_and_code(2025, "0A"),
        resultado=ResultDisposition.INGRESO,
        tipo_renta_code="01",
    )
    window = None if resolution is None else resolution.dated_window
    assert window is not None
    assert (window.opens_on, window.closes_on) == (date(2026, 1, 1), date(2026, 1, 20))


def test_resolve_filing_window_m210_annual_0a_without_resultado_returns_none() -> None:
    """M210 annual '0A' plazos depend on resultado and tipo de renta.

    Without that context no single window applies, so the unqualified resolver
    returns None rather than silently picking one of the scoped windows.
    """
    result = resolve_filing_window("210", 2025, Period.from_year_and_code(2025, "0A"))
    assert result is None


def test_resolve_filing_window_far_beyond_the_horizon_is_a_typed_projection() -> None:
    """A year far ahead is not refused for being far ahead; it is a dated projection whose close is unknown."""
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    far_ahead = supported_years.horizon + (FOUR_DIGIT_YEAR_LAST - supported_years.horizon) // 2
    answer = resolve_filing_window("303", far_ahead, Period.from_year_and_code(far_ahead, "1T"))
    assert isinstance(answer, ProjectedFilingWindow)
    assert answer.period.filing_year == far_ahead
    assert answer.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert answer.closes_on == answer.nominal_closes_on


def test_resolve_filing_window_on_the_last_writable_year_is_an_answer_not_a_crash() -> None:
    period = Period.from_year_and_code(FOUR_DIGIT_YEAR_LAST, "4T")
    assert resolve_filing_window("303", FOUR_DIGIT_YEAR_LAST, period) is None
