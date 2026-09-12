"""Cross-filing fold requirements and values for relation-prefill bindings.

A ``relation_prefill`` binding declares a fold from another modelo's filed
values -- or from an earlier period of this one -- into a slot of the target
filing. This module turns those declarations into the source requirements that
must be satisfied before the target modelo can be calculated, and resolves the
folded values once the source observations are available.

The fold used to be declared by a separate relation family keyed by its own
identifier. It is now the binding's own provider, so the binding id is the key
everywhere: one declaration, one identity, one inheritance rule.

See Also:
    :mod:`cadrumo.domain.calculations.registry.bindings_previous_filing`
        Same requirement record reused by direct previous-filing carries.
    :mod:`cadrumo.domain.calculations.registry.observation_fold`
        Observation fold helpers used to gather source casilla values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind, RelationAggregationOp
from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period, RegistrySelectorPeriodCode
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import unique_tuple
from .binding_temporal import binding_applies_to_period
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, SourceRefId
from .observation_fold import gather_observed_requirement_values
from .relation_dependency import (
    RelationDependencyRole,
    RelationDependencyRoleField,
    RelationDependencyTreatment,
    RelationDependencyTreatmentField,
)
from .relation_prefill_bindings import RelationPrefillProvider
from .schema_base import filing_period_from_scope

if TYPE_CHECKING:
    from .bindings import RegistryModeloObservation
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "RegistryFoldRequirement",
    "relation_prefill_bindings_for_period",
    "relation_requirement_index",
    "relation_source_requirements",
    "resolve_relation_values",
    "resolve_relation_values_from_observations",
    "source_presence_gaps",
]

#: The two folds an observation-backed requirement can perform. A binding may
#: declare any :class:`~core.aggregation.BindingAggregationOp`, but only these
#: two describe folding matched source FILINGS; a row-emitting or counting op
#: on a cross-filing fold is a declaration error rather than a fold this module
#: can perform, so it is refused instead of coerced.
_FOLD_OPS: Mapping[BindingAggregationOp, RelationAggregationOp] = {
    BindingAggregationOp.COPY: RelationAggregationOp.COPY,
    BindingAggregationOp.SUM: RelationAggregationOp.SUM,
}


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

    The single unified requirement record for both fold mechanisms: a
    cross-modelo ``relation_prefill`` fold (``target_bindings`` populated) and
    a same-modelo direct ``previous_filing`` carry (``binding_ids`` populated).
    Both the source-period and source-casilla axes are PLURAL so the record is
    a superset of the two shapes: a relation-prefill requirement fans plural
    ``periods`` against a single ``source_casilla_ids`` member, while a
    ``previous_filing`` requirement carries a single ``periods`` member against
    plural ``source_casilla_ids``. ``legal_refs`` and ``source_refs`` retain the
    originating binding's grounding for operator diagnostics.

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
    target_bindings: tuple[BindingId, ...] = ()
    # Both fold producers resolve these from an already-typed source (the
    # provider's dependency_role, the binding's aggregation op,
    # DependencyClassificationDefinition.treatment); the same-modelo
    # previous_filing producer legitimately has no dependency role or fold op to
    # report, hence the optional shape rather than a magic empty-string
    # sentinel.
    dependency_role: RelationDependencyRoleField | None = None
    dependency_treatment: RelationDependencyTreatmentField | None = None
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
class _FoldRequirementBucket:
    """Collect the bindings and grounding one requirement key accumulates."""

    target_bindings: set[BindingId] = field(default_factory=set)
    legal_refs: set[LegalRefId] = field(default_factory=set)
    source_refs: set[SourceRefId] = field(default_factory=set)


#: Same closed vocabularies as :attr:`RegistryFoldRequirement.dependency_role`
#: and :attr:`RegistryFoldRequirement.dependency_treatment` -- the grouping key
#: below carries the exact values those fields are ultimately built from
#: (:attr:`RelationPrefillProvider.dependency_role`,
#: :attr:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition.treatment`),
#: so it is typed to match rather than widened to a bare ``str``.
type _FoldRequirementKey = tuple[
    str,
    int,
    tuple[str, ...],
    CasillaId,
    RelationDependencyRole,
    RelationDependencyTreatment,
    str,
]


def relation_prefill_bindings_for_period(
    revision: ModeloRevision,
    *,
    period: str | None = None,
) -> tuple[tuple[BindingDefinition, RelationPrefillProvider], ...]:
    """Return this revision's relation-prefill bindings applicable to a period.

    The binding's own ``applicability`` is what scopes it now; the relation's
    ``target_periods`` moved there in the same change that folded the relation
    into the provider, so period scoping has one home rather than two.
    """
    return tuple(
        (binding, binding.provider)
        for binding in revision.bindings
        if binding.source is BindingSourceKind.RELATION_PREFILL
        and isinstance(binding.provider, RelationPrefillProvider)
        and binding_applies_to_period(binding.applicability, period)
    )


def _fold_op(binding: BindingDefinition) -> RelationAggregationOp:
    """Return the observation-fold op a relation-prefill binding declares."""
    declared = binding_aggregation_op(binding)
    fold = _FOLD_OPS.get(declared)
    if fold is None:
        raise RegistryValidationError(
            f"relation_prefill binding {binding.id!r} declares aggregation op {declared.value!r}, "
            "which does not fold matched source filings",
            context={"binding_id": str(binding.id), "op": declared.value},
        )
    return fold


def relation_requirement_index(
    requirements: Iterable[RegistryFoldRequirement],
) -> dict[BindingId, RegistryFoldRequirement]:
    """Index canonical fold requirements by every target binding they satisfy.

    ``relation_source_requirements`` deliberately coalesces source filings that
    satisfy more than one binding. Consumers nevertheless need a direct
    binding-id lookup to project the one requirement's source identity,
    treatment, and grounding. Keeping that fan-out here means every consumer
    gets the same requirement object instead of reconstructing partial metadata
    with a local comprehension.
    """
    return {binding_id: requirement for requirement in requirements for binding_id in requirement.target_bindings}


def relation_source_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return requirement records needed to resolve relation prefills for a filing.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation-prefill bindings to inspect.
        filing_year: Target filing year; combined with each provider's temporal
            member to derive the expected source-modelo filing year.
        period: Target period token; filters bindings by applicability and
            seeds the source-period derivation.

    Returns:
        :class:`~cadrumo.domain.calculations.registry.RegistryFoldRequirement`
        rows keyed by source modelo/year/period and source casilla.
    """
    grouped = _group_fold_requirements(revision, filing_year=filing_year, period=period)
    return tuple(_registry_fold_requirement(key, values) for key, values in sorted(grouped.items()))


