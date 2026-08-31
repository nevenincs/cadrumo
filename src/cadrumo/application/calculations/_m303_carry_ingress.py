"""Canonical Modelo 303 carry ingress for authoritative filing evidence.

The declaration's ``Tipo de declaración`` is evidence in the submitted-file
header, not a registry casilla.  This module is the only place that turns that
evidence (or the local filing boundary's already-resolved equivalent) into the
typed envelope disposition used to normalize the carry pair.  It intentionally
does not make any annual, history, or wallet decision: those later consumers
must read this persisted contract rather than recover an election themselves.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CoreValidationError, TerminalPreconditionErrorMixin
from ...core.modelo import Modelo
from ...core.resources.bundled_data import bundled_path
from ...core.result_disposition import ResultDisposition, result_disposition_is_refund
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.temporal import select_revision
from ...domain.iva_compensation.filed_derivation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    M303CompensationAvailableDerivation,
    derive_m303_compensation_available_from_casillas,
)

if TYPE_CHECKING:
    from ..operator_actions.models import PreconditionVerdict

    _M303CarryIngressErrorMixin = TerminalPreconditionErrorMixin[PreconditionVerdict]
else:
    _M303CarryIngressErrorMixin = TerminalPreconditionErrorMixin
from .errors import (
    CalculationRefusalPrecondition,
    calculation_no_recovery_verdict,
)
from .observations_repository import (
    ObservationEnvelopePayload,
    ObservationSourceKind,
    ResultDispositionProjection,
)

M303_DECLARATION_TYPE_HEADER_KEY = "declaration_type"
"""The only submitted-file header that can establish an official M303 result disposition."""

_M303_DISPOSITIONS = frozenset(
    {
        ResultDisposition.COMPENSACION,
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DOMICILIACION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    },
)
_NEGATIVE_DISPOSITIONS = frozenset(
    {
        ResultDisposition.COMPENSACION,
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    },
)
_POSITIVE_DISPOSITIONS = frozenset(
    {
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.DOMICILIACION,
    },
)
_ZERO = Decimal("0")


class M303CarryIngressError(_M303CarryIngressErrorMixin, CoreValidationError):
    """Modelo 303 carry evidence was insufficient or internally contradictory.

    A refusal reporting two sources of the same declared amount that disagree
    attaches a SAFETY :class:`~application.operator_actions.PreconditionVerdict`,
    because choosing either side silently changes the compensación the taxpayer
    carries forward. An evidence-incomplete refusal carries no verdict: the
    operator fixes it by supplying the missing evidence.
    """


def normalize_m303_carry_observation_envelope(
    envelope: ObservationEnvelopePayload,
) -> ObservationEnvelopePayload:
    """Resolve and persist the sole disposition-aware M303 carry projection.

    Official AEAT evidence must contain exactly one ``declaration_type`` header.
    Local app evidence must carry the typed result determined at the filing
    boundary.  Both paths converge here, where the result sign, supplied typed
    projection, and the normalized available/generated pair are checked before
    a later reader can treat the observation as carry evidence.
    """
    if str(envelope.observation.modelo) != Modelo.M303.value:
        return envelope

    disposition_projection = _resolve_result_disposition(envelope)
    _assert_result_sign_compatible(envelope, disposition_projection.disposition)
    normalized_observation, basis = _normalize_carry_observation(
        envelope.observation,
        disposition_projection.disposition,
        prior_basis=envelope.m303_compensation_basis,
    )
    return envelope.model_copy(
        update={
            "observation": normalized_observation,
            "result_disposition": disposition_projection,
            "m303_compensation_basis": basis,
        },
    )


def validate_normalized_m303_carry_observation_envelope(
    envelope: ObservationEnvelopePayload,
) -> ObservationEnvelopePayload:
    """Require an envelope to already carry the canonical M303 pair.

    History consumes persisted evidence rather than performing a second
    normalization. Re-running the ingress independently establishes what the
    canonical projection would be; requiring it to equal the supplied envelope
    prevents a caller from selecting either semantic amount after validation.
    Legacy envelopes remain readable through the observation repository, but
    cannot pass this carry-consumer boundary without a disposition and explicit
    normalized pair.
    """
    if str(envelope.observation.modelo) != Modelo.M303.value:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.non_m303_envelope",
            context={"modelo": envelope.observation.modelo},
        )
    normalized = normalize_m303_carry_observation_envelope(envelope)
    if normalized != envelope:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.envelope_not_normalized",
            context={
                "has_result_disposition": envelope.result_disposition is not None,
                "m303_compensation_basis": envelope.m303_compensation_basis,
            },
        )
    return envelope


def _resolve_result_disposition(envelope: ObservationEnvelopePayload) -> ResultDispositionProjection:
    """Recover one valid M303 disposition without selecting a convenient default."""
    header_projection = _header_projection(envelope)
    supplied = envelope.result_disposition

    if envelope.source_kind.is_official_aeat:
        if header_projection is None:
            raise M303CarryIngressError(
                translated_message=(
                    "application.calculations.m303_carry.errors.official_declaration_type_header_required"
                ),
                context={"source_kind": envelope.source_kind, "header_key": M303_DECLARATION_TYPE_HEADER_KEY},
            )
        if supplied is not None and supplied.disposition is not header_projection.disposition:
            raise M303CarryIngressError(
                translated_message=(
                    "application.calculations.m303_carry.errors.official_disposition_header_disagreement"
                ),
                context={
                    "typed_disposition": supplied.disposition,
                    "header_disposition": header_projection.disposition,
                },
                precondition_verdict=calculation_no_recovery_verdict(
                    CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
                    facts={
                        "source_kind": str(envelope.source_kind),
                        "typed_disposition": str(supplied.disposition),
                        "header_disposition": str(header_projection.disposition),
                    },
                ),
            )
        return header_projection

    if envelope.source_kind is ObservationSourceKind.APP_FILING:
        if supplied is None:
            raise M303CarryIngressError(
                translated_message="application.calculations.m303_carry.errors.local_filing_disposition_required",
                context={"source_kind": envelope.source_kind},
            )
        if supplied.provenance_kind != "app_filing":
            raise M303CarryIngressError(
                translated_message="application.calculations.m303_carry.errors.local_filing_provenance_required",
                context={"provenance_kind": supplied.provenance_kind},
            )
        if header_projection is not None and supplied.disposition is not header_projection.disposition:
            raise M303CarryIngressError(
                translated_message="application.calculations.m303_carry.errors.local_disposition_header_disagreement",
                context={
                    "typed_disposition": supplied.disposition,
                    "header_disposition": header_projection.disposition,
                },
                precondition_verdict=calculation_no_recovery_verdict(
                    CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
                    facts={
                        "source_kind": str(envelope.source_kind),
                        "typed_disposition": str(supplied.disposition),
                        "header_disposition": str(header_projection.disposition),
                    },
                ),
            )
        return supplied

    raise M303CarryIngressError(
        translated_message="application.calculations.m303_carry.errors.unsupported_provenance",
        context={"source_kind": envelope.source_kind},
    )


def _header_projection(envelope: ObservationEnvelopePayload) -> ResultDispositionProjection | None:
    """Return the one declaration-type header projection, refusing ambiguity."""
    facts = tuple(item for item in envelope.source_headers if item.header_key == M303_DECLARATION_TYPE_HEADER_KEY)
    if not facts:
        return None
    if len(facts) != 1:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.duplicate_declaration_type_headers",
            context={"header_count": len(facts), "header_key": M303_DECLARATION_TYPE_HEADER_KEY},
        )
    fact = facts[0]
    try:
        disposition = ResultDisposition(fact.value)
    except ValueError as exc:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.declaration_type_code_invalid",
            context={"value": fact.value, "source_locator": fact.source_locator},
        ) from exc
    if disposition not in _M303_DISPOSITIONS:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.declaration_type_code_not_admitted",
            context={"value": fact.value, "source_locator": fact.source_locator},
        )
    return ResultDispositionProjection(
        disposition=disposition,
        provenance_kind="source_header",
        provenance_locator=fact.source_locator,
    )


def _assert_result_sign_compatible(
    envelope: ObservationEnvelopePayload,
    disposition: ResultDisposition,
) -> None:
    """Reject a header election whose result sign could not have selected it."""
    resultado = envelope.observation.casilla_values.get(M303_COMPENSATION_RESULTADO_CASILLA)
    if resultado is None:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.resultado_casilla_required",
            context={"casilla_id": M303_COMPENSATION_RESULTADO_CASILLA},
        )
    compatible = (
        (disposition in _NEGATIVE_DISPOSITIONS and resultado < _ZERO)
        or (disposition in _POSITIVE_DISPOSITIONS and resultado > _ZERO)
        or (disposition is ResultDisposition.NEGATIVA and resultado == _ZERO)
    )
    if not compatible:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.disposition_resultado_sign_incompatible",
            context={"disposition": disposition, "resultado": str(resultado)},
            precondition_verdict=calculation_no_recovery_verdict(
                CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
                facts={
                    "disposition": str(disposition),
                    "resultado": str(resultado),
                    "casilla_id": str(M303_COMPENSATION_RESULTADO_CASILLA),
                },
            ),
        )


def _normalize_carry_observation(
    observation: object,
    disposition: ResultDisposition,
    *,
    prior_basis: str | None,
) -> tuple[object, str]:
    """Normalize the available/generated pair while preserving casilla-only storage."""
    # ``observation`` is deliberately typed structurally at this private seam:
    # importing RegistryModeloObservation just to repeat the public envelope's
    # field contract makes no runtime distinction and obscures the policy.
    from ...domain.calculations.registry.bindings import RegistryModeloObservation

    if not isinstance(observation, RegistryModeloObservation):
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.invalid_registry_observation",
            context={"observed_type": type(observation).__name__},
        )

    values = dict(observation.casilla_values)
    values.setdefault(M303_COMPENSATION_POSTERIOR_CASILLA, _ZERO)
    # A resultado-basis normalization materializes the generated casilla so
    # every persisted envelope carries the full pair. On revalidation that
    # materialized row is evidence of the already selected result basis, not a
    # fresh independently-filed generated operand that may flip the basis.
    if prior_basis == "resultado":
        values.pop(M303_COMPENSATION_GENERADA_CASILLA, None)
    derivation = derive_m303_compensation_available_from_casillas(
        values,
        refunded=result_disposition_is_refund(disposition),
    )
    if derivation is None:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.incomplete_supported_operands",
            context={"casilla_ids": sorted(str(casilla_id) for casilla_id in values)},
        )

    supplied_rows = {item.casilla_id: item for item in observation.observations}
    current_available = values.get(M303_COMPENSATION_AVAILABLE_CASILLA)
    available_was_calculated = (
        supplied_rows.get(M303_COMPENSATION_AVAILABLE_CASILLA) is not None
        and supplied_rows[M303_COMPENSATION_AVAILABLE_CASILLA].formula_id is not None
    )
    current_generated = values.get(M303_COMPENSATION_GENERADA_CASILLA)
    _require_supplied_pair_matches_derivation(
        derivation,
        current_available=current_available,
        current_generated=current_generated,
        available_was_calculated=available_was_calculated,
    )

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(candidate for candidate in modelos if candidate.id == Modelo.M303.value)
    revision = select_revision(
        modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casillas = casillas_by_id(revision)
    formula_id = _resolve_available_compensation_formula_id(revision, derivation)

    available = CasillaObservation(
        casilla_id=M303_COMPENSATION_AVAILABLE_CASILLA,
        value=derivation.available,
        formula_id=formula_id,
        operand_refs=derivation.operand_refs,
        operand_casilla_refs=derivation.operand_refs,
        operand_values=derivation.operand_values,
        legal_refs=tuple(casillas[M303_COMPENSATION_AVAILABLE_CASILLA].legal_refs),
        source_refs=tuple(casillas[M303_COMPENSATION_AVAILABLE_CASILLA].source_refs),
    )
    generated = CasillaObservation(
        casilla_id=M303_COMPENSATION_GENERADA_CASILLA,
        value=derivation.generated,
        legal_refs=tuple(casillas[M303_COMPENSATION_GENERADA_CASILLA].legal_refs),
        source_refs=tuple(casillas[M303_COMPENSATION_GENERADA_CASILLA].source_refs),
    )

    normalized = _spliced_carry_observations(observation.observations, available, generated)
    return observation.model_copy(update={"observations": normalized}), derivation.basis


def _require_supplied_pair_matches_derivation(
    derivation: M303CompensationAvailableDerivation,
    *,
    current_available: Decimal | None,
    current_generated: Decimal | None,
    available_was_calculated: bool,
) -> None:
    """Refuse a supplied carry pair that contradicts the disposition-aware derivation.

    A supplied row that the filer's own engine calculated is not a contradiction:
    it is the same derivation arriving pre-computed, so it never blocks ingress.
    """
    if current_available is not None and current_available != derivation.available and not available_was_calculated:
        raise M303CarryIngressError(
            translated_message=("application.calculations.m303_carry.errors.supplied_available_contradicts_derivation"),
            context={
                "supplied_available": str(current_available),
                "derived_available": str(derivation.available),
                "basis": derivation.basis,
            },
            precondition_verdict=calculation_no_recovery_verdict(
                CalculationRefusalPrecondition.M303_CARRY_DERIVATION_CONSISTENT,
                facts={
                    "supplied_available": str(current_available),
                    "derived_available": str(derivation.available),
                    "basis": str(derivation.basis),
                },
            ),
        )
    if (
        current_available is not None
        and current_generated is not None
        and current_generated != derivation.generated
        and not available_was_calculated
    ):
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.supplied_pair_contradicts_derivation",
            context={
                "supplied_available": str(current_available),
                "supplied_generated": str(current_generated),
                "derived_generated": str(derivation.generated),
                "basis": derivation.basis,
            },
            precondition_verdict=calculation_no_recovery_verdict(
                CalculationRefusalPrecondition.M303_CARRY_DERIVATION_CONSISTENT,
                facts={
                    "supplied_available": str(current_available),
                    "supplied_generated": str(current_generated),
                    "derived_generated": str(derivation.generated),
                    "basis": str(derivation.basis),
                },
            ),
        )


def _resolve_available_compensation_formula_id(
    revision: ModeloRevision,
    derivation: M303CompensationAvailableDerivation,
) -> str | None:
    """Return the registry formula id backing a generated-basis available projection.

    A resultado-basis derivation carries no operands and so cites no formula.
    """
    if not derivation.operand_refs:
        return None
    formula = next(
        (item for item in revision.formulas if item.target_casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA),
        None,
    )
    if formula is None:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.available_compensation_formula_missing",
            context={
                "revision_id": revision.id,
                "target_casilla_id": str(M303_COMPENSATION_AVAILABLE_CASILLA),
            },
        )
    expected_operands = expression_casilla_refs(formula.expression)
    if derivation.operand_refs != expected_operands:
        raise M303CarryIngressError(
            translated_message="application.calculations.m303_carry.errors.carry_operands_disagree_with_formula",
            context={
                "derivation_operands": derivation.operand_refs,
                "registry_operands": expected_operands,
            },
            precondition_verdict=calculation_no_recovery_verdict(
                CalculationRefusalPrecondition.M303_CARRY_MATCHES_REGISTRY_FORMULA,
                facts={
                    "formula_id": str(formula.id),
                    "derivation_operands": ",".join(str(item) for item in derivation.operand_refs),
                    "registry_operands": ",".join(str(item) for item in expected_operands),
                },
            ),
        )
    return formula.id


def _spliced_carry_observations(
    supplied: tuple[CasillaObservation, ...],
    available: CasillaObservation,
    generated: CasillaObservation,
) -> tuple[CasillaObservation, ...]:
    """Replace the carry pair in place, appending whichever row the envelope lacked."""
    normalized: list[CasillaObservation] = []
    seen_available = False
    seen_generated = False
    for item in supplied:
        if item.casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA:
            normalized.append(available)
            seen_available = True
        elif item.casilla_id == M303_COMPENSATION_GENERADA_CASILLA:
            normalized.append(generated)
            seen_generated = True
        else:
            normalized.append(item)
    if not seen_available:
        normalized.append(available)
    if not seen_generated:
        normalized.append(generated)
    return tuple(normalized)


__all__ = [
    "M303_DECLARATION_TYPE_HEADER_KEY",
    "M303CarryIngressError",
    "normalize_m303_carry_observation_envelope",
    "validate_normalized_m303_carry_observation_envelope",
]
