"""An obligation is not overdue on a day its filer may still file.

A filing window's published close is the nominal date on the national basis. A
window whose close falls on a Saturday, Sunday or national inhábil runs to the
next business day (Ley 39/2015 art. 30.5, applied to tax procedure through Ley
58/2003 art. 7.2). Classifying the obligation against the nominal date called
the filer late on a day the plazo was still open, and the recargo it attached
counted from the wrong deadline.

Where the shift's own holiday calendar is not published, the effective close is
unknown. Such an obligation is ``UNKNOWN`` and carries no payment cutoff and no
recovery: nothing is judged after a date that is only a lower bound.

Both windows are found by scanning the supported filing years rather than named
here: the supported years are declared once in the year policy, and each
modelo's editions once in its own revisions.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.irpf_income_categories import require_irpf_income_category
from ...contribuyente.entity_type import require_entity_type
from ..engine import DeadlineEngine
from ..festivos import DeadlineHolidayCoverage
from ..models import IVARegime, ModeloDeadline, ObligationStatus, TaxpayerProfile
from .effective_close_scan import (
    ScannedObligation,
    obligation_with_a_shifted_close,
    obligations_with_an_unresolvable_shift,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@pytest.fixture(name="taxpayer")
def _taxpayer() -> TaxpayerProfile:
    """An autónomo with employees and rent, so the schedule covers several modelos."""
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "has_employees": True,
            "pays_rent_with_retencion": True,
        },
    )


@pytest.fixture(name="shifted")
def _shifted(taxpayer: TaxpayerProfile, operation: PinnedAuthorityOperation) -> ScannedObligation:
    return obligation_with_a_shifted_close(taxpayer, operation=operation)


def _recomputed(
    scanned: ScannedObligation,
    *,
    today: date,
    taxpayer: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> ModeloDeadline:
    """Recompute the scanned obligation's own row against another reference date."""
    schedule = DeadlineEngine(authority=operation).compute(taxpayer, scanned.filing_year, today=today)
    rows = [
        row
        for row in schedule.obligations
        if row.modelo == scanned.obligation.modelo and row.period == scanned.obligation.period
    ]
    assert len(rows) == 1, f"the engine lists {scanned.obligation.modelo} {scanned.obligation.period} once"
    return rows[0]


def test_the_obligation_publishes_both_closes(shifted: ScannedObligation) -> None:
    """``closes_on`` keeps its published meaning; the shifted date travels beside it."""
    row = shifted.obligation

    assert row.adjusted_closes_on > row.closes_on
    assert row.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert row.shift_reason not in {"business_day", "modelo_exception"}, "a shifted close names what moved it"


def test_the_shifted_close_day_is_due_today_not_overdue(
    shifted: ScannedObligation,
    taxpayer: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    """On the business day the filer still has, the obligation is due, not late."""
    row = _recomputed(shifted, today=shifted.effective_closes_on, taxpayer=taxpayer, operation=operation)

    assert row.status is ObligationStatus.DUE_TODAY
    assert row.recovery is None


def test_the_nominal_close_day_is_still_open(
    shifted: ScannedObligation,
    taxpayer: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    """The non-business nominal close is inside the window, not the last day."""
    row = _recomputed(shifted, today=shifted.nominal_closes_on, taxpayer=taxpayer, operation=operation)

    assert row.status is ObligationStatus.DUE_SOON


def test_the_day_after_the_shifted_close_is_overdue(
    shifted: ScannedObligation,
    taxpayer: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    """Lateness and its recargo band start the day after the effective close."""
    day_after = shifted.effective_closes_on + timedelta(days=1)
    row = _recomputed(shifted, today=day_after, taxpayer=taxpayer, operation=operation)

    assert row.status is ObligationStatus.OVERDUE
    assert row.recovery is not None, "the band is resolved from the effective close"


def test_every_supported_year_resolves_the_shift_calendar_of_each_dated_obligation(
    taxpayer: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> None:
    """Whichever year is filed, a dated obligation's effective close is known.

    The registry authors the holiday calendar of every year a supported filing
    year's windows reach, so no obligation is left with an unverified nominal
    close that would be judged differently from the same obligation in another
    year.
    """
    unresolved = obligations_with_an_unresolvable_shift(taxpayer, operation=operation)

    assert not unresolved, [
        (scanned.filing_year, scanned.obligation.modelo, scanned.obligation.period.registry_token)
        for scanned in unresolved
    ]
