"""Application service for active-profile maritime exemption previews.

This module backs the ``aeat app modelo work preview-maritime-exemption`` CLI
surface. It reads the active profile's ``maritime_worker.*`` facts, normalises
them into :class:`aeat.domain.renta.MaritimeWorkerFacts`, delegates legal
pathway selection and typed observation creation to
:func:`aeat.application.calculations.resolve_maritime_exemption`, and returns a
:class:`ModeloMaritimeExemptionPreview` for transport rendering.

The RETMAR mandatory-filing completeness gate is handled here rather than in
the CLI transport. When the legal resolver raises
:class:`aeat.domain.renta.ProfileCompletenessError`, the service preserves the
original profile facts and reruns the calculation with only
``retmar_registered`` cleared, allowing the CLI to emit both the warning and the
same observation payload shape used by non-warning previews.

See Also:
    :func:`aeat.entrypoints.cli._modelo_maritime_cli.register_maritime_commands`:
        Registers the CLI command that serialises this preview into operator
        payloads.
    :func:`aeat.application.calculations.resolve_maritime_exemption`:
        Legal application service that produces the typed observations.
    :class:`aeat.domain.renta.MaritimeWorkerFacts`:
        Closed profile fact carrier consumed by the maritime selectors.
    :class:`aeat.domain.renta.ProfileCompletenessError`:
        Warning-class gate used for RETMAR mandatory-filing disclosure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, cast

from ...application.calculations import resolve_maritime_exemption
from ...application.calculations._maritime_exemption_service import MaritimeExemptionResult
from ...application.user_profile import fact_value
from ...application.workflow import workflow_state_repository
from ...domain.renta import MaritimeWorkerFacts, ProfileCompletenessError


@dataclass(frozen=True)
class ModeloMaritimeExemptionPreview:
    """Resolved active-profile maritime preview returned to the CLI renderer.

    Attributes:
        facts: Original :class:`~aeat.domain.renta.MaritimeWorkerFacts` read
            from the active profile. These facts are preserved even when RETMAR
            warning handling reruns the calculation with a cleared flag.
        result: :class:`~aeat.application.calculations._maritime_exemption_service.MaritimeExemptionResult`
            containing typed observations and the derived casilla-value view.
        retmar_warning_error: Optional
            :class:`~aeat.domain.renta.ProfileCompletenessError` for the CLI to
            translate into ``retmar_warning`` while still emitting observations.
    """

    facts: MaritimeWorkerFacts
    result: MaritimeExemptionResult
    retmar_warning_error: ProfileCompletenessError | None = None


def maritime_facts_from_active_profile() -> MaritimeWorkerFacts:
    """Build :class:`MaritimeWorkerFacts` from the active workflow profile.

    The profile store exposes encrypted fact values as raw strings, so this
    adapter narrows the closed literal fields accepted by
    :class:`~aeat.domain.renta.MaritimeWorkerFacts` and converts absent or falsy
    boolean facts to ``False``. It does not evaluate legal eligibility; the
    returned facts are passed unchanged to the maritime exemption resolver.

    See Also:
        :func:`aeat.application.user_profile.fact_value`:
            Reads a stored profile fact by dotted path.
        :func:`aeat.application.workflow.workflow_state_repository`:
            Supplies the active profile record.
    """
    state = workflow_state_repository().load()
    record = state.active_profile_record()

    def _raw(path: str) -> str | None:
        raw = fact_value(record, path)
        return raw.strip() if raw else None

    def _bool(path: str) -> bool:
        raw = fact_value(record, path)
        if raw is None:
            return False
        return raw.strip().lower() in {"true", "1", "yes"}

    # fact_value() returns unvalidated str from encrypted profile storage.
    # Each Literal field on MaritimeWorkerFacts carries a closed value set;
    # membership tests below narrow the runtime value and cast bridges the
    # str→Literal narrowing that ty cannot express from a membership test.
    # This is a genuine profile-storage adapter boundary.
    _vf_raw = _raw("maritime_worker.vessel_flag")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    vessel_flag = cast(
        "Literal['ES', 'foreign'] | None",
        _vf_raw if _vf_raw in ("ES", "foreign") else None,
    )
    _wt_raw = _raw("maritime_worker.waters_type")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    waters_type = cast(
        "Literal['national', 'international'] | None",
        _wt_raw if _wt_raw in ("national", "international") else None,
    )
    _vr_raw = _raw("maritime_worker.vessel_registry")
    # CAST-RATIONALE-MARITIME-LITERAL-FIELD: str->Literal narrowing at profile-storage boundary.
    vessel_registry = cast(
        "Literal['REBECA', 'rebeca_eu_eea', 'scheduled_canary_route'] | None",
        _vr_raw if _vr_raw in ("REBECA", "rebeca_eu_eea", "scheduled_canary_route") else None,
    )
    return MaritimeWorkerFacts(
        worker_class=_raw("maritime_worker.worker_class"),
        vessel_flag=vessel_flag,
        waters_type=waters_type,
        vessel_registry=vessel_registry,
        tuna_fleet=_bool("maritime_worker.tuna_fleet"),
        pending_eu_clearance=_bool("maritime_worker.pending_eu_clearance"),
        retmar_registered=_bool("maritime_worker.retmar_registered"),
    )


def preview_maritime_exemption_for_active_profile(
    *,
    annual_salary: Decimal | None,
    qualifying_days: int | None,
    gross_navigation_income: Decimal | None,
) -> ModeloMaritimeExemptionPreview:
    """Resolve the active profile maritime exemption preview.

    ``annual_salary`` and ``qualifying_days`` are required only when the active
    facts trigger Art. 7.p) eligibility. ``gross_navigation_income`` is required
    only when the active facts trigger the REBECA pathway. The resolver owns
    those eligibility checks and raises the domain validation errors for missing
    inputs.

    RETMAR registration is a non-blocking warning for this preview: the first
    resolver call records the :class:`~aeat.domain.renta.ProfileCompletenessError`,
    then the calculation is rerun with ``retmar_registered=False`` so the
    operator still receives the observation payload. The returned
    :class:`ModeloMaritimeExemptionPreview` keeps the original facts, the rerun
    result, and the warning error for CLI translation.

    Args:
        annual_salary: Optional gross annual salary in EUR for Art. 7.p).
        qualifying_days: Optional days worked outside Spanish territory for
            Art. 7.p).
        gross_navigation_income: Optional gross navigation income in EUR for
            REBECA.

    Returns:
        :class:`ModeloMaritimeExemptionPreview` carrying original facts,
        resolved observations, and an optional RETMAR warning error.

    See Also:
        :func:`aeat.application.calculations.resolve_maritime_exemption`:
            Performs DA 41, RETMAR, Art. 7.p), and REBECA resolution.
        :class:`aeat.application.calculations._maritime_exemption_service.MaritimeExemptionResult`:
            Typed observation carrier stored on the preview.
    """
    facts = maritime_facts_from_active_profile()
    try:
        result = resolve_maritime_exemption(
            facts=facts,
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
        )
    except ProfileCompletenessError as exc:
        facts_without_retmar = replace(facts, retmar_registered=False)
        result = resolve_maritime_exemption(
            facts=facts_without_retmar,
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
        )
        return ModeloMaritimeExemptionPreview(
            facts=facts,
            result=result,
            retmar_warning_error=exc,
        )

    return ModeloMaritimeExemptionPreview(facts=facts, result=result)
