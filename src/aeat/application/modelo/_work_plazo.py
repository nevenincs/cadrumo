"""Application summaries for modelo work-unit filing deadlines.

This module turns a :class:`WorkUnit` into the deadline summary used by the
calculate CLI payload. It asks the registry deadline-window surface for the
voluntary filing close date, derives either ``days_remaining`` or
``days_overdue`` against a reference date, and attaches the Ley 58/2003 art. 27
recargo band when the filing is late and the band table resolves.

An unknown registry deadline is deliberately represented as ``None`` rather
than a blocking error. A recargo lookup failure still returns the overdue
posture, logs the validation problem, and lets the rendering layer emit the
generic extemporaneous-filing warning.

See Also:
    :func:`aeat.domain.deadlines._plazo.resolve_filing_closes_on`:
        Registry-backed lookup for the plazo voluntario close date.
    :func:`aeat.domain.deadlines._recargo.build_recovery_for_overdue`:
        Resolves the Art. 27 LGT recargo band for overdue filing.
    :func:`aeat.entrypoints.cli._modelo_rendering.work_unit_deadline_output`:
        Projects this summary onto JSON payloads and warning notices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.logging import get_logger
from ...domain.modelos._work_unit import WorkUnit

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ModeloWorkRecargoSummary:
    """Recargo band summary for an overdue modelo work unit.

    The fields mirror the resolved deadline-domain recovery band: stable band
    id, surcharge percentage, interest applicability, and legal reference. The
    CLI renderer serialises this structure into the recargo block on the
    deadline payload.
    """

    band_id: str
    surcharge_pct: Decimal
    interest_applies: bool
    legal_ref: str


@dataclass(frozen=True, slots=True)
class ModeloWorkPlazoSummary:
    """Filing-deadline summary for a modelo work unit.

    ``closes_on`` is the voluntary filing close date. Exactly one posture should
    be populated by :func:`modelo_work_plazo_summary`: ``days_remaining`` for
    in-time filings, or ``days_overdue`` for late filings. ``recargo`` is present
    only when the overdue Art. 27 LGT band resolved successfully.
    """

    closes_on: date
    days_remaining: int | None = None
    days_overdue: int | None = None
    recargo: ModeloWorkRecargoSummary | None = None


def modelo_work_plazo_summary(
    work_unit: WorkUnit,
    *,
    today: date | None = None,
) -> ModeloWorkPlazoSummary | None:
    """Return deadline and recargo posture for a :class:`WorkUnit`, if known.

    The work unit supplies the modelo, filing year, and typed period used to
    match a registry deadline window. When no window matches, the function
    returns ``None`` so callers can omit the deadline block. When the filing is
    still inside the voluntary window, the summary carries ``days_remaining``.
    When the close date has passed, it carries ``days_overdue`` and, when
    available, a :class:`ModeloWorkRecargoSummary`.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo, filing year, and
            :class:`~aeat.core.Period` select a registry filing window.
        today: Optional reference date for deterministic tests; defaults to
            ``date.today()``.

    Returns:
        A :class:`ModeloWorkPlazoSummary`, or ``None`` when the registry has no
        deadline window for the work unit's filing axis.

    See Also:
        :func:`aeat.entrypoints.cli._modelo_rendering._work_unit_deadline_output_from_summary`:
            Converts the summary into operator-facing payloads and notices.
    """
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
