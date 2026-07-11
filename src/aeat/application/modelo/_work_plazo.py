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
from ...domain.modelos import WorkUnit

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ModeloWorkRecargoSummary:
    """Recargo band summary for an overdue modelo work unit.

    The fields mirror the resolved deadline-domain recovery band: stable band
    id, surcharge percentage, interest applicability, and legal reference. The
    CLI renderer serialises this structure into the recargo block on the
    deadline payload.

    ``conditional`` records whether this is a rate-only CONDITIONAL advisory or a
    statutory recargo COMPUTATION. The Art. 27 LGT recargo is only *determined*
    when there is an importe a ingresar, the actual presentation date is known,
    and there is no prior AEAT requirement. The calculate path normally holds none
    of those facts, so the band it surfaces is the surcharge percentage that
    *would* apply — a conditional advisory (``conditional=True``) — not an
    eligibility determination. It is set to ``False`` only when
    :func:`modelo_work_plazo_summary` is given all three statutory facts and they
    establish that a recargo is actually due.
    """

    band_id: str
    surcharge_pct: Decimal
    interest_applies: bool
    legal_ref: str
    conditional: bool = True


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
    amount_payable: Decimal | None = None,
    presentation_date: date | None = None,
    prior_requirement: bool | None = None,
) -> ModeloWorkPlazoSummary | None:
    """Return deadline and recargo posture for a :class:`WorkUnit`, if known.

    The work unit supplies the modelo, filing year, and typed period used to
    match a registry deadline window. When no window matches, the function
    returns ``None`` so callers can omit the deadline block. When the filing is
    still inside the voluntary window, the summary carries ``days_remaining``.
    When the close date has passed, it carries ``days_overdue`` and, when
    applicable, a :class:`ModeloWorkRecargoSummary`.

    Art. 27 LGT statutory-fact gate. The recargo por declaración extemporánea is
    only *determined* — a statutory computation — when three facts hold: there is
    an importe a ingresar (Art. 27.2: the recargo is computed "sobre el importe a
    ingresar"), the actual presentation date is known, and there is no prior AEAT
    requirement (Art. 27.1: the regime applies only "sin requerimiento previo").
    The calculate path is given only a work unit and a reference date, so it holds
    none of those facts. This function therefore FAILS CLOSED: absent the facts it
    surfaces the surcharge percentage that *would* apply as a rate-only
    CONDITIONAL advisory (``recargo.conditional=True``) and makes no eligibility
    claim; a supplied ``prior_requirement=True`` or a non-positive
    ``amount_payable`` yields the overdue posture with **no** recargo at all,
    because neither can attract an Art. 27 recargo. The recargo is marked a
    statutory computation (``conditional=False``) only when all three facts are
    present and establish that a recargo is due.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo, filing year, and
            :class:`~aeat.core.Period` select a registry filing window.
        today: Optional reference date for deterministic tests; defaults to
            ``date.today()``. Drives the ``days_remaining`` / ``days_overdue``
            posture.
        amount_payable: The importe a ingresar of the filing, when known. A
            ``None`` value means "unknown" (conditional); a value ``<= 0`` means
            there is nothing to ingresar, so no recargo is due.
        presentation_date: The actual date the self-assessment is presented, when
            committed. Drives the recargo band when supplied; ``None`` means the
            band is computed against ``today`` as a conditional estimate.
        prior_requirement: Whether a prior AEAT requerimiento exists. ``True``
            removes the Art. 27 sin-requerimiento recargo regime; ``None`` means
            unknown (conditional); ``False`` is one of the three facts required to
            treat the recargo as a statutory computation.

    Returns:
        A :class:`ModeloWorkPlazoSummary`, or ``None`` when the registry has no
        deadline window for the work unit's filing axis.

    See Also:
        :func:`aeat.entrypoints.cli._modelo_rendering._work_unit_deadline_output_from_summary`:
            Converts the summary into operator-facing payloads and notices.
    """
    from ...domain.deadlines import DeadlineValidationError, build_recovery_for_overdue, resolve_filing_closes_on

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

    # Fail-closed statutory gate. A prior requerimiento, or a filing with no
    # importe a ingresar (informational / zero / refund), cannot attract an
    # Art. 27 recargo: surface the overdue posture with no recargo claim.
    if prior_requirement is True or (amount_payable is not None and amount_payable <= 0):
        return ModeloWorkPlazoSummary(closes_on=closes_on, days_overdue=days_overdue)

    statutory_facts_established = (
        amount_payable is not None
        and amount_payable > 0
        and presentation_date is not None
        and prior_requirement is False
    )
    band_reference = presentation_date or resolved_today

    try:
        recovery = build_recovery_for_overdue(
            closes_on=closes_on,
            reference_today=band_reference,
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
            conditional=not statutory_facts_established,
        ),
    )


__all__ = [
    "ModeloWorkPlazoSummary",
    "ModeloWorkRecargoSummary",
    "modelo_work_plazo_summary",
]
