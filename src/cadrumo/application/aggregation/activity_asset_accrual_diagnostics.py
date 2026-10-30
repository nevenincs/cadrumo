"""Findings for unavailable and excluded activity-asset accruals."""

from __future__ import annotations

from datetime import date

from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.errors import RegistryError
from ...domain.renta.actividad_asset.errors import ActividadAssetError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ..actividad_asset.schedule_walk import M130ElementAccrual, M130ElementOutcome
from .source_mesh import CalculationSourceDiagnostic


def m130_accrual_diagnostics(
    accrual: M130ElementAccrual,
    *,
    period: Period,
    target_casilla_id: CasillaId,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Describe why a quarterly accrual is excluded, unavailable, or incomplete."""
    revision = accrual.revision
    if accrual.outcome is M130ElementOutcome.AGRARIAN_EXCLUDED:
        return (agrarian_excluded_diagnostic(revision, period=period, resolver_id=resolver_id),)
    if accrual.outcome is M130ElementOutcome.UNAVAILABLE and accrual.error is not None:
        return (accrual_unavailable_diagnostic(revision, accrual.error, casilla_id=None, resolver_id=resolver_id),)
    if accrual.outcome is not M130ElementOutcome.FREE_GAP:
        return ()
    start = max(date(period.filing_year, 1, 1), revision.in_service_date)
    return (
        CalculationSourceDiagnostic(
            reason="activity_asset_claim_gap",
            source_kind=resolver_id,
            resolver_id=resolver_id,
            source_ref=f"activity-asset:{revision.asset_id}",
            message=(
                f"element {revision.asset_id!r} has no effective claim for {start.isoformat()} to "
                f"{period.end_date.isoformat()} and no computable accrual, because the amount of a free method "
                f"is the taxpayer's election; it contributes nothing to box {target_casilla_id}"
            ),
            remedy="record the elected amortization charge to deduct it",
        ),
    )


def accrual_unavailable_diagnostic(
    revision: ActivityAssetRevision,
    error: ActividadAssetError | RegistryError,
    *,
    casilla_id: CasillaId | None,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    """Explain why an element's schedule could not be computed."""
    return CalculationSourceDiagnostic(
        reason="activity_asset_accrual_unavailable",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        casilla_id=casilla_id,
        message=f"the schedule of element {revision.asset_id!r} could not be worked out: {error}",
        remedy="complete or correct the element in the register, then calculate again",
    )


def agrarian_excluded_diagnostic(
    revision: ActivityAssetRevision,
    *,
    period: Period,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    """Explain why an agrarian element is excluded from the instalment."""
    return CalculationSourceDiagnostic(
        reason="activity_asset_agrarian_excluded",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        message=(
            f"element {revision.asset_id!r} belongs to an agrarian activity, whose {period.registry_token} instalment "
            "is a share of income (RIRPF art. 110.1.c); its amortization is deducted in Modelo 100 only"
        ),
    )


def activity_undeclared_diagnostic(
    revision: ActivityAssetRevision,
    *,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    """Report the assumed activity of an element with no declared activity."""
    return CalculationSourceDiagnostic(
        reason="activity_asset_activity_undeclared",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"transaction:{revision.acquisition.observed_transaction_id}",
        message=(
            f"the acquisition of element {revision.asset_id!r} declares no activity, and another element of this "
            "taxpayer is agrarian; it is counted as non-agrarian"
        ),
        remedy="set the type of activity on the acquisition entry, then calculate again",
    )
