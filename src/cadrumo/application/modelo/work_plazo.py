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
    :func:`cadrumo.domain.deadlines.plazo.resolve_filing_closes_on`:
        Registry-backed lookup for the plazo voluntario close date.
    :func:`cadrumo.domain.deadlines.recargo.build_recovery_for_overdue`:
        Resolves the Art. 27 LGT recargo band for overdue filing.
    :func:`cadrumo.entrypoints.cli._modelo_rendering.work_unit_deadline_output`:
        Projects this summary onto JSON payloads and warning notices.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from ...core.logging import get_logger
from ...core.modelo import Modelo
from ...core.time.clock import today_madrid
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class M210PlazoResolution:
    """The resolved Modelo 210 filing window, carried as facts.

    Deliberately NOT a :class:`~core.json_contract.Notice`. A notice carries
    localized operator-facing prose, and rendering it here would put
    presentation inside the application layer; the frontends build the notice
    from these facts instead, so the same resolution can be spoken in any
    surface's own voice.

    Attributes:
        closes_on: ISO date the voluntary filing window closes.
        context: Deterministic diagnostic metadata, already in the shape a
            notice context takes -- window identity, legal and source refs.
    """

    closes_on: str
    context: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ModeloWorkConditionalRecargoPreview:
    """Unassessed Article 27 rate preview for an overdue work unit.

    This is a governed calendar-rate preview, not an Article 27 statutory
    assessment.  It preserves the deadline engine's band id, percentage,
    interest applicability, and legal reference so an operator can see the
    consequence that *may* apply at ``rate_reference_on``.  It does not carry
    an amount, eligibility decision, interest amount, or proof of the Article
    27 predicates.

    ``rate_reference_on`` is the explicit as-of date used for deadline posture
    and the conditional preview.  It is never represented as an actual filing
    presentation date.  ``assessment_status`` is intentionally a one-value
    contract: this calculate surface cannot assess Article 27 liability until a
    complete provenance-bearing assessment boundary exists.
    """

    band_id: str
    surcharge_pct: Decimal
    interest_applies: bool
    legal_ref: str
    rate_reference_on: date
    assessment_status: Literal["unassessed"] = "unassessed"


@dataclass(frozen=True, slots=True)
class ModeloWorkDeadlinePosture:
    """Voluntary-filing deadline posture for a modelo work unit.

    ``closes_on`` is the voluntary filing close date. Exactly one posture is
    populated by :func:`modelo_work_deadline_posture`: ``days_remaining`` for
    an in-time reference date, or ``days_overdue`` for an overdue reference
    date. ``conditional_recargo_preview`` is optional rate guidance only; it
    never represents a determined surcharge or interest liability.
    """

    closes_on: date
    days_remaining: int | None = None
    days_overdue: int | None = None
    conditional_recargo_preview: ModeloWorkConditionalRecargoPreview | None = None

    def __post_init__(self) -> None:
        """Reject a deadline summary that cannot describe one calendar posture."""
        validate_modelo_work_deadline_posture(
            closes_on=self.closes_on,
            days_remaining=self.days_remaining,
            days_overdue=self.days_overdue,
        )


def validate_modelo_work_deadline_posture(
    *,
    closes_on: date,
    days_remaining: int | None,
    days_overdue: int | None,
) -> None:
    """Enforce the canonical one-sided voluntary-deadline state contract."""
    if type(closes_on) is not date:
        raise ValueError("closes_on must be a date")

    day_counts = (days_remaining, days_overdue)
    if sum(value is not None for value in day_counts) != 1:
        raise ValueError("exactly one of days_remaining or days_overdue must be populated")

    for field_name, value in zip(("days_remaining", "days_overdue"), day_counts, strict=True):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{field_name} must be a non-negative integer when populated")


