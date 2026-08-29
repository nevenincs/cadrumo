"""Relation helpers for cross-model registry dependencies.

Resolves cross-modelo source requirements and materialises relation values
for a :class:`~cadrumo.domain.calculations.registry.ModeloRevision` filing.
Relations declare which source filings and output casillas must be available
before the target modelo can be calculated.

See Also:
    :mod:`cadrumo.domain.calculations.registry.bindings_previous_filing`
        Same requirement record reused by direct previous-filing carries.
    :mod:`cadrumo.domain.calculations.registry.observation_fold`
        Observation fold helpers used to gather source casilla values.
    :mod:`cadrumo.domain.calculations.registry._relation_aggregation`
        Canonical relation aggregation resolver used by this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, CasillaId, Period, RegistrySelectorPeriodCode
from ....core.aggregation import RelationAggregationOp
from ._relation_aggregation import relation_aggregation_op
from .binding_selector_utils import unique_tuple
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, RelationId, SourceRefId
from .observation_fold import gather_observed_requirement_values
from .period_offset_math import apply_period_offset
from .schema import ModeloRevision, filing_period_from_scope
from .schema_surfaces import RelationDefinition

if TYPE_CHECKING:
    from .bindings import RegistryModeloObservation
from ....core.filing_year import FilingYear

__all__ = [
    "RegistryFoldRequirement",
    "derive_offset_source_period",
    "relation_requirement_index",
    "relation_source_requirements",
    "resolve_relation_values",
    "resolve_relation_values_from_observations",
    "source_presence_gaps",
]


def source_presence_gaps(
    *,
    required_source_casilla_ids: Iterable[CasillaId],
    source_presence_groups: Iterable[Iterable[CasillaId]],
    observed_source_casilla_ids: Iterable[CasillaId],
) -> tuple[tuple[CasillaId, ...], tuple[tuple[CasillaId, ...], ...]]:
    """Return missing mandatory casillas and unsatisfied any-of groups.

    This is the single enforcement primitive for registry-derived previous-
    filing source presence. Adapters and application gates consume the same
    result instead of reinterpreting candidate sets independently.
    """
    observed = frozenset(observed_source_casilla_ids)
    missing_required = tuple(sorted(set(required_source_casilla_ids) - observed))
    missing_groups = tuple(tuple(group) for group in source_presence_groups if not set(group) & observed)
    return missing_required, missing_groups


class RegistryFoldRequirement(BaseModel):
    """One source-filing requirement for a cross-filing fold-in.

    The single unified requirement record for both fold-in mechanisms: a
    cross-modelo relation fold (``relation_ids`` / ``target_bindings`` populated)
    and a same-modelo direct ``previous_filing`` carry (``binding_ids``
    populated). Both the source-period and source-casilla axes are PLURAL so the
    record is a superset of the two prior shapes: a relation requirement fans
    plural ``periods`` against a single ``source_casilla_ids`` member, while a
    ``previous_filing`` requirement carries a single ``periods`` member against
    plural ``source_casilla_ids``. ``legal_refs`` and ``source_refs`` retain the
    originating relation/binding grounding for operator diagnostics. Each
    producer emits a single-element tuple where its cardinality is one; no value
    shifts, only the record TYPE unifies.

    Consumed by :func:`relation_source_requirements`,
    :func:`resolve_relation_values_from_observations`, and
    :func:`cadrumo.domain.calculations.registry.previous_filing_observation_requirements`.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    filing_year: FilingYear
    filing_periods: tuple[Period, ...] = ()
    periods: tuple[RegistrySelectorPeriodCode, ...] = Field(min_length=1)
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    required_source_casilla_ids: tuple[CasillaId, ...] | None = None
    source_presence_groups: tuple[tuple[CasillaId, ...], ...] = ()
    binding_ids: tuple[BindingId, ...] = ()
    relation_ids: tuple[RelationId, ...] = ()
    target_bindings: tuple[BindingId, ...] = ()
    # Both fold-in producers already resolve these from an already-typed
    # source (RelationDefinition.dependency_role, a relation's resolved
    # aggregation op, DependencyClassificationDefinition.treatment); the
    # same-modelo previous_filing producer legitimately has no relation or
    # aggregation to report, hence the optional shape rather than a magic
    # empty-string sentinel.
    dependency_role: (
        Literal[
            "periodic_to_annual_summary",
            "instalment_to_final_settlement",
            "direct_calculation",
            "factual_evidence",
        ]
        | None
    ) = None
    dependency_treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"] | None = None
    aggregation_op: RelationAggregationOp | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    _values_unique = field_validator(
        "binding_ids",
        "source_casilla_ids",
        "legal_refs",
        "source_refs",
    )(unique_tuple("fold requirement tuple"))

    @field_validator("required_source_casilla_ids")
    @classmethod
    def _required_source_casillas_unique(
        cls,
        value: tuple[CasillaId, ...] | None,
    ) -> tuple[CasillaId, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("fold requirement required source casilla entries must be unique")
        return value

    @model_validator(mode="after")
    def _required_sources_are_candidates(self) -> Self:
        if self.required_source_casilla_ids is not None and not set(self.required_source_casilla_ids) <= set(
            self.source_casilla_ids
        ):
            raise RegistryValidationError("fold requirement required source casillas must be candidate source casillas")
        candidate_ids = set(self.source_casilla_ids)
        for group in self.source_presence_groups:
            if not group:
                raise RegistryValidationError("fold requirement source presence groups must not be empty")
            if not set(group) <= candidate_ids:
                raise RegistryValidationError("fold requirement source presence groups must contain candidate casillas")
        return self

    @property
    def enforced_source_casilla_ids(self) -> tuple[CasillaId, ...]:
        """Return the registry-declared mandatory subset, defaulting to every candidate."""
        if self.required_source_casilla_ids is None:
            return self.source_casilla_ids
        return self.required_source_casilla_ids


@dataclass(slots=True)
class _RelationRequirementBucket:
    relation_ids: set[RelationId]
    target_bindings: set[BindingId]
    legal_refs: set[LegalRefId]
    source_refs: set[SourceRefId]


#: Same closed vocabularies as :attr:`RegistryFoldRequirement.dependency_role`
#: and :attr:`RegistryFoldRequirement.dependency_treatment` -- the grouping key
#: below carries the exact values those fields are ultimately built from
#: (:attr:`RelationDefinition.dependency_role`,
#: :attr:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition.treatment`),
#: so it is typed to match rather than widened to a bare ``str``.
type _RelationRequirementDependencyRole = Literal[
    "periodic_to_annual_summary",
    "instalment_to_final_settlement",
    "direct_calculation",
    "factual_evidence",
]
type _RelationRequirementDependencyTreatment = Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
type _RelationRequirementKey = tuple[
    str,
    int,
    tuple[str, ...],
    CasillaId,
    _RelationRequirementDependencyRole,
    _RelationRequirementDependencyTreatment,
    str,
]


def relation_requirement_index(
    requirements: Iterable[RegistryFoldRequirement],
) -> dict[RelationId, RegistryFoldRequirement]:
    """Index canonical fold requirements by every relation they satisfy.

    ``relation_source_requirements`` deliberately coalesces source filings that
    satisfy more than one relation. Consumers nevertheless need a direct
    relation-id lookup to project the one requirement's source identity,
    treatment, and grounding. Keeping that fan-out here means every consumer
    gets the same requirement object instead of reconstructing partial metadata
    with a local comprehension.

    The requirement producer sorts its rows deterministically, and this retains
    its established last-row-wins behavior for an invalid duplicate relation id
    until the registry validator reports that structural fault.
    """
    return {relation_id: requirement for requirement in requirements for relation_id in requirement.relation_ids}


def relation_source_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return requirement records needed to resolve relations for a filing.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation declarations to inspect.
        filing_year: Target filing year; combined with each relation's source
            offset to derive the expected source-modelo filing year.
        period: Target period token; filters relations by ``target_periods``
            and seeds the source-period derivation.

    Returns:
        :class:`~cadrumo.domain.calculations.registry.RegistryFoldRequirement`
        rows keyed by source modelo/year/period and source casilla.
    """
    grouped = _group_relation_requirements(revision, filing_year=filing_year, period=period)
    return tuple(_registry_fold_requirement(key, values) for key, values in sorted(grouped.items()))


def _group_relation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> dict[_RelationRequirementKey, _RelationRequirementBucket]:
    classifications_by_source = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    grouped: dict[_RelationRequirementKey, _RelationRequirementBucket] = {}
    for relation in revision.relations:
        if relation.target_periods and period not in relation.target_periods:
            continue
        classification = classifications_by_source.get(relation.source_modelo)
        if classification is None:
            raise RegistryValidationError(
                f"relation {relation.id!r} source modelo {relation.source_modelo!r} has no dependency classification",
            )
        source_year, source_periods = _relation_requirement_source_scope(
            relation,
            filing_year=filing_year,
            period=period,
        )
        if source_year is None:
            continue
        key = (
            relation.source_modelo,
            source_year,
            tuple(source_periods),
            relation.source_casilla_id,
            relation.dependency_role,
            classification.treatment,
            relation_aggregation_op(relation).value,
        )
        bucket = grouped.setdefault(
            key,
            _RelationRequirementBucket(
                relation_ids=set(),
                target_bindings=set(),
                legal_refs=set(),
                source_refs=set(),
            ),
        )
        bucket.relation_ids.add(relation.id)
        bucket.target_bindings.add(relation.target_binding)
        bucket.legal_refs.update(relation.legal_refs)
        bucket.source_refs.update(relation.source_refs)
    return grouped


def _relation_requirement_source_scope(
    relation: RelationDefinition,
    *,
    filing_year: int,
    period: str,
) -> tuple[int | None, tuple[str, ...]]:
    if relation.source_period_offset_from_target is not None:
        derived = _derive_offset_source_anchor(relation, target_period=period)
        if derived is None:
            return None, ()
        period_year_delta, source_period = derived
        return _relation_source_year(relation, filing_year=filing_year) + period_year_delta, (source_period,)
    return _relation_source_year(relation, filing_year=filing_year), relation.source_periods or (period,)


def _registry_fold_requirement(
    key: _RelationRequirementKey,
    values: _RelationRequirementBucket,
) -> RegistryFoldRequirement:
    (
        source_modelo,
        source_year,
        source_periods,
        source_casilla_id,
        dependency_role,
        dependency_treatment,
        aggregation_op,
    ) = key
    return RegistryFoldRequirement(
        source_modelo=source_modelo,
        filing_year=source_year,
        filing_periods=tuple(
            filing_period
            for source_period in source_periods
            if (filing_period := filing_period_from_scope(source_year, source_period)) is not None
        ),
        periods=source_periods,
        source_casilla_ids=(source_casilla_id,),
        relation_ids=tuple(sorted(values.relation_ids)),
        target_bindings=tuple(sorted(values.target_bindings)),
        dependency_role=dependency_role,
        dependency_treatment=dependency_treatment,
        aggregation_op=RelationAggregationOp(aggregation_op),
        legal_refs=tuple(sorted(values.legal_refs)),
        source_refs=tuple(sorted(values.source_refs)),
    )


def resolve_relation_values(
    revision: ModeloRevision,
    external_outputs: Mapping[RelationId, Decimal | tuple[Decimal, ...]],
    *,
    period: str | None = None,
) -> dict[RelationId, Decimal]:
    """Resolve typed relation values from caller-supplied external outputs.

    ``external_outputs`` is keyed by relation id. Aggregation defaults to copy;
    ``{"op": "sum"}`` sums tuple values for annual summaries.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation definitions are resolved against the supplied external
            outputs.
        external_outputs: Caller-supplied per-relation values keyed by
            :class:`~cadrumo.domain.calculations.registry.RelationId`; a
            :class:`decimal.Decimal` under ``copy`` aggregation or a tuple of
            Decimals under ``sum``.
        period: Optional period token; restricts active relations to those
            whose ``target_periods`` set contains it.
    """
    relations = tuple(_active_relations(revision, period=period))
    relation_ids = {relation.id for relation in relations}
    unknown = sorted(set(external_outputs).difference(relation_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation ids: {unknown!r}")
    resolved: dict[RelationId, Decimal] = {}
    for relation in relations:
        if relation.id not in external_outputs:
            raise RegistryValidationError(f"missing relation value for {relation.id!r}")
        raw_value = external_outputs[relation.id]
        op = relation_aggregation_op(relation)
        if op == RelationAggregationOp.COPY:
            if not isinstance(raw_value, Decimal):
                raise RegistryValidationError(f"relation {relation.id!r} copy requires one Decimal")
            resolved[relation.id] = raw_value
        else:
            if not isinstance(raw_value, tuple):
                raise RegistryValidationError(f"relation {relation.id!r} sum requires a tuple of Decimal values")
            resolved[relation.id] = sum(raw_value, Decimal("0"))
    return resolved


def resolve_relation_values_from_observations(
    revision: ModeloRevision,
    observations: Iterable[RegistryModeloObservation],
    *,
    filing_year: int,
    period: str,
) -> dict[RelationId, Decimal]:
    """Resolve relation values from normalized filed-declaration observations.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation declarations to resolve.
        observations: Filed-declaration
            :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation`
            rows that supply the source values each relation consumes.
        filing_year: Target filing year; combined with each relation's source
            offset to match observation rows.
        period: Target period token whose relation requirements drive
            observation matching.

    Returns:
        Resolved :class:`~cadrumo.domain.calculations.registry.RelationId` values
        suitable for
        :func:`cadrumo.domain.calculations.registry.formula_runtime.calculate_registry_snapshot`.
    """
    available = tuple(observations)
    external_outputs: dict[RelationId, Decimal | tuple[Decimal, ...]] = {}
    for requirement in relation_source_requirements(revision, filing_year=filing_year, period=period):
        values = gather_observed_requirement_values(requirement, available)
        raw_value: Decimal | tuple[Decimal, ...]
        if requirement.aggregation_op == "copy":
            if len(values) != 1:
                raise RegistryValidationError(
                    f"relation requirement {requirement.relation_ids!r} copy aggregation requires one observation",
                )
            raw_value = values[0]
        else:
            raw_value = values
        for relation_id in requirement.relation_ids:
            external_outputs[relation_id] = raw_value
    return resolve_relation_values(revision, external_outputs, period=period)


def materialize_relation_binding_values(
    revision: ModeloRevision,
    relation_values: Mapping[RelationId, Decimal],
    *,
    period: str | None = None,
) -> dict[BindingId, Decimal]:
    """Copy resolved relation values into their declared target bindings.

    Relation ids remain the canonical formula-runtime keys. This helper is an
    additive bridge for registry rows that also declare ``target_binding`` so
    bound casillas can consume a relation-backed value without duplicating
    relation resolution in the application layer.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation-to-binding mappings are used to populate the returned dict.
        relation_values: Already-resolved relation id to Decimal mapping.
        period: Optional period token; restricts active relations to those
            whose ``target_periods`` set contains it.

    Returns:
        Target :class:`~cadrumo.domain.calculations.registry.BindingId` values for
        relation-backed bound casillas.
    """
    values: dict[BindingId, Decimal] = {}
    for relation in _active_relations(revision, period=period):
        if relation.id not in relation_values:
            continue
        value = relation_values[relation.id]
        existing = values.get(relation.target_binding)
        if existing is not None and existing != value:
            raise RegistryValidationError(
                f"target binding {relation.target_binding!r} receives conflicting relation values",
            )
        values[relation.target_binding] = value
    return values


def _active_relations(revision: ModeloRevision, *, period: str | None) -> tuple[RelationDefinition, ...]:
    if period is None:
        return revision.relations
    return tuple(
        relation for relation in revision.relations if not relation.target_periods or period in relation.target_periods
    )


def _relation_source_year(relation: RelationDefinition, *, filing_year: int) -> int:
    selector = relation.source_revision_selector
    if selector.year is not None:
        return selector.year
    return filing_year + (selector.filing_year_delta or 0)


def derive_offset_source_period(relation: RelationDefinition, *, target_period: str) -> str | None:
    """Return the source period selected by a relation's period offset."""
    anchor = _derive_offset_source_anchor(relation, target_period=target_period)
    return None if anchor is None else anchor[1]


def _derive_offset_source_anchor(relation: RelationDefinition, *, target_period: str) -> tuple[int, str] | None:
    """Apply ``source_period_offset_from_target`` to a target period code.

    Supports quarterly period codes (``1T``..``4T``), pago-fraccionado period
    codes used by modelo 202 (``1P``..``3P``), and zero-padded monthly codes
    (``01``..``12``). Delegates arithmetic to
    :func:`_period_offset_math.apply_period_offset`.
    """
    offset = relation.source_period_offset_from_target
    if offset is None:
        return None
    try:
        return apply_period_offset(offset, target_period=target_period)
    except RegistryValidationError as exc:
        raise RegistryValidationError(
            f"relation {relation.id!r} source_period_offset_from_target "
            f"cannot interpret target period {target_period!r}",
        ) from exc
