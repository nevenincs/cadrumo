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

from ...core import Modelo, ResultDisposition, result_disposition_is_refund
from ...core.errors import CoreValidationError
from ...core.resources import resources
from ...domain.calculations.registry import CasillaObservation, casillas_by_id, expression_casilla_refs
from ...domain.iva_compensation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    derive_m303_compensation_available_from_casillas,
)
from ._observations_repository import (
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


class M303CarryIngressError(CoreValidationError):
    """Modelo 303 carry evidence was insufficient or internally contradictory."""


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
            "Modelo 303 carry history received a non-Modelo 303 observation envelope",
            context={"modelo": envelope.observation.modelo},
        )
    normalized = normalize_m303_carry_observation_envelope(envelope)
    if normalized != envelope:
        raise M303CarryIngressError(
            "Modelo 303 carry history requires an already-normalized disposition-aware available/generated pair",
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
                "official Modelo 303 carry evidence requires exactly one declaration_type source header",
                context={"source_kind": envelope.source_kind, "header_key": M303_DECLARATION_TYPE_HEADER_KEY},
            )
        if supplied is not None and supplied.disposition is not header_projection.disposition:
            raise M303CarryIngressError(
                "official Modelo 303 typed disposition disagrees with the declaration_type source header",
                context={
                    "typed_disposition": supplied.disposition,
                    "header_disposition": header_projection.disposition,
                },
            )
        return header_projection

    if envelope.source_kind is ObservationSourceKind.APP_FILING:
        if supplied is None:
            raise M303CarryIngressError(
                "local Modelo 303 filing carry evidence requires the filing-boundary result disposition",
                context={"source_kind": envelope.source_kind},
            )
        if supplied.provenance_kind != "app_filing":
            raise M303CarryIngressError(
                "local Modelo 303 filing disposition must retain app_filing provenance",
                context={"provenance_kind": supplied.provenance_kind},
            )
        if header_projection is not None and supplied.disposition is not header_projection.disposition:
            raise M303CarryIngressError(
                "local Modelo 303 typed disposition disagrees with the declaration_type source header",
                context={
                    "typed_disposition": supplied.disposition,
                    "header_disposition": header_projection.disposition,
                },
            )
        return supplied

    raise M303CarryIngressError(
        "Modelo 303 carry normalization accepts only official AEAT or app_filing provenance",
        context={"source_kind": envelope.source_kind},
    )


def _header_projection(envelope: ObservationEnvelopePayload) -> ResultDispositionProjection | None:
    """Return the one declaration-type header projection, refusing ambiguity."""
    facts = tuple(item for item in envelope.source_headers if item.header_key == M303_DECLARATION_TYPE_HEADER_KEY)
    if not facts:
        return None
    if len(facts) != 1:
        raise M303CarryIngressError(
            "Modelo 303 carry evidence has duplicate declaration_type source headers",
            context={"header_count": len(facts), "header_key": M303_DECLARATION_TYPE_HEADER_KEY},
        )
    fact = facts[0]
    try:
        disposition = ResultDisposition(fact.value)
    except ValueError as exc:
        raise M303CarryIngressError(
            "Modelo 303 declaration_type source header has an invalid result-disposition code",
            context={"value": fact.value, "source_locator": fact.source_locator},
        ) from exc
    if disposition not in _M303_DISPOSITIONS:
        raise M303CarryIngressError(
            "Modelo 303 declaration_type source header uses a code not admitted by the Modelo 303 diseño",
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
            "Modelo 303 carry normalization requires the filed resultado casilla",
            context={"casilla_id": M303_COMPENSATION_RESULTADO_CASILLA},
        )
    compatible = (
        (disposition in _NEGATIVE_DISPOSITIONS and resultado < _ZERO)
        or (disposition in _POSITIVE_DISPOSITIONS and resultado > _ZERO)
        or (disposition is ResultDisposition.NEGATIVA and resultado == _ZERO)
    )
    if not compatible:
        raise M303CarryIngressError(
            "Modelo 303 declaration disposition is incompatible with the filed resultado sign",
            context={"disposition": disposition, "resultado": str(resultado)},
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
    from ...domain.calculations.registry import RegistryModeloObservation

    if not isinstance(observation, RegistryModeloObservation):
        raise M303CarryIngressError("Modelo 303 carry ingress received an invalid registry observation")

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
            "Modelo 303 carry normalization has incomplete supported operands",
            context={"casilla_ids": sorted(str(casilla_id) for casilla_id in values)},
        )

    supplied_rows = {item.casilla_id: item for item in observation.observations}
    current_available = values.get(M303_COMPENSATION_AVAILABLE_CASILLA)
    available_was_calculated = (
        supplied_rows.get(M303_COMPENSATION_AVAILABLE_CASILLA) is not None
        and supplied_rows[M303_COMPENSATION_AVAILABLE_CASILLA].formula_id is not None
    )
    if current_available is not None and current_available != derivation.available and not available_was_calculated:
        raise M303CarryIngressError(
            "Modelo 303 supplied available compensation contradicts the disposition-aware derivation",
            context={
                "supplied_available": str(current_available),
                "derived_available": str(derivation.available),
                "basis": derivation.basis,
            },
        )
    current_generated = values.get(M303_COMPENSATION_GENERADA_CASILLA)
    if (
        current_available is not None
        and current_generated is not None
        and current_generated != derivation.generated
        and not available_was_calculated
    ):
        raise M303CarryIngressError(
            "Modelo 303 supplied available/generated pair contradicts the disposition-aware derivation",
            context={
                "supplied_available": str(current_available),
                "supplied_generated": str(current_generated),
                "derived_generated": str(derivation.generated),
                "basis": derivation.basis,
            },
        )

    snapshot = resources().modelos.authority.snapshot(
        Modelo.M303.value,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casillas = casillas_by_id(snapshot.revision)
    formula = next(
        (item for item in snapshot.revision.formulas if item.target_casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA),
        None,
    )
    formula_id = None
    if derivation.operand_refs:
        if formula is None:
            raise M303CarryIngressError(
                "Modelo 303 registry has no formula for the generated-basis available compensation projection",
            )
        expected_operands = expression_casilla_refs(formula.expression)
        if derivation.operand_refs != expected_operands:
            raise M303CarryIngressError(
                "Modelo 303 generated-basis carry operands disagree with the registry formula",
                context={
                    "derivation_operands": derivation.operand_refs,
                    "registry_operands": expected_operands,
                },
            )
        formula_id = formula.id

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

    normalized: list[CasillaObservation] = []
    seen_available = False
    seen_generated = False
    for item in observation.observations:
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
    return observation.model_copy(update={"observations": tuple(normalized)}), derivation.basis


__all__ = [
    "M303_DECLARATION_TYPE_HEADER_KEY",
    "M303CarryIngressError",
    "normalize_m303_carry_observation_envelope",
    "validate_normalized_m303_carry_observation_envelope",
]