def modelo_work_deadline_posture(
    work_unit: WorkUnit,
    *,
    reference_on: date | None = None,
) -> ModeloWorkDeadlinePosture | None:
    """Return voluntary-deadline posture and rate-only preview, if known.

    The work unit supplies the modelo, filing year, and typed period used to
    match a registry deadline window. When no window matches, the function
    returns ``None`` so callers can omit the deadline block. When the filing is
    still inside the voluntary window, the posture carries ``days_remaining``.
    When the close date has passed, it carries ``days_overdue`` and, when the
    deadline engine resolves a band, a
    :class:`ModeloWorkConditionalRecargoPreview`.

    This function deliberately has no statutory-assessment inputs.  An Article
    27 determination needs provenance-bearing filing, amount, prior-requirement,
    identity, legal-regime, and additional statutory facts that the calculate
    path does not possess.  The returned preview is therefore always
    ``unassessed``.  The reference date drives an observable deadline posture
    and a conditional rate preview only; it is never an actual presentation
    date.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo, filing year, and
            :class:`~cadrumo.core.Period` select a registry filing window.
        reference_on: Optional date from which the caller observes the voluntary
            deadline. Defaults to the current Europe/Madrid civil date
            (:func:`cadrumo.core.time.today_madrid`) — the AEAT filing plazo is a
            Spanish-calendar boundary — which derives from the clock seam so a
            :func:`~cadrumo.core.time.frozen_clock` scope pins it. It drives the
            deadline posture and conditional preview rate; it is not a
            presentation date.

    Returns:
        A :class:`ModeloWorkDeadlinePosture`, or ``None`` when the registry has
        no deadline window for the work unit's filing axis.

    See Also:
        :func:`cadrumo.entrypoints.cli._modelo_rendering._work_unit_deadline_output_from_posture`:
            Converts the summary into operator-facing payloads and notices.
    """
    from ...domain.deadlines.errors import DeadlineValidationError
    from ...domain.deadlines.plazo import resolve_filing_closes_on
    from ...domain.deadlines.recargo import build_recovery_for_overdue

    closes_on = resolve_filing_closes_on(
        str(work_unit.modelo),
        work_unit.filing_year,
        work_unit.period,
    )
    if closes_on is None:
        return None

    resolved_reference_on = reference_on or today_madrid()
    if resolved_reference_on <= closes_on:
        return ModeloWorkDeadlinePosture(
            closes_on=closes_on,
            days_remaining=(closes_on - resolved_reference_on).days,
        )

    days_overdue = (resolved_reference_on - closes_on).days
    try:
        recovery = build_recovery_for_overdue(
            closes_on=closes_on,
            reference_today=resolved_reference_on,
            modelo=str(work_unit.modelo),
            period=work_unit.period,
        )
    except DeadlineValidationError:
        _LOG.debug(
            "modelo work deadline preview resolution failed; returning overdue posture without preview "
            "modelo=%s filing_year=%s period=%s days_overdue=%s",
            work_unit.modelo,
            work_unit.filing_year,
            work_unit.period.registry_token,
            days_overdue,
            exc_info=True,
        )
        return ModeloWorkDeadlinePosture(closes_on=closes_on, days_overdue=days_overdue)

    band = recovery.recargo_band
    return ModeloWorkDeadlinePosture(
        closes_on=closes_on,
        days_overdue=days_overdue,
        conditional_recargo_preview=ModeloWorkConditionalRecargoPreview(
            band_id=band.id,
            surcharge_pct=band.surcharge_pct,
            interest_applies=band.interest_applies,
            legal_ref=band.legal_ref,
            rate_reference_on=resolved_reference_on,
        ),
    )


def calculated_m210_plazo_resolution(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
) -> M210PlazoResolution | None:
    """Return the grounded post-calculation Modelo 210 plazo facts, if known.

    Modelo 210 annual filing windows depend on the calculated declaration
    result and the operator's persisted official two-digit tipo-renta code.
    Those facts do not exist at work-unit creation time, so this projection is
    deliberately separate from :func:`modelo_work_deadline_posture`, which
    remains the unqualified pre-calculation extemporaneidad surface.

    The function derives the result through the same application resolver used
    by filing/export and delegates window matching to the canonical deadline
    resolver.  It owns no result vocabulary, tipo-renta map, date catalogue, or
    matching rule.  A missing window produces no notice; notably, tipo 28 stays
    silent until its event-relative offset has authoritative registry backing.
    """
    if work_unit.modelo != Modelo.M210:
        return None

    from ...domain.deadlines.plazo import resolve_filing_window
    from .result_disposition_resolution import resolve_modelo_result_disposition

    resultado = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=work_unit.period,
    )
    tipo_renta_code = revision.m210_official_tipo_renta_code
    window = resolve_filing_window(
        str(work_unit.modelo),
        work_unit.filing_year,
        work_unit.period,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
    )
    if window is None:
        return None

    context = {
        "modelo": str(work_unit.modelo),
        "filing_year": str(work_unit.filing_year),
        "period": work_unit.period.registry_token,
        "resultado": resultado.value,
        "deadline_window_id": window.id,
        "opens_on": window.opens_on.isoformat(),
        "closes_on": window.closes_on.isoformat(),
        "legal_refs": ", ".join(window.legal_refs),
        "source_refs": ", ".join(window.source_refs),
    }
    if tipo_renta_code is not None:
        context["tipo_renta_code"] = tipo_renta_code
    if window.payment_cutoff_on is not None:
        context["payment_cutoff_on"] = window.payment_cutoff_on.isoformat()

    return M210PlazoResolution(closes_on=window.closes_on.isoformat(), context=context)


__all__ = [
    "M210PlazoResolution",
    "ModeloWorkConditionalRecargoPreview",
    "ModeloWorkDeadlinePosture",
    "calculated_m210_plazo_resolution",
    "modelo_work_deadline_posture",
    "validate_modelo_work_deadline_posture",
]
