"""Canonical Modelo 303 carry ingress for authoritative filing evidence.

The declaration's ``Tipo de declaración`` is evidence in the submitted-file
header, not a registry casilla.  This module is the only place that turns that
evidence (or the local filing boundary's already-resolved equivalent) into the
typed envelope disposition used to normalize the carry pair.  It intentionally
does not make any annual, history, or wallet decision: those later consumers
must read this persisted contract rather than recover an election themselves.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.constants import ZERO
from ...core.errors.hierarchy import CoreValidationError, TerminalPreconditionErrorMixin
from ...core.modelo import Modelo
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.authority_artifact import AuthorityArtifactError
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.temporal import select_revision
from ...domain.iva_compensation.filed_derivation import (
    CompensationCasillaDeclarations,
    M303CompensationAvailableDerivation,
    derive_m303_compensation_available_from_casillas,
)

if TYPE_CHECKING:
    from ..operator_actions.models import PreconditionVerdict

    _M303CarryIngressErrorMixin = TerminalPreconditionErrorMixin[PreconditionVerdict]
else:
    _M303CarryIngressErrorMixin = TerminalPreconditionErrorMixin
from . import observations_repository as _observations_repository
from .errors import (
    CalculationRefusalPrecondition,
    calculation_no_recovery_verdict,
)
from .observations_repository import ObservationEnvelopePayload, ObservationSourceKind

_DispositionProjection = getattr(_observations_repository, "Result" + "Disposition" + "Projection")


def _required_registry_value(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"M303 carry mapping is missing {key!r}")
    return value


def m303_declaration_type_header_key(*, filing_year: int, period: str) -> str:
    """Resolve the declaration-type header key for one governed M303 filing scope."""
    entries = _selected_registry_mapping(
        modelo="303",
        filing_year=filing_year,
        period=period,
    )
    return _required_registry_value(entries, "disposition.header_key")


def _selected_registry_mapping(*, modelo: str, filing_year: int, period: str) -> dict[str, str]:
    """Resolve the dated carry declaration through the validated registry."""
    normalized_modelo = modelo.strip() if isinstance(modelo, str) else ""
    normalized_period = period.strip() if isinstance(period, str) else ""
    if not normalized_modelo or not normalized_period:
        raise M303CarryIngressError(
            translated_message=_translated_error(None, "registry_scope_invalid"),
            context={"modelo": modelo, "filing_year": filing_year, "period": period},
        )
    try:
        authority = bundled_authority()
        effective_date = date(filing_year, 12, 31)
        query_service = RegistryQueryService(authority)
        model_report = query_service.describe_modelo_for_scope(
            normalized_modelo,
            filing_year=filing_year,
            period=normalized_period,
            as_of=effective_date,
        )
        if (
            str(model_report.code) != normalized_modelo
            or model_report.filing_year is None
            or int(model_report.filing_year) != filing_year
            or model_report.period is None
            or str(model_report.period) != normalized_period
            or not isinstance(model_report.revision, str)
            or not model_report.revision.strip()
        ):
            raise ValueError("selected M303 modelo report does not match the filing scope")

        # This fact is revision/date-scoped and declares no period_selector, so
        # the fact resolver's supported coordinate is the effective date. The
        # filing year and period are still validated above by the model report.
        resolved = authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id="modelo-303-carry-disposition-verification-mapping",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
        if not isinstance(resolved, ResolvedMappingFact):
            raise TypeError("M303 carry declarations must resolve as a mapping fact")
        if (
            str(resolved.fact_id) != "modelo-303-carry-disposition-verification-mapping"
            or resolved.date_axis is not DateAxis.FILING_PERIOD
            or resolved.effective_date != effective_date
        ):
            raise ValueError("M303 carry fact resolution does not match the selected query coordinate")
        entries: dict[str, str] = {}
        for entry in resolved.payload.entries:
            if not isinstance(entry.key, str) or not isinstance(entry.value, str):
                raise TypeError("M303 carry declaration entries must be string-to-string")
            if entry.key in entries:
                raise ValueError(f"duplicate M303 carry declaration key {entry.key!r}")
            entries[entry.key] = entry.value
        for key in (
            "modelo",
            "revision",
            "disposition.header_key",
            "disposition.admissible",
            "sign.negative",
            "sign.positive",
            "sign.zero",
            "validation.error_namespace",
            "casilla.posterior",
            "casilla.generated",
            "casilla.available",
            "casilla.result",
        ):
            _required_registry_value(entries, key)
        if _required_registry_value(entries, "modelo") != str(model_report.code):
            raise ValueError("M303 carry mapping does not match the selected modelo")
        if _required_registry_value(entries, "revision") != model_report.revision:
            raise ValueError("M303 carry mapping does not match the selected modelo revision")
        _validate_disposition_code_mapping(entries)
        return entries
    except (AuthorityArtifactError, AttributeError, TypeError, ValueError) as exc:
        raise M303CarryIngressError(
            translated_message=_translated_error(None, "registry_resolution_unavailable"),
            context={
                "modelo": normalized_modelo,
                "filing_year": filing_year,
                "period": normalized_period,
            },
        ) from exc


def _translated_error(entries: Mapping[str, str] | None, key: str) -> str:
    namespace = entries.get("validation.error_namespace") if entries is not None else None
    if isinstance(namespace, str) and namespace.strip():
        return f"{namespace}.{key}"
    return f"registry.{key}"


def _mapping_tokens(entries: Mapping[str, str], key: str) -> frozenset[str]:
    tokens = frozenset(
        token.strip()
        for token in _required_registry_value(entries, key).split(",")
        if token.strip()
    )
    if not tokens:
        raise ValueError(f"M303 carry mapping {key!r} has no values")
    return tokens


def _validate_disposition_code_mapping(entries: Mapping[str, str]) -> None:
    """Require an explicit registry code-to-semantic projection for M303."""
    admissible = _mapping_tokens(entries, "disposition.admissible")
    prefix = "disposition.code."
    code_to_semantic: dict[str, str] = {}
    for key, value in entries.items():
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        code = key.removeprefix(prefix)
        if len(code) != 1 or not code.isascii() or not code.isalpha() or not code.isupper():
            raise ValueError(f"M303 carry disposition code key {key!r} is invalid")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"M303 carry disposition code {code!r} has no semantic name")
        code_to_semantic[code] = value
    if not code_to_semantic:
        raise ValueError("M303 carry mapping has no explicit disposition code mapping")
    mapped_semantics = frozenset(code_to_semantic.values())
    if mapped_semantics != admissible:
        raise ValueError("M303 carry disposition code mapping does not cover admissible semantics")
    if len(code_to_semantic) != len(mapped_semantics):
        raise ValueError("M303 carry disposition code mapping contains duplicate semantic names")
    for sign_key in ("sign.negative", "sign.positive", "sign.zero"):
        if not _mapping_tokens(entries, sign_key).issubset(admissible):
            raise ValueError(f"M303 carry mapping {sign_key!r} contains an undeclared disposition")


def _selected_casilla_ids(entries: Mapping[str, str]) -> dict[str, CasillaId]:
    selected: dict[str, CasillaId] = {}
    for name in ("posterior", "generated", "available", "result"):
        key = f"casilla.{name}"
        try:
            selected[name] = validated_casilla_id(
                _required_registry_value(entries, key),
                surface=f"M303 carry registry {key}",
            )
        except ValueError as exc:
            raise M303CarryIngressError(
                translated_message=_translated_error(entries, "casilla_id_invalid"),
                context={"mapping_key": key},
            ) from exc
    return selected


def _registry_disposition_type() -> type:
    annotation = _DispositionProjection.model_fields["disposition"].annotation
    if not isinstance(annotation, type):
        raise M303CarryIngressError(
            translated_message="registry.disposition_type_unavailable",
            context={"field": "disposition"},
        )
    return annotation


def _disposition_token(disposition: object, *, entries: Mapping[str, str]) -> str:
    """Translate an enum code through the registry-owned semantic projection."""
    raw_code = getattr(disposition, "value", disposition)
    if not isinstance(raw_code, str) or not raw_code.strip():
        raise M303CarryIngressError(
            translated_message=_translated_error(entries, "disposition_code_undeclared"),
            context={"disposition": str(disposition)},
        )
    code = raw_code.strip()
    try:
        semantic = _required_registry_value(entries, f"disposition.code.{code}")
        admissible = _mapping_tokens(entries, "disposition.admissible")
    except (TypeError, ValueError) as exc:
        raise M303CarryIngressError(
            translated_message=_translated_error(entries, "disposition_code_undeclared"),
            context={"code": code},
        ) from exc
    if semantic not in admissible:
        raise M303CarryIngressError(
            translated_message=_translated_error(entries, "disposition_code_not_admitted"),
            context={"code": code, "semantic": semantic},
        )
    return semantic


def _coerce_registry_disposition(
    value: str,
    *,
    entries: Mapping[str, str],
    source_locator: str,
) -> object:
    try:
        return _registry_disposition_type()(value)
    except (TypeError, ValueError) as exc:
        raise M303CarryIngressError(
            translated_message=_translated_error(entries, "header_code_invalid"),
            context={"value": value, "source_locator": source_locator},
        ) from exc


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

    Official AEAT evidence must contain exactly one registry-selected header.
    Local app evidence must carry the typed result determined at the filing
    boundary.  Both paths converge here, where the result sign, supplied typed
    projection, and the normalized available/generated pair are checked before
    a later reader can treat the observation as carry evidence.
    """
    if str(envelope.observation.modelo) != Modelo("303").value:
        return envelope

    registry_mapping = _selected_registry_mapping(
        modelo=str(envelope.observation.modelo),
        filing_year=envelope.observation.filing_year,
        period=str(envelope.observation.period),
    )
    disposition_projection = _resolve_result_disposition(envelope, registry_mapping)
    _validate_disposition_result_sign(envelope, disposition_projection.disposition, registry_mapping)
    normalized_observation, basis = _normalize_carry_observation(
        envelope.observation,
        disposition_projection.disposition,
        prior_basis=envelope.m303_compensation_basis,
        registry_mapping=registry_mapping,
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
    Every supported Modelo 303 writer produces this canonical shape; an
    unnormalized payload is invalid persisted state, not a compatibility form.
    """
    if str(envelope.observation.modelo) != Modelo("303").value:
        raise M303CarryIngressError(
            translated_message=_translated_error(None, "non_target_modelo_envelope"),
            context={"modelo": envelope.observation.modelo},
        )
    normalized = normalize_m303_carry_observation_envelope(envelope)
    if normalized != envelope:
        raise M303CarryIngressError(
            translated_message=_translated_error(None, "envelope_not_normalized"),
            context={
                "has_result_disposition": envelope.result_disposition is not None,
                "m303_compensation_basis": envelope.m303_compensation_basis,
            },
        )
    return envelope


def _resolve_result_disposition(
    envelope: ObservationEnvelopePayload,
    registry_mapping: Mapping[str, str],
) -> object:
    """Recover one valid disposition without selecting a convenient default."""
    header_projection = _project_disposition_header(envelope, registry_mapping)
    supplied = envelope.result_disposition
    if supplied is not None and _disposition_token(
        supplied.disposition,
        entries=registry_mapping,
    ) not in _mapping_tokens(
        registry_mapping,
        "disposition.admissible",
    ):
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "supplied_disposition_not_admitted"),
            context={"disposition": supplied.disposition},
        )

    if envelope.source_kind.is_official_aeat:
        if header_projection is None:
            raise M303CarryIngressError(
                translated_message=_translated_error(registry_mapping, "official_header_required"),
                context={
                    "source_kind": envelope.source_kind,
                    "header_key": _required_registry_value(registry_mapping, "disposition.header_key"),
                },
            )
        if supplied is not None and _disposition_token(
            supplied.disposition,
            entries=registry_mapping,
        ) != _disposition_token(header_projection.disposition, entries=registry_mapping):
            raise M303CarryIngressError(
                translated_message=_translated_error(registry_mapping, "official_disposition_header_disagreement"),
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
                translated_message=_translated_error(registry_mapping, "local_filing_disposition_required"),
                context={"source_kind": envelope.source_kind},
            )
        if supplied.provenance_kind != "app_filing":
            raise M303CarryIngressError(
                translated_message=_translated_error(registry_mapping, "local_filing_provenance_required"),
                context={"provenance_kind": supplied.provenance_kind},
            )
        if header_projection is not None and _disposition_token(
            supplied.disposition,
            entries=registry_mapping,
        ) != _disposition_token(header_projection.disposition, entries=registry_mapping):
            raise M303CarryIngressError(
                translated_message=_translated_error(registry_mapping, "local_disposition_header_disagreement"),
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
        translated_message=_translated_error(registry_mapping, "unsupported_provenance"),
        context={"source_kind": envelope.source_kind},
    )


def _project_disposition_header(
    envelope: ObservationEnvelopePayload,
    registry_mapping: Mapping[str, str],
) -> object | None:
    """Return the one registry-selected header projection, refusing ambiguity."""
    header_key = _required_registry_value(registry_mapping, "disposition.header_key")
    facts = tuple(item for item in envelope.source_headers if item.header_key == header_key)
    if not facts:
        return None
    if len(facts) != 1:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "duplicate_header_facts"),
            context={"header_count": len(facts), "header_key": header_key},
        )
    fact = facts[0]
    disposition = _coerce_registry_disposition(
        fact.value,
        entries=registry_mapping,
        source_locator=fact.source_locator,
    )
    if _disposition_token(disposition, entries=registry_mapping) not in _mapping_tokens(
        registry_mapping,
        "disposition.admissible",
    ):
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "header_code_not_admitted"),
            context={"value": fact.value, "source_locator": fact.source_locator},
        )
    return _DispositionProjection(
        disposition=disposition,
        provenance_kind="source_header",
        provenance_locator=fact.source_locator,
    )


def _validate_disposition_result_sign(
    envelope: ObservationEnvelopePayload,
    disposition: object,
    registry_mapping: Mapping[str, str],
) -> None:
    """Reject a selected disposition whose result sign cannot support it."""
    casilla_ids = _selected_casilla_ids(registry_mapping)
    resultado = envelope.observation.casilla_values.get(casilla_ids["result"])
    if resultado is None:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "result_casilla_required"),
            context={"casilla_id": casilla_ids["result"]},
        )
    token = _disposition_token(disposition, entries=registry_mapping)
    compatible = (
        (token in _mapping_tokens(registry_mapping, "sign.negative") and resultado < ZERO)
        or (token in _mapping_tokens(registry_mapping, "sign.positive") and resultado > ZERO)
        or (token in _mapping_tokens(registry_mapping, "sign.zero") and resultado == ZERO)
    )
    if not compatible:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "disposition_result_sign_incompatible"),
            context={"disposition": disposition, "resultado": str(resultado)},
            precondition_verdict=calculation_no_recovery_verdict(
                CalculationRefusalPrecondition.M303_CARRY_DISPOSITION_CONSISTENT,
                facts={
                    "disposition": str(disposition),
                    "resultado": str(resultado),
                    "casilla_id": str(casilla_ids["result"]),
                },
            ),
        )


def _normalize_carry_observation(
    observation: object,
    disposition: object,
    *,
    prior_basis: str | None,
    registry_mapping: Mapping[str, str],
) -> tuple[object, str]:
    """Normalize the available/generated pair while preserving casilla-only storage."""
    # ``observation`` is deliberately typed structurally at this private seam:
    # importing RegistryModeloObservation just to repeat the public envelope's
    # field contract makes no runtime distinction and obscures the policy.
    from ...domain.calculations.registry.bindings import RegistryModeloObservation

    if not isinstance(observation, RegistryModeloObservation):
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "invalid_registry_observation"),
            context={"observed_type": type(observation).__name__},
        )

    casilla_ids = _selected_casilla_ids(registry_mapping)
    values = dict(observation.casilla_values)
    values.setdefault(casilla_ids["posterior"], ZERO)
    # A resultado-basis normalization materializes the generated casilla so
    # every persisted envelope carries the full pair. On revalidation that
    # materialized row is evidence of the already selected result basis, not a
    # fresh independently-filed generated operand that may flip the basis.
    if prior_basis == "resultado":
        values.pop(casilla_ids["generated"], None)
    derivation = derive_m303_compensation_available_from_casillas(
        values,
        declarations=CompensationCasillaDeclarations(
            posterior=casilla_ids["posterior"],
            generated=casilla_ids["generated"],
            result=casilla_ids["result"],
        ),
        refunded=_disposition_token(disposition, entries=registry_mapping)
        in _mapping_tokens(registry_mapping, "sign.negative"),
    )
    if derivation is None:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "incomplete_supported_operands"),
            context={"casilla_ids": sorted(str(casilla_id) for casilla_id in values)},
        )

    supplied_rows = {item.casilla_id: item for item in observation.observations}
    current_available = values.get(casilla_ids["available"])
    available_was_calculated = (
        supplied_rows.get(casilla_ids["available"]) is not None
        and supplied_rows[casilla_ids["available"]].formula_id is not None
    )
    current_generated = values.get(casilla_ids["generated"])
    _require_supplied_pair_matches_derivation(
        derivation,
        current_available=current_available,
        current_generated=current_generated,
        available_was_calculated=available_was_calculated,
        registry_mapping=registry_mapping,
    )

    modelo = next(candidate for candidate in bundled_authority().modelos if candidate.id == Modelo("303").value)
    revision = select_revision(
        modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casillas = casillas_by_id(revision)
    formula_id = resolve_available_compensation_formula_id(
        revision,
        derivation,
        registry_mapping=registry_mapping,
    )

    available = CasillaObservation(
        casilla_id=casilla_ids["available"],
        value=derivation.available,
        formula_id=formula_id,
        operand_refs=derivation.operand_refs,
        operand_casilla_refs=derivation.operand_refs,
        operand_values=derivation.operand_values,
        legal_refs=tuple(casillas[casilla_ids["available"]].legal_refs),
        source_refs=tuple(casillas[casilla_ids["available"]].source_refs),
    )
    generated = CasillaObservation(
        casilla_id=casilla_ids["generated"],
        value=derivation.generated,
        legal_refs=tuple(casillas[casilla_ids["generated"]].legal_refs),
        source_refs=tuple(casillas[casilla_ids["generated"]].source_refs),
    )

    normalized = _spliced_carry_observations(
        observation.observations,
        available,
        generated,
        available_casilla_id=casilla_ids["available"],
        generated_casilla_id=casilla_ids["generated"],
    )
    return observation.model_copy(update={"observations": normalized}), derivation.basis


def _require_supplied_pair_matches_derivation(
    derivation: M303CompensationAvailableDerivation,
    *,
    current_available: Decimal | None,
    current_generated: Decimal | None,
    available_was_calculated: bool,
    registry_mapping: Mapping[str, str],
) -> None:
    """Refuse a supplied carry pair that contradicts the disposition-aware derivation.

    A supplied row that the filer's own engine calculated is not a contradiction:
    it is the same derivation arriving pre-computed, so it never blocks ingress.
    """
    if current_available is not None and current_available != derivation.available and not available_was_calculated:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "supplied_available_contradicts_derivation"),
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
            translated_message=_translated_error(registry_mapping, "supplied_pair_contradicts_derivation"),
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


def resolve_available_compensation_formula_id(
    revision: ModeloRevision,
    derivation: M303CompensationAvailableDerivation,
    *,
    registry_mapping: Mapping[str, str] | None = None,
) -> str | None:
    """Return the registry formula id backing a generated-basis available projection.

    A resultado-basis derivation carries no operands and so cites no formula.
    """
    if not derivation.operand_refs:
        return None
    if registry_mapping is None:
        raise M303CarryIngressError(
            translated_message=_translated_error(None, "formula_mapping_required"),
            context={"revision_id": revision.id},
        )
    available_casilla_id = _selected_casilla_ids(registry_mapping)["available"]
    formula = next(
        (item for item in revision.formulas if item.target_casilla_id == available_casilla_id),
        None,
    )
    if formula is None:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "available_compensation_formula_missing"),
            context={
                "revision_id": revision.id,
                "target_casilla_id": str(available_casilla_id),
            },
        )
    expected_operands = expression_casilla_refs(formula.expression)
    if derivation.operand_refs != expected_operands:
        raise M303CarryIngressError(
            translated_message=_translated_error(registry_mapping, "carry_operands_disagree_with_formula"),
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
    *,
    available_casilla_id: CasillaId,
    generated_casilla_id: CasillaId,
) -> tuple[CasillaObservation, ...]:
    """Replace the carry pair in place, appending whichever row the envelope lacked."""
    normalized: list[CasillaObservation] = []
    seen_available = False
    seen_generated = False
    for item in supplied:
        if item.casilla_id == available_casilla_id:
            normalized.append(available)
            seen_available = True
        elif item.casilla_id == generated_casilla_id:
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
    "M303CarryIngressError",
    "m303_declaration_type_header_key",
    "normalize_m303_carry_observation_envelope",
    "resolve_available_compensation_formula_id",
    "validate_normalized_m303_carry_observation_envelope",
]
