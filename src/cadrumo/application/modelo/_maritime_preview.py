"""Application service for active-profile maritime exemption previews.

This module backs the ``aeat app modelo work preview-maritime-exemption`` CLI
surface. It reads the active profile's ``maritime_worker.*`` facts, normalises
them into :class:`cadrumo.domain.renta.MaritimeWorkerFacts`, delegates legal
pathway selection and typed observation creation to
:func:`cadrumo.application.calculations.resolve_maritime_exemption`, and returns a
:class:`ModeloMaritimeExemptionPreview` for transport rendering.

The RETMAR mandatory-filing completeness gate is handled here rather than in
the CLI transport. When the legal resolver raises
:class:`cadrumo.domain.renta.ProfileCompletenessError`, the service preserves the
original profile facts and reruns the calculation with only
``retmar_registered`` cleared, allowing the CLI to emit both the warning and the
same observation payload shape used by non-warning previews.

See Also:
    :func:`cadrumo.entrypoints.cli._modelo_maritime_cli.register_maritime_commands`:
        Registers the CLI command that serialises this preview into operator
        payloads.
    :func:`cadrumo.application.calculations.resolve_maritime_exemption`:
        Legal application service that produces the typed observations.
    :class:`cadrumo.domain.renta.MaritimeWorkerFacts`:
        Closed profile fact carrier consumed by the maritime selectors.
    :class:`cadrumo.domain.renta.ProfileCompletenessError`:
        Warning-class gate used for RETMAR mandatory-filing disclosure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

from ...application.calculations._maritime_exemption_service import (
    resolve_maritime_exemption,
    retmar_mandatory_filing,
)
from ...application.user_profile.projections import fact_value
from ...core.parsing import parse_bool
from ...domain.renta._maritime_exemption import MaritimeWorkerFacts, ProfileCompletenessError
from ..calculations._maritime_exemption_service import MaritimeExemptionResult
from ..workflow.persistence import workflow_state_repository


@dataclass(frozen=True)
class ModeloMaritimeExemptionPreview:
    """Resolved active-profile maritime preview returned to the CLI renderer.

    Attributes:
        facts: Original :class:`~cadrumo.domain.renta.MaritimeWorkerFacts` read
            from the active profile. These facts are preserved even when RETMAR
            warning handling reruns the calculation with a cleared flag.
        result: :class:`~cadrumo.application.calculations._maritime_exemption_service.MaritimeExemptionResult`
            containing typed observations and the derived casilla-value view.
        retmar_warning_error: Optional
            :class:`~cadrumo.domain.renta.ProfileCompletenessError` for the CLI to
            translate into ``retmar_warning`` while still emitting observations.

    Read ``retmar_mandatory_filing`` from this preview, never from
    ``result``: on the warning path the result was computed from cleared facts
    and its copy of that answer is false regardless of the truth.
    """

    facts: MaritimeWorkerFacts
    result: MaritimeExemptionResult
    retmar_warning_error: ProfileCompletenessError | None = None

    @property
    def retmar_mandatory_filing(self) -> bool:
        """Whether RETMAR registration makes this filing mandatory.

        Read from :attr:`facts` rather than from :attr:`result`, and that is the
        whole point of the property. On the warning path ``result`` was computed
        from facts with the RETMAR flag deliberately cleared, so its own copy of
        this answer is false whether or not the worker is registered. Asking
        here, through the service's one determination, keeps the two paths
        agreeing and keeps the answer out of the renderer that was previously
        reconstructing it.
        """
        return retmar_mandatory_filing(self.facts)


def _vessel_flag(value: str | None) -> Literal["ES", "foreign"] | None:
    match value:
        case "ES":
            return "ES"
        case "foreign":
            return "foreign"
        case _:
            return None


def _waters_type(value: str | None) -> Literal["national", "international"] | None:
    match value:
        case "national":
            return "national"
        case "international":
            return "international"
        case _:
            return None


def _vessel_registry(
    value: str | None,
) -> Literal["REBECA", "rebeca_eu_eea", "scheduled_canary_route"] | None:
    match value:
        case "REBECA":
            return "REBECA"
        case "rebeca_eu_eea":
            return "rebeca_eu_eea"
        case "scheduled_canary_route":
            return "scheduled_canary_route"
        case _:
            return None


def maritime_facts_from_active_profile() -> MaritimeWorkerFacts:
    """Build :class:`MaritimeWorkerFacts` from the active workflow profile.

    The profile store exposes encrypted fact values as raw strings, so this
    adapter narrows the closed literal fields accepted by
    :class:`~cadrumo.domain.renta.MaritimeWorkerFacts` and converts absent or falsy
    boolean facts to ``False``. It does not evaluate legal eligibility; the
    returned facts are passed unchanged to the maritime exemption resolver.

    See Also:
        :func:`cadrumo.application.user_profile.fact_value`:
            Reads a stored profile fact by dotted path.
        :func:`cadrumo.application.workflow.workflow_state_repository`:
            Supplies the active profile record.
    """
    state = workflow_state_repository().load()
    record = state.active_profile_record()

    def _raw(path: str) -> str | None:
        raw = fact_value(record, path)
        return raw.strip() if raw else None

    def _bool(path: str) -> bool:
        return _bool_from_raw(fact_value(record, path))

    return MaritimeWorkerFacts(
        worker_class=_raw("maritime_worker.worker_class"),
        vessel_flag=_vessel_flag(_raw("maritime_worker.vessel_flag")),
        waters_type=_waters_type(_raw("maritime_worker.waters_type")),
        vessel_registry=_vessel_registry(_raw("maritime_worker.vessel_registry")),
        tuna_fleet=_bool("maritime_worker.tuna_fleet"),
        pending_eu_clearance=_bool("maritime_worker.pending_eu_clearance"),
        retmar_registered=_bool("maritime_worker.retmar_registered"),
    )


def _bool_from_raw(raw: str | None) -> bool:
    """Read a stored boolean fact, defaulting an absent or unreadable one to ``False``.

    Resolves through the one canonical vocabulary rather than a set spelled out
    here. The set spelled out here accepted ``true``, ``1`` and ``yes`` and
    nothing else, so a taxpayer answering ``si`` -- ordinary Spanish, and
    already accepted by the filing layer -- was recorded as having said no on a
    fact that gates an exemption pathway.

    ``False`` remains the fallback for a word the vocabulary cannot read,
    because these fields are optional and a partial profile must still resolve.
    That fallback is safe only because the write door refuses an unreadable
    value at entry, where the operator can still correct it; it is not a
    licence to interpret garbage.
    """
    return parse_bool(raw) is True


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
    resolver call records the :class:`~cadrumo.domain.renta.ProfileCompletenessError`,
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
        :func:`cadrumo.application.calculations.resolve_maritime_exemption`:
            Performs DA 41, RETMAR, Art. 7.p), and REBECA resolution.
        :class:`cadrumo.application.calculations._maritime_exemption_service.MaritimeExemptionResult`:
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
