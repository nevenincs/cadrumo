"""Regression: the unassessed Article 27 preview fires for late M303 quarters.

The Art. 27 LGT extemporaneidad recargo warning covers the R9 (quarterly
IVA / Modelo 303) deadline cluster. The deadline-generic advisory
(:func:`cadrumo.application.modelo.modelo_work_deadline_posture` +
:func:`cadrumo.domain.deadlines.recargo.build_recovery_for_overdue`), and the
Modelo 303 registry carries quarterly deadline windows (``1T``/``2T``/``3T``/
``4T``) exactly like Modelo 130. Because the summary resolves its close date
through the generic :func:`resolve_filing_closes_on`, no M303-specific wiring is
needed: a late M303 quarter already surfaces the unassessed rate preview.

This test proves that invariant so the R9 cluster cannot silently regress. It is
the M303-quarterly companion to
``cadrumo.domain.deadlines.tests.test_extemporaneidad`` (which covers the M130
quarterly resolver and the BOE-grounded recargo band schedule) and to
``cadrumo.entrypoints.cli.tests.test_modelo_calculate_recargo_notice`` (which drives
the CLI Notice for M130).

Real-behaviour, non-tautology: the close date is read from the live registry
authority via :func:`resolve_filing_closes_on`; the reference dates are derived
*relative to that resolved close date* (never a frozen calendar literal), so the
test tracks the registry rather than a hardcoded plazo. The recargo band is not
hand-asserted — it is compared against the domain
:func:`build_recovery_for_overdue` result for the same ``(closes_on,
reference_today)`` pair, whose statutory grounding is proven separately. The
load-bearing assertions are wiring/posture invariants: a late M303 quarter
carries an overdue posture plus the Art. 27 LGT preview, and an in-time
M303 quarter carries neither.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines.plazo import resolve_filing_closes_on
from ....domain.deadlines.recargo import build_recovery_for_overdue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .._work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "c" * 64

# The Modelo 303 registry carries quarterly windows for these filing years; each
# is a distinct member of the R9 quarterly-IVA deadline cluster.
_QUARTERS = ("1T", "2T", "3T", "4T")
_FILING_YEARS = (2025, 2026)


def _quarter_year_cases():
    for quarter in _QUARTERS:
        for filing_year in _FILING_YEARS:
            yield quarter, filing_year


def _work_unit_for(quarter: str, filing_year: int) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, quarter)
    revision_id = bundled_authority().snapshot("303", filing_year=filing_year, period=period.registry_token).revision.id
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    now = datetime(filing_year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"303-{filing_year}-{quarter}",
        created_at=now,
        updated_at=now,
    )


def test_late_m303_quarter_surfaces_unassessed_rate_preview() -> None:
    """A past M303 deadline carries an unassessed Art. 27 rate preview.

    The reference date is derived as ``closes_on + 40 days`` — unambiguously
    extemporáneo, past the first completed month — from the registry-resolved
    close date, so the assertion tracks the registry deadline rather than a
    frozen literal. The recargo band is cross-checked against the domain
    ``build_recovery_for_overdue`` computation, not a hand-picked percentage.
    """
    for quarter, filing_year in _quarter_year_cases():
        case_id = f"M303 {filing_year} {quarter}"
        period = Period.from_year_and_code(filing_year, quarter)
        closes_on = resolve_filing_closes_on("303", filing_year, period)
        assert closes_on is not None, f"registry must carry an {case_id} window"

        reference_today = closes_on + timedelta(days=40)
        work_unit = _work_unit_for(quarter, filing_year)

        summary = modelo_work_deadline_posture(work_unit, reference_on=reference_today)

        assert summary is not None, case_id
        assert summary.closes_on == closes_on, case_id
        assert summary.days_remaining is None, case_id
        assert summary.days_overdue == (reference_today - closes_on).days, case_id
        assert summary.days_overdue == 40, case_id

        preview = summary.conditional_recargo_preview
        assert preview is not None, case_id
        assert preview.assessment_status == "unassessed", case_id
        assert preview.rate_reference_on == reference_today, case_id
        assert preview.legal_ref.startswith("ley-58-2003:art-27"), case_id

        expected = build_recovery_for_overdue(
            closes_on=closes_on,
            reference_today=reference_today,
            modelo="303",
            period=period,
        )
        assert preview.band_id == expected.recargo_band.id, case_id
        assert preview.surcharge_pct == expected.recargo_band.surcharge_pct, case_id
        assert preview.interest_applies is expected.recargo_band.interest_applies, case_id


def test_in_time_m303_quarter_is_silent() -> None:
    """An open M303 window carries no Article 27 preview.

    The reference date is derived as ``closes_on - 5 days`` from the
    registry-resolved close date, so the in-time branch is exercised without a
    hardcoded calendar. The summary must carry ``days_remaining`` and no
    recargo — the advisory stays silent when the filing is not extemporáneo.
    """
    for quarter, filing_year in _quarter_year_cases():
        case_id = f"M303 {filing_year} {quarter}"
        period = Period.from_year_and_code(filing_year, quarter)
        closes_on = resolve_filing_closes_on("303", filing_year, period)
        assert closes_on is not None, case_id

        reference_today = closes_on - timedelta(days=5)
        work_unit = _work_unit_for(quarter, filing_year)

        summary = modelo_work_deadline_posture(work_unit, reference_on=reference_today)

        assert summary is not None, case_id
        assert summary.closes_on == closes_on, case_id
        assert summary.days_overdue is None, case_id
        assert summary.days_remaining == 5, case_id
        assert summary.conditional_recargo_preview is None, case_id


def test_m303_quarterly_resolver_returns_dates_for_full_cluster() -> None:
    """Every registered M303 quarter in the cluster resolves a close date.

    This is the resolver-level guard: the deadline-generic advisory can only
    fire for M303 quarters if :func:`resolve_filing_closes_on` returns a date
    for each ``(303, filing_year, NT)`` axis. A registry drift that dropped an
    M303 quarterly window would silence the recargo advisory for that
    quarter; this test fails loudly if that happens.
    """
    for filing_year in _FILING_YEARS:
        for quarter in _QUARTERS:
            period = Period.from_year_and_code(filing_year, quarter)
            closes_on = resolve_filing_closes_on("303", filing_year, period)
            assert closes_on is not None, f"M303 {filing_year} {quarter} window missing"
            assert isinstance(closes_on, date)
