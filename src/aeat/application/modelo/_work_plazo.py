"""Application summaries for modelo work-unit filing deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.logging import get_logger
from ...domain.modelos._work_unit import WorkUnit

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ModeloWorkRecargoSummary:
    """Recargo band summary for an overdue modelo work unit."""

    band_id: str
    surcharge_pct: Decimal
    interest_applies: bool
    legal_ref: str


@dataclass(frozen=True, slots=True)
class ModeloWorkPlazoSummary:
    """Filing-deadline summary for a modelo work unit."""

    closes_on: date
    days_remaining: int | None = None
    days_overdue: int | None = None
    recargo: ModeloWorkRecargoSummary | None = None


def modelo_work_plazo_summary(
    work_unit: WorkUnit,
    *,
    today: date | None = None,
) -> ModeloWorkPlazoSummary | None:
    """Return a :class:`ModeloWorkPlazoSummary` with deadline and recargo information, or ``None`` when unknown."""
    from ...domain.deadlines._errors import DeadlineValidationError
    from ...domain.deadlines._plazo import resolve_filing_closes_on
    from ...domain.deadlines._recargo import build_recovery_for_overdue

    closes_on = resolve_filing_closes_on(
        str(work_unit.modelo),
        work_unit.filing_year,
        work_unit.period,
    )
    if closes_on is None:
        return None

    resolved_today = today or date.today()
    if resolved_today <= closes_on:
        return ModeloWorkPlazoSummary(closes_on=closes_on, days_remaining=(closes_on - resolved_today).days)

    days_overdue = (resolved_today - closes_on).days
    if days_overdue < 1:
        return ModeloWorkPlazoSummary(closes_on=closes_on)

    try:
        recovery = build_recovery_for_overdue(
            closes_on=closes_on,
            reference_today=resolved_today,
            modelo=str(work_unit.modelo),
            period=work_unit.period,
        )
    except DeadlineValidationError:
        _LOG.debug(
            "modelo work plazo recargo resolution failed; returning overdue summary without recargo "
            "modelo=%s filing_year=%s period=%s days_overdue=%s",
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period.registry_token,
            days_overdue,
            exc_info=True,
        )
        return ModeloWorkPlazoSummary(closes_on=closes_on, days_overdue=days_overdue)

    band = recovery.recargo_band
    return ModeloWorkPlazoSummary(
        closes_on=closes_on,
        days_overdue=days_overdue,
        recargo=ModeloWorkRecargoSummary(
            band_id=band.id,
            surcharge_pct=band.surcharge_pct,
            interest_applies=band.interest_applies,
            legal_ref=band.legal_ref,
        ),
    )


__all__ = [
    "ModeloWorkPlazoSummary",
    "ModeloWorkRecargoSummary",
    "modelo_work_plazo_summary",
]