def _group_fold_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> dict[_FoldRequirementKey, _FoldRequirementBucket]:
    classifications_by_source = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    grouped: dict[_FoldRequirementKey, _FoldRequirementBucket] = {}
    for binding, provider in relation_prefill_bindings_for_period(revision, period=period):
        classification = classifications_by_source.get(provider.source_modelo)
        if classification is None:
            raise RegistryValidationError(
                f"relation_prefill binding {binding.id!r} source modelo {provider.source_modelo!r} "
                "has no dependency classification",
            )
        for source_year, source_periods in _anchors_by_source_year(provider, filing_year=filing_year, period=period):
            key = (
                provider.source_modelo,
                source_year,
                source_periods,
                _single_source_casilla(binding, provider),
                provider.dependency_role,
                classification.treatment,
                _fold_op(binding).value,
            )
            bucket = grouped.setdefault(key, _FoldRequirementBucket())
            bucket.target_bindings.add(binding.id)
            bucket.legal_refs.update(binding.legal_refs)
            bucket.source_refs.update(binding.source_refs)
    return grouped


def _single_source_casilla(binding: BindingDefinition, provider: RelationPrefillProvider) -> CasillaId:
    """Return the one source casilla a relation-prefill fold reads.

    The fold matches one source casilla per requirement; a provider declaring
    several would silently collapse to the first, so the shape is refused here
    rather than reinterpreted.
    """
    declared = provider.declared_source_casilla_ids
    if len(declared) != 1:
        raise RegistryValidationError(
            f"relation_prefill binding {binding.id!r} must read exactly one source casilla",
            context={"binding_id": str(binding.id), "source_casilla_ids": ",".join(declared)},
        )
    return declared[0]


