"""Statutory-fact gate for the calculate-path Art. 27 LGT recargo advisory.

Cross-domain-continuity audit finding ``articulo-27-statute-fact-gate``: the
calculate path is handed only a work unit and a reference date, so it cannot
establish the three facts Art. 27 LGT needs to *determine* a recargo — an importe
a ingresar (Art. 27.2: the recargo is computed "sobre el importe a ingresar"),
the actual presentation date, and the absence of a prior AEAT requerimiento
(Art. 27.1: the regime applies only "sin requerimiento previo"). Absent those
facts the summary must present the surcharge percentage as a rate-only
CONDITIONAL advisory and must NOT claim recargo eligibility (fail closed); a prior
requerimiento or a filing with nothing to ingresar must attract no recargo at all.

External authority: Ley 58/2003 (LGT) Art. 27, post-Ley 11/2021. These tests
derive the overdue posture and the recargo band from the live registry deadline
window (``resolve_filing_closes_on``) and the separately-grounded domain
``build_recovery_for_overdue`` — never a hand-picked percentage — so the
load-bearing assertions are the conditional-vs-statutory distinction and the
fail-closed posture, not a manufactured Decimal.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.deadlines import build_recovery_for_overdue, resolve_filing_closes_on
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from .._work_plazo import modelo_work_plazo_summary

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "d" * 64
_REVISION_ID = "130-2019-y-siguientes"
_MODELO = "130"
_PERIOD_CODE = "1T"
_FILING_YEAR = 2026


def _work_unit(period: Period) -> WorkUnit:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
    )
    now = datetime(_FILING_YEAR, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
        name=f"{_MODELO}-{_FILING_YEAR}-{_PERIOD_CODE}",
        created_at=now,
        updated_at=now,
    )


def _overdue_context() -> tuple[WorkUnit, Period, date, date]:
    """Return (work_unit, period, closes_on, reference_today) for a late M130 1T."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    closes_on = resolve_filing_closes_on(_MODELO, _FILING_YEAR, period)
    assert closes_on is not None, "registry must carry an M130 1T 2026 deadline window"
    reference_today = closes_on + timedelta(days=40)
    return _work_unit(period), period, closes_on, reference_today


def test_facts_absent_yields_conditional_rate_only_advisory() -> None:
    """No statutory facts → a rate-only CONDITIONAL advisory, no eligibility claim.

    The default calculate path passes no amount payable, no actual presentation
    date, and no prior-requirement status. The overdue posture and a recargo band
    still surface (the operator learns the rate that would apply), but the band is
    marked ``conditional`` so nothing claims the recargo is due.
    """
    work_unit, _period, closes_on, reference_today = _overdue_context()

    summary = modelo_work_plazo_summary(work_unit, today=reference_today)

    assert summary is not None
    assert summary.closes_on == closes_on
    assert summary.days_overdue == (reference_today - closes_on).days
    assert summary.recargo is not None, "the conditional rate advisory must still surface the band"
    assert summary.recargo.conditional is True, "facts absent must not claim a statutory recargo"
    assert summary.recargo.legal_ref.startswith("ley-58-2003:art-27")


def test_facts_present_yields_statutory_recargo_computation() -> None:
    """All three statutory facts present → the recargo is a determined computation.

    An importe a ingresar, a committed presentation date, and no prior AEAT
    requerimiento establish the Art. 27 recargo. The band is marked non-conditional
    and its percentage matches the separately-grounded domain computation for the
    same presentation date (cross-checked, not hand-asserted).
    """
    work_unit, period, closes_on, reference_today = _overdue_context()

    summary = modelo_work_plazo_summary(
        work_unit,
        today=reference_today,
        amount_payable=Decimal("450.00"),
        presentation_date=reference_today,
        prior_requirement=False,
    )

    assert summary is not None
    assert summary.recargo is not None
    assert summary.recargo.conditional is False, "all statutory facts present must be a computation"

    expected = build_recovery_for_overdue(
        closes_on=closes_on,
        reference_today=reference_today,
        modelo=_MODELO,
        period=period,
    )
    assert summary.recargo.band_id == expected.recargo_band.id
    assert summary.recargo.surcharge_pct == expected.recargo_band.surcharge_pct
    assert summary.recargo.interest_applies is expected.recargo_band.interest_applies


def test_prior_requirement_fails_closed_with_no_recargo() -> None:
    """A prior AEAT requerimiento removes the Art. 27 recargo regime entirely.

    Art. 27.1: the recargo por declaración extemporánea applies only "sin
    requerimiento previo". With a prior requerimiento the overdue posture still
    surfaces, but no recargo may be claimed (fail closed).
    """
    work_unit, _period, closes_on, reference_today = _overdue_context()

    summary = modelo_work_plazo_summary(
        work_unit,
        today=reference_today,
        amount_payable=Decimal("450.00"),
        presentation_date=reference_today,
        prior_requirement=True,
    )

    assert summary is not None
    assert summary.days_overdue == (reference_today - closes_on).days
    assert summary.recargo is None, "a prior requerimiento must not attract an Art. 27 recargo"


def test_no_amount_payable_fails_closed_with_no_recargo() -> None:
    """A filing with nothing to ingresar (zero/refund/informational) has no recargo.

    Art. 27.2: the recargo is computed "sobre el importe a ingresar". A
    non-positive amount payable means there is no base for a recargo, so the
    overdue posture surfaces without any recargo claim (fail closed) — the
    informational/zero/refund work that the over-claiming advisory used to
    mislabel as recargo-eligible.
    """
    work_unit, _period, closes_on, reference_today = _overdue_context()

    summary = modelo_work_plazo_summary(
        work_unit,
        today=reference_today,
        amount_payable=Decimal("0.00"),
        presentation_date=reference_today,
        prior_requirement=False,
    )

    assert summary is not None
    assert summary.days_overdue == (reference_today - closes_on).days
    assert summary.recargo is None, "no importe a ingresar must not attract an Art. 27 recargo"


def test_in_time_filing_carries_no_recargo() -> None:
    """A filing inside the voluntary window carries days_remaining and no recargo."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    closes_on = resolve_filing_closes_on(_MODELO, _FILING_YEAR, period)
    assert closes_on is not None
    reference_today = closes_on - timedelta(days=5)

    summary = modelo_work_plazo_summary(_work_unit(period), today=reference_today)

    assert summary is not None
    assert summary.days_remaining == 5
    assert summary.days_overdue is None
    assert summary.recargo is None
