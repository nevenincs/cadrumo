"""Governed-fact projections of selected modelo-owned parameters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_base import DateAxis
from ..schema_formula import DatedValue, ParameterDefinition
from .resolution import ScalarFactQuery
from .schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    ScalarFactPayload,
)

__all__ = [
    "MODELO_PARAMETER_PROJECTION_PROVIDER_ID",
    "ModeloParameterFact",
    "compile_modelo_parameter_projection_facts",
    "modelo_parameter_fact_query",
]


MODELO_PARAMETER_PROJECTION_PROVIDER_ID = "modelo-parameter-projections"


class ModeloParameterFact(StrEnum):
    """Closed semantic identities projected for Wave 3 consumer migrations."""

    M347_COUNTERPARTY_ANNUAL_THRESHOLD = "declarations.m347.counterparty-annual-threshold"
    MATERNITY_MONTHLY_DEDUCTION = "renta.maternity.monthly-deduction"
    MATERNITY_ANNUAL_CAP = "renta.maternity.annual-cap"
    MATERNITY_POST_ENROLLMENT_INCREMENT = "renta.maternity.post-enrollment-increment"


@dataclass(frozen=True, slots=True)
class _ProjectionTarget:
    fact: ModeloParameterFact
    modelo_id: str
    parameter_id: str


_TARGETS = (
    _ProjectionTarget(
        ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD,
        "347",
        "modelo-347-tercero-anual-threshold-eur",
    ),
    _ProjectionTarget(ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION, "100", "renta-2025-maternidad-mensual"),
    _ProjectionTarget(ModeloParameterFact.MATERNITY_ANNUAL_CAP, "100", "renta-2025-maternidad-cap-anual"),
    _ProjectionTarget(
        ModeloParameterFact.MATERNITY_POST_ENROLLMENT_INCREMENT,
        "100",
        "renta-2025-maternidad-alta-posterior-incremento",
    ),
)
_TARGET_BY_FACT: Mapping[ModeloParameterFact, _ProjectionTarget] = {target.fact: target for target in _TARGETS}


def modelo_parameter_fact_query(fact: ModeloParameterFact, on: date) -> ScalarFactQuery:
    """Build an exact query for one projected modelo parameter."""
    target = _TARGET_BY_FACT[fact]
    return ScalarFactQuery(
        fact_id=fact.value,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=on,
        selectors=(
            FactSelector(name="modelo", value=target.modelo_id),
            FactSelector(name="parameter_id", value=target.parameter_id),
        ),
    )


def compile_modelo_parameter_projection_facts(
    modelos: Iterable[ModeloDefinition],
) -> tuple[GovernedFact, ...]:
    """Project the exact migration targets from already-compiled revisions."""
    by_id = {modelo.id: modelo for modelo in modelos}
    facts: list[GovernedFact] = []
    for target in _TARGETS:
        modelo = by_id.get(target.modelo_id)
        if modelo is None:
            raise RegistryValidationError(f"modelo projection requires modelo {target.modelo_id!r}")
        variants = _target_variants(modelo, target)
        if not variants:
            raise RegistryValidationError(
                f"modelo {target.modelo_id} projection requires parameter {target.parameter_id!r}",
            )
        facts.append(GovernedFact(fact_id=target.fact.value, family=GovernedFactFamily.SCALAR, variants=variants))
    return tuple(facts)


def _target_variants(modelo: ModeloDefinition, target: _ProjectionTarget) -> tuple[GovernedFactVariant, ...]:
    variants: list[GovernedFactVariant] = []
    seen: set[tuple[object, ...]] = set()
    for revision in modelo.revisions.values():
        for parameter in revision.parameters:
            if parameter.id != target.parameter_id:
                continue
            _require_scalar_parameter(parameter, modelo_id=modelo.id, revision_id=revision.id)
            for value in parameter.values:
                identity = (
                    value.date_axis,
                    value.valid_from,
                    value.valid_to,
                    value.value,
                    parameter.unit,
                    parameter.legal_refs,
                    parameter.source_refs,
                    parameter.source_citations,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                variants.append(_project_variant(modelo.id, revision, parameter, value))
    return tuple(sorted(variants, key=lambda variant: (variant.valid_from, variant.variant_id)))


def _require_scalar_parameter(parameter: ParameterDefinition, *, modelo_id: str, revision_id: str) -> None:
    if parameter.data_type.value not in {"decimal", "money", "integer", "ratio"}:
        raise RegistryValidationError(
            f"modelo {modelo_id} revision {revision_id} parameter {parameter.id!r} is not a scalar projection",
        )


def _project_variant(
    modelo_id: str,
    revision: ModeloRevision,
    parameter: ParameterDefinition,
    value: DatedValue,
) -> GovernedFactVariant:
    return GovernedFactVariant(
        variant_id=f"m{modelo_id}:{parameter.id}:{value.valid_from.isoformat()}",
        selectors=(
            FactSelector(name="modelo", value=modelo_id),
            FactSelector(name="parameter_id", value=parameter.id),
        ),
        date_axis=value.date_axis,
        valid_from=value.valid_from,
        valid_to=value.valid_to,
        payload=ScalarFactPayload(value=value.value, unit=parameter.unit),
        legal_refs=parameter.legal_refs,
        source_refs=parameter.source_refs,
        source_citations=parameter.source_citations,
        review_status=revision.review_status,
        ownership=FactOwnership.GENERATED,
    )