def _anchors_by_source_year(
    provider: RelationPrefillProvider,
    *,
    filing_year: int,
    period: str,
) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Group the provider's anchors into ``(source year, periods)`` pairs.

    Most temporal members produce anchors sharing one year delta, but the
    period offset can straddle a year boundary, so the grouping is derived
    rather than assumed. An empty result is a scope-out: the member names no
    source window for this target period, and the caller must not substitute
    one.
    """
    by_year: dict[int, list[str]] = {}
    for year_delta, source_period in provider.required_period_anchors_for_target(period):
        periods = by_year.setdefault(filing_year + year_delta, [])
        if source_period not in periods:
            periods.append(source_period)
    return tuple((year, tuple(periods)) for year, periods in sorted(by_year.items()))


def _registry_fold_requirement(
    key: _FoldRequirementKey,
    values: _FoldRequirementBucket,
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
        target_bindings=tuple(sorted(values.target_bindings)),
        dependency_role=dependency_role,
        dependency_treatment=dependency_treatment,
        aggregation_op=RelationAggregationOp(aggregation_op),
        legal_refs=tuple(sorted(values.legal_refs)),
        source_refs=tuple(sorted(values.source_refs)),
    )


def resolve_relation_values(
    revision: ModeloRevision,
    external_outputs: Mapping[BindingId, Decimal | tuple[Decimal, ...]],
    *,
    period: str | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill values from caller-supplied external outputs.

    ``external_outputs`` is keyed by target binding id. ``copy`` folds one
    Decimal through unchanged; ``sum`` adds the tuple of matched per-period
    values.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation-prefill bindings are resolved against the supplied outputs.
        external_outputs: Caller-supplied per-binding values keyed by
            :class:`~cadrumo.domain.calculations.registry.BindingId`; a
            :class:`decimal.Decimal` under ``copy`` aggregation or a tuple of
            Decimals under ``sum``.
        period: Optional period token; restricts active bindings to those whose
            applicability admits it.
    """
    active = relation_prefill_bindings_for_period(revision, period=period)
    binding_ids = {binding.id for binding, _ in active}
    unknown = sorted(set(external_outputs).difference(binding_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation-prefill binding ids: {unknown!r}")
    resolved: dict[BindingId, Decimal] = {}
    for binding, _ in active:
        if binding.id not in external_outputs:
            raise RegistryValidationError(f"missing relation-prefill value for {binding.id!r}")
        raw_value = external_outputs[binding.id]
        if _fold_op(binding) is RelationAggregationOp.COPY:
            if not isinstance(raw_value, Decimal):
                raise RegistryValidationError(f"relation-prefill binding {binding.id!r} copy requires one Decimal")
            resolved[binding.id] = raw_value
        else:
            if not isinstance(raw_value, tuple):
                raise RegistryValidationError(
                    f"relation-prefill binding {binding.id!r} sum requires a tuple of Decimal values",
                )
            resolved[binding.id] = sum(raw_value, Decimal("0"))
    return resolved


def resolve_relation_values_from_observations(
    revision: ModeloRevision,
    observations: Iterable[RegistryModeloObservation],
    *,
    filing_year: int,
    period: str,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill values from normalized filed-declaration observations.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            relation-prefill bindings to resolve.
        observations: Filed-declaration
            :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation`
            rows that supply the source values each fold consumes.
        filing_year: Target filing year; combined with each provider's temporal
            member to match observation rows.
        period: Target period token whose requirements drive observation
            matching.

    Returns:
        Resolved :class:`~cadrumo.domain.calculations.registry.BindingId` values
        suitable for
        :func:`cadrumo.domain.calculations.registry.formula_runtime.calculate_registry_snapshot`.
    """
    available = tuple(observations)
    external_outputs: dict[BindingId, Decimal | tuple[Decimal, ...]] = {}
    for requirement in relation_source_requirements(revision, filing_year=filing_year, period=period):
        values = gather_observed_requirement_values(requirement, available)
        raw_value: Decimal | tuple[Decimal, ...]
        if requirement.aggregation_op == "copy":
            if len(values) != 1:
                raise RegistryValidationError(
                    f"fold requirement {requirement.target_bindings!r} copy aggregation requires one observation",
                )
            raw_value = values[0]
        else:
            raw_value = values
        for binding_id in requirement.target_bindings:
            external_outputs[binding_id] = raw_value
    return resolve_relation_values(revision, external_outputs, period=period)
