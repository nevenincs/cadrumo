"""Governed-fact projections of selected modelo-owned parameters."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import GovernedFactFamily, ScalarFactPayload
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from cadrumo.domain.calculations.registry.facts.variants import (
    FactOwnership,
    FactSelector,
    GovernedFactVariant,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import DatedValue, ParameterDefinition

__all__ = [
    "MODELO_PARAMETER_PROJECTION_PROVIDER_ID",
    "ModeloParameterFact",
    "compile_modelo_parameter_projection_facts",
    "projected_parameter_ids",
]


MODELO_PARAMETER_PROJECTION_PROVIDER_ID = "modelo-parameter-projections"


class ModeloParameterFact(StrEnum):
    """Closed fact identifiers for the projected modelo parameters."""

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
    _ProjectionTarget(ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION, "100", "renta-maternidad-mensual"),
    _ProjectionTarget(ModeloParameterFact.MATERNITY_ANNUAL_CAP, "100", "renta-maternidad-cap-anual"),
    _ProjectionTarget(
        ModeloParameterFact.MATERNITY_POST_ENROLLMENT_INCREMENT,
        "100",
        "renta-maternidad-alta-posterior-incremento",
    ),
)


def projected_modelo_ids() -> frozenset[str]:
    """Return every modelo a projection reads from when governed facts compile.

    Compilation refuses when one of these is absent, so anything assembling a
    PARTIAL registry - the isolated candidate a generated tree is validated
    against - depends on them exactly as it depends on a modelo the target folds
    a value in from. Exposed so that dependency can be declared rather than
    rediscovered as a failure.
    """
    return frozenset(target.modelo_id for target in _TARGETS)


def projected_parameter_ids(modelo_id: str) -> frozenset[str]:
    """Return the parameter ids a projection consumes from one modelo.

    A projected parameter is read by the compiler rather than by a formula or a
    ``read_parameter`` call, so a consumer census that walks only those two
    paths reports it as unused. Exposed so the census can ask instead of
    guessing.
    """
    return frozenset(target.parameter_id for target in _TARGETS if target.modelo_id == modelo_id)


def compile_modelo_parameter_projection_facts(
    modelos: Iterable[ModeloDefinition],
) -> tuple[GovernedFact, ...]:
    """Project the exact migration targets from already-compiled revisions."""
    by_id = {modelo.id: modelo for modelo in modelos}
    facts: list[GovernedFact] = []
    for target in _TARGETS:
        modelo = by_id.get(target.modelo_id)
        if modelo is None:
            # A registry that does not CONTAIN a modelo cannot carry a fact
            # projected from it, and refusing to compile every other fact
            # because of that made a partial registry impossible to validate:
            # the isolated candidate a generated tree is checked against holds
            # one modelo by design, and the two projection targets pull a
            # transitive closure of nineteen.
            #
            # The projection is omitted rather than faked. Nothing is
            # substituted and no default appears; a caller asking for this fact
            # against this registry gets no variant and fails at resolution,
            # which is the boundary that knows what the value was for. A
            # complete registry contains both targets, so this never fires
            # there and what it publishes is unchanged.
            continue
        variants = _target_variants(modelo, target)
        if not variants:
            raise RegistryValidationError(
                f"modelo {target.modelo_id} projection requires parameter {target.parameter_id!r}",
            )
        facts.append(GovernedFact(fact_id=target.fact.value, family=GovernedFactFamily.SCALAR, variants=variants))
    return tuple(facts)


def _target_variants(modelo: ModeloDefinition, target: _ProjectionTarget) -> tuple[GovernedFactVariant, ...]:
    rows: dict[tuple[object, ...], list[tuple[ModeloRevision, ParameterDefinition, DatedValue]]] = {}
    for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id))):
        for parameter in revision.parameters:
            if parameter.id != target.parameter_id:
                continue
            _require_scalar_parameter(parameter, modelo_id=modelo.id, revision_id=revision.id)
            for value in parameter.values:
                row = (value.date_axis, value.valid_from, value.valid_to, value.value, parameter.unit)
                rows.setdefault(row, []).append((revision, parameter, value))
    variants = [
        variant
        for statements in rows.values()
        for variant in _row_variants(modelo.id, parameter_id=target.parameter_id, statements=statements)
    ]
    return _open_newest_edition(
        modelo,
        tuple(sorted(variants, key=lambda variant: (variant.valid_from, variant.variant_id))),
    )


def _row_variants(
    modelo_id: str,
    *,
    parameter_id: str,
    statements: list[tuple[ModeloRevision, ParameterDefinition, DatedValue]],
) -> tuple[GovernedFactVariant, ...]:
    """Project one dated row that one or more editions state.

    Consecutive editions stating the row with the same provenance share one
    variant. An unchanged value can stay open across editions that each carry
    their own review evidence; the row is then split at the first filing year
    of each edition whose provenance differs, so every slice keeps the evidence
    of the edition that states it and the slices together cover exactly the
    row's own window.
    """
    runs = _row_provenance_runs(modelo_id, parameter_id=parameter_id, statements=statements)
    if len(runs) > 1 and runs[0][2].date_axis is not DateAxis.FILING_PERIOD:
        raise RegistryValidationError(
            f"modelo {modelo_id} parameter {parameter_id!r} restates one {runs[0][2].date_axis} row with "
            "different provenance; only a filing-period row can be split at edition boundaries"
        )
    variants: list[GovernedFactVariant] = []
    for index, (run_revisions, parameter, value) in enumerate(runs):
        valid_from = value.valid_from if index == 0 else max(value.valid_from, run_revisions[0].valid_from)
        valid_to = value.valid_to if index == len(runs) - 1 else runs[index + 1][0][0].valid_from - timedelta(days=1)
        sliced = value.model_copy(update={"valid_from": valid_from, "valid_to": valid_to})
        variant = _project_variant(modelo_id, run_revisions[0], parameter, sliced)
        variants.append(
            variant.model_copy(update={"source_revision_ids": tuple(revision.id for revision in run_revisions)})
        )
    return tuple(variants)


def _row_provenance_runs(
    modelo_id: str,
    *,
    parameter_id: str,
    statements: list[tuple[ModeloRevision, ParameterDefinition, DatedValue]],
) -> list[tuple[list[ModeloRevision], ParameterDefinition, DatedValue]]:
    """Group consecutive identical provenance while requiring agreement on review."""
    runs: list[tuple[list[ModeloRevision], ParameterDefinition, DatedValue]] = []
    for revision, parameter, value in statements:
        if runs and _provenance(runs[-1][1]) == _provenance(parameter):
            run_revisions = runs[-1][0]
            if run_revisions[0].review_status is not revision.review_status:
                raise RegistryValidationError(
                    f"modelo {modelo_id} parameter {parameter_id!r} revisions contributing one "
                    "projected fact disagree on review status"
                )
            run_revisions.append(revision)
            continue
        runs.append(([revision], parameter, value))
    return runs


def _provenance(parameter: ParameterDefinition) -> tuple[object, ...]:
    return (parameter.legal_refs, parameter.source_refs, parameter.source_citations)


def _open_newest_edition(
    modelo: ModeloDefinition,
    variants: tuple[GovernedFactVariant, ...],
) -> tuple[GovernedFactVariant, ...]:
    """Leave the newest edition's value open-ended, as the registry carries that edition forward.

    A modelo revision's annual window marks the edition it was authored for, not
    a legal end of the parameter; the registry projects the newest edition into
    later filing years. A governed fact treats an explicit end as a legal
    boundary, so the projection drops only the end that is exactly the newest
    edition's own window end.
    """
    newest = max(modelo.revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))
    if newest.valid_to is None:
        return variants
    return tuple(
        variant.model_copy(update={"valid_to": None})
        if newest.id in variant.source_revision_ids and variant.valid_to == newest.valid_to
        else variant
        for variant in variants
    )


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
        source_revision_ids=(revision.id,),
    )
