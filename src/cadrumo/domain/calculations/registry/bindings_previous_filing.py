"""Previous-filing binding selectors, requirements, and resolvers.

The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
``previous_filing``
:class:`~cadrumo.domain.calculations.registry.BindingDefinition`
declarations; this module turns those selectors into
:class:`~cadrumo.domain.calculations.registry.RegistryFoldRequirement` source
requirements and resolved
:class:`~cadrumo.domain.calculations.registry.BindingId` values.

See Also:
    :mod:`cadrumo.domain.calculations.registry.bindings`
        Public import surface that re-exports these previous-filing helpers.
    :mod:`cadrumo.domain.calculations.registry.relations`
        Relation-fold sibling that materialises cross-modelo source values.
    :mod:`cadrumo.domain.calculations.registry.observation_fold`
        Shared fold helpers for observed casilla values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from pydantic import BaseModel, field_validator, model_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .binding_temporal import (
    BindingTemporalSelector,
    FiledCurrentPeriod,
    FilingYearOffset,
    FilingYearOffsetByTargetPeriod,
    PriorQuarterExpandingSpan,
    SameFilingYearPeriods,
    SameTargetContext,
    TargetPeriodOffset,
    temporal_max_year_delta,
    temporal_period_anchors,
)
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, SourceRefId
from .observation_fold import fold_sum_or_copy
from .relation_dependency import (
    RelationDependencyTreatmentField,
)
from .relations import RegistryFoldRequirement
from .schema_base import filing_period_from_scope

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision


class _RegistryModeloObservationLike(Protocol):
    """Structural observation protocol consumed by previous-filing folds."""

    modelo: ModeloId
    filing_year: int
    period: str

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]: ...


@dataclass(frozen=True, slots=True)
class PreviousFilingSourceReference:
    """Canonical source reference extracted from a typed previous-filing selector.

    The reference names the source
    :class:`~cadrumo.domain.calculations.registry.ModeloId`, required periods, and
    source :class:`~cadrumo.core.CasillaId` values declared
    by one previous-filing binding selector.

    ``filing_year_delta`` and ``max_year_delta`` ride along so a build-time
    year-coverage check can derive the exact source-year interval a selector
    requires without re-parsing the selector a second time.

    ``has_variable_year_offset`` is ``True`` for a provider whose temporal
    member is the expanding span or a period offset: both produce PER-ANCHOR
    year deltas (:meth:`PreviousFilingProvider.required_period_anchors_for_target`
    returns several ``(period_year_delta, period)`` pairs, each with its own
    offset) rather than the single uniform offset a coverage check keyed on one
    interval can represent.
    """

    source_modelo: ModeloId
    required_periods: tuple[str, ...]
    source_casilla_ids: tuple[CasillaId, ...]
    filing_year_delta: int = 0
    max_year_delta: int | None = None
    has_variable_year_offset: bool = False


_PreviousFilingRequirementKey = tuple[ModeloId, int, str]


@dataclass(slots=True)
class _PreviousFilingRequirementAccumulator:
    """Collect one requirement's keyed evidence before materialisation."""

    binding_ids_by_key: dict[_PreviousFilingRequirementKey, set[BindingId]] = field(default_factory=dict)
    source_casilla_ids_by_key: dict[_PreviousFilingRequirementKey, set[CasillaId]] = field(default_factory=dict)
    required_source_casilla_ids_by_key: dict[
        _PreviousFilingRequirementKey,
        set[CasillaId],
    ] = field(default_factory=dict)
    source_presence_groups_by_key: dict[
        _PreviousFilingRequirementKey,
        set[tuple[CasillaId, ...]],
    ] = field(default_factory=dict)
    legal_refs_by_key: dict[_PreviousFilingRequirementKey, set[LegalRefId]] = field(default_factory=dict)
    source_refs_by_key: dict[_PreviousFilingRequirementKey, set[SourceRefId]] = field(default_factory=dict)
    dependency_treatment_by_key: dict[
        _PreviousFilingRequirementKey,
        RelationDependencyTreatmentField | None,
    ] = field(default_factory=dict)


def previous_filing_source_reference(binding: BindingDefinition) -> PreviousFilingSourceReference:
    """Return the :class:`PreviousFilingSourceReference` for a ``previous_filing`` binding.

    The supplied
    :class:`~cadrumo.domain.calculations.registry.BindingDefinition` is parsed
    through the same selector model used by
    :func:`previous_filing_observation_requirements`.
    """
    selector = _previous_filing_selector(binding)
    return PreviousFilingSourceReference(
        source_modelo=selector.source_modelo,
        required_periods=selector.required_periods,
        source_casilla_ids=_previous_filing_source_ids(selector),
        filing_year_delta=selector.uniform_filing_year_delta,
        max_year_delta=selector.max_year_delta,
        has_variable_year_offset=selector.has_variable_year_offset,
    )


def _direct_previous_filing_selectors(
    revision: ModeloRevision,
) -> Iterable[tuple[BindingDefinition, PreviousFilingProvider]]:
    """Yield typed selectors for direct previous-filing bindings in revision order."""
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        if not is_direct_previous_filing_binding(binding):
            continue
        yield binding, _previous_filing_selector(binding)


def _record_previous_filing_requirement(
    accumulator: _PreviousFilingRequirementAccumulator,
    binding: BindingDefinition,
    selector: PreviousFilingProvider,
    *,
    filing_year: int,
    period_year_delta: int,
    required_period: str,
    dependency_treatments_by_source: Mapping[ModeloId, RelationDependencyTreatmentField],
) -> None:
    """Record one selector anchor and all of its registry provenance."""
    expected_year = filing_year + period_year_delta
    key = (selector.source_modelo, expected_year, required_period)
    source_ids = _previous_filing_source_ids(selector)
    accumulator.binding_ids_by_key.setdefault(key, set()).add(binding.id)
    accumulator.source_casilla_ids_by_key.setdefault(key, set()).update(source_ids)
    required_ids = source_ids if selector.required_source_casilla_ids is None else selector.required_source_casilla_ids
    accumulator.required_source_casilla_ids_by_key.setdefault(key, set()).update(required_ids)
    if selector.required_source_casilla_ids == ():
        accumulator.source_presence_groups_by_key.setdefault(key, set()).add(source_ids)
    accumulator.legal_refs_by_key.setdefault(key, set()).update(binding.legal_refs)
    accumulator.source_refs_by_key.setdefault(key, set()).update(binding.source_refs)
    accumulator.dependency_treatment_by_key[key] = dependency_treatments_by_source.get(selector.source_modelo)


def _materialise_previous_filing_requirement(
    key: _PreviousFilingRequirementKey,
    accumulator: _PreviousFilingRequirementAccumulator,
) -> RegistryFoldRequirement:
    """Build one deterministic fold requirement from the keyed accumulator."""
    modelo, expected_year, required_period = key
    return RegistryFoldRequirement(
        source_modelo=modelo,
        filing_periods=tuple(
            filing_period
            for filing_period in (filing_period_from_scope(expected_year, required_period),)
            if filing_period is not None
        ),
        filing_year=expected_year,
        periods=(required_period,),
        binding_ids=tuple(sorted(accumulator.binding_ids_by_key[key])),
        source_casilla_ids=tuple(sorted(accumulator.source_casilla_ids_by_key[key])),
        required_source_casilla_ids=tuple(sorted(accumulator.required_source_casilla_ids_by_key[key])),
        source_presence_groups=tuple(sorted(accumulator.source_presence_groups_by_key.get(key, set()))),
        dependency_treatment=accumulator.dependency_treatment_by_key[key],
        legal_refs=tuple(sorted(accumulator.legal_refs_by_key[key])),
        source_refs=tuple(sorted(accumulator.source_refs_by_key[key])),
    )


def previous_filing_observation_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return source requirements needed by direct previous-filing bindings.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` is scanned
    for direct ``previous_filing`` bindings, and each selector becomes a
    :class:`~cadrumo.domain.calculations.registry.RegistryFoldRequirement` naming
    source modelo/year/period, :class:`~cadrumo.domain.calculations.registry.BindingId`
    consumers, and source casilla ids.
    """
    accumulator = _PreviousFilingRequirementAccumulator()
    # Same closed vocabulary as
    # :attr:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition.treatment`
    # and :attr:`RegistryFoldRequirement.dependency_treatment`, which this
    # value ultimately feeds -- typed to match rather than widened to `str`.
    dependency_treatments_by_source = {
        classification.source_modelo: classification.treatment for classification in revision.dependency_classifications
    }
    for binding, selector in _direct_previous_filing_selectors(revision):
        for period_year_delta, required_period in selector.required_period_anchors_for_target(period):
            _record_previous_filing_requirement(
                accumulator,
                binding,
                selector,
                filing_year=filing_year,
                period_year_delta=period_year_delta,
                required_period=required_period,
                dependency_treatments_by_source=dependency_treatments_by_source,
            )
    return tuple(
        _materialise_previous_filing_requirement(key, accumulator) for key in sorted(accumulator.binding_ids_by_key)
    )


def _observed_casilla_values(
    binding: BindingDefinition,
    selector: PreviousFilingProvider,
    match: _RegistryModeloObservationLike,
    expected_year: int,
    required_period: str,
) -> list[Decimal]:
    source_ids = _previous_filing_source_ids(selector)
    required_ids = (
        frozenset(source_ids)
        if selector.required_source_casilla_ids is None
        else frozenset(selector.required_source_casilla_ids)
    )
    values: list[Decimal] = []
    observed_count = 0
    for casilla_id in source_ids:
        casilla_value = match.casilla_values.get(casilla_id)
        if casilla_value is None:
            if casilla_id in required_ids:
                raise RegistryValidationError(
                    f"binding {binding.id!r} requires observed casilla {casilla_id!r} "
                    f"from {selector.source_modelo!r}/{expected_year}/{required_period!r}",
                )
            values.append(Decimal("0"))
            continue
        observed_count += 1
        values.append(casilla_value)
    if source_ids and observed_count == 0:
        raise RegistryValidationError(
            f"binding {binding.id!r} requires at least one observed source casilla "
            f"from {selector.source_modelo!r}/{expected_year}/{required_period!r}",
        )
    return values


class _PreviousFilingObservationAbsentError(Exception):
    """Internal signal: the required source filing was simply never observed.

    Raised by :func:`_resolve_anchor_values` for the ZERO-MATCH case only,
    and deliberately NOT a :class:`RegistryValidationError` subclass, so it
    can never be caught by a broad ``except RegistryValidationError`` /
    ``except CoreValidationError`` elsewhere in the tree — the raise site's
    OTHER two conditions (an ambiguous multiple-match, or a matched filing
    missing a required source casilla) are structural defects and must keep
    raising :class:`RegistryValidationError` unchanged. Absence is not a
    validation failure: AEAT has simply never seen this filing yet, which is
    exactly the SAME condition the sibling relation-fold channel resolves to
    an unsatisfied slot rather than a refusal. Caught immediately by
    :func:`_resolve_binding_values`, which resolves the whole binding to
    ``None`` (unsatisfied — the caller's existing "nothing to add" shape)
    rather than letting the raise propagate.
    """

    __bare_base_rationale__: ClassVar[str] = (
        "A private control-flow signal, never an operator-facing failure: it is "
        "raised and caught inside this module and resolves the binding to "
        "unsatisfied. Binding it to the error registry would give an outcome no "
        "operator can observe a code and a locale key, and deriving it from "
        "CadrumoError would make a broad domain-error except swallow it — the "
        "exact confusion with the sibling structural defects this class exists "
        "to keep separate."
    )


def _resolve_anchor_values(
    binding: BindingDefinition,
    selector: PreviousFilingProvider,
    available: tuple[_RegistryModeloObservationLike, ...],
    *,
    expected_year: int,
    required_period: str,
) -> list[Decimal]:
    matches = tuple(
        observation
        for observation in available
        if observation.modelo == selector.source_modelo
        and observation.filing_year == expected_year
        and observation.period == required_period
    )
    if selector.grouping == "per_grupo_member":
        if not matches:
            raise _PreviousFilingObservationAbsentError(
                f"binding {binding.id!r} (per_grupo_member) has no observed filing "
                f"{selector.source_modelo!r}/{expected_year}/{required_period!r}",
            )
        values: list[Decimal] = []
        for member_match in matches:
            values.extend(_observed_casilla_values(binding, selector, member_match, expected_year, required_period))
        return values
    if not matches:
        raise _PreviousFilingObservationAbsentError(
            f"binding {binding.id!r} has no observed filing "
            f"{selector.source_modelo!r}/{expected_year}/{required_period!r}",
        )
    if len(matches) > 1:
        raise RegistryValidationError(
            f"binding {binding.id!r} expected one observed filing "
            f"{selector.source_modelo!r}/{expected_year}/{required_period!r}, found {len(matches)}",
        )
    single_match = next(iter(matches))
    return _observed_casilla_values(binding, selector, single_match, expected_year, required_period)


def _resolve_binding_values(
    binding: BindingDefinition,
    available: tuple[_RegistryModeloObservationLike, ...],
    *,
    filing_year: int,
    period: str,
    activity_start_date: date | None = None,
) -> list[Decimal] | None:
    selector = _previous_filing_selector(binding)
    required_anchors = selector.required_period_anchors_for_target(period)
    if not required_anchors:
        return None
    values: list[Decimal] = []
    scoped_pre_activity = False
    for period_year_delta, required_period in required_anchors:
        expected_year = filing_year + period_year_delta
        if _anchor_strictly_before_activity_start(
            expected_year,
            required_period,
            activity_start_date=activity_start_date,
        ):
            scoped_pre_activity = True
            continue
        try:
            values.extend(
                _resolve_anchor_values(
                    binding,
                    selector,
                    available,
                    expected_year=expected_year,
                    required_period=required_period,
                ),
            )
        except _PreviousFilingObservationAbsentError:
            # The whole binding resolves to unsatisfied rather than a partial
            # (and therefore wrong) value from the anchors that DID resolve.
            # A malformed binding (RegistryValidationError, not caught here)
            # still propagates unchanged.
            return None
    if not values and scoped_pre_activity:
        return _zero_values_for_scoped_out_binding(selector)
    return values


def resolve_previous_filing_binding_values(
    revision: ModeloRevision,
    observations: Iterable[_RegistryModeloObservationLike],
    *,
    filing_year: int,
    period: str,
    activity_start_date: date | None = None,
    excluded_binding_ids: frozenset[BindingId] | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve direct previous-filing bindings from observed filed declarations.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies the
    binding selectors and aggregation operators; ``observations`` supply the
    filed casilla values they fold. The returned mapping is keyed by
    :class:`~cadrumo.domain.calculations.registry.BindingId` and carries resolved
    :class:`decimal.Decimal` values for formula runtime consumption.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    excluded = excluded_binding_ids or frozenset()
    for binding in revision.bindings:
        if binding.id in excluded:
            continue
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        if not is_direct_previous_filing_binding(binding):
            continue
        values = _resolve_binding_values(
            binding,
            available,
            filing_year=filing_year,
            period=period,
            activity_start_date=activity_start_date,
        )
        if values is None:
            continue
        resolved[binding.id] = _aggregate_previous_filing_binding(
            binding,
            values,
            source_casilla_ids=_previous_filing_source_ids(_previous_filing_selector(binding)),
        )
    return resolved


def _anchor_strictly_before_activity_start(
    expected_year: int,
    required_period: str,
    *,
    activity_start_date: date | None,
) -> bool:
    """Return whether a source period ended before the taxpayer's activity started."""
    if activity_start_date is None:
        return False
    filing_period = filing_period_from_scope(expected_year, required_period)
    if filing_period is None or not filing_period.has_date_span():
        return False
    return filing_period.end_date < activity_start_date


def _zero_values_for_scoped_out_binding(selector: PreviousFilingProvider) -> list[Decimal]:
    """Return a neutral zero vector matching the binding's source-casilla shape."""
    return [Decimal("0")] * max(1, len(_previous_filing_source_ids(selector)))


class PreviousFilingProvider(BaseModel):
    """Typed provider model for a ``previous_filing`` binding declaration.

    The source coordinate is split in two: ``source_modelo`` plus the source
    casilla ids name WHICH filed values are read, and :attr:`temporal` names
    WHEN they were filed, relative to the target filing context. The temporal
    axis is the shared closed union, so the six mutually exclusive period
    fields this model used to carry -- and the hand-written validators that
    policed their legal combinations -- are replaced by members that cannot
    express an illegal combination at all.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PREVIOUS_FILING] = BindingSourceKind.PREVIOUS_FILING

    source_modelo: ModeloId
    temporal: BindingTemporalSelector
    source_casilla_ids: tuple[CasillaId, ...] = ()
    source_casilla_id: CasillaId | None = None
    required_source_casilla_ids: tuple[CasillaId, ...] | None = None
    grouping: Literal["per_grupo_member"] | None = None

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing source_casilla_ids entries must be unique")
        return value

    @field_validator("required_source_casilla_ids")
    @classmethod
    def _required_source_casilla_ids_unique(
        cls,
        value: tuple[CasillaId, ...] | None,
    ) -> tuple[CasillaId, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("previous-filing required_source_casilla_ids entries must be unique")
        return value

    @property
    def required_periods(self) -> tuple[str, ...]:
        """Return the source periods the temporal member names, if any.

        ``same_target_context``, the period offset, and the expanding span name
        no fixed period set: their periods depend on the target period and are
        produced by :meth:`required_period_anchors_for_target` instead.
        """
        if isinstance(self.temporal, SameFilingYearPeriods | FilingYearOffset | FilingYearOffsetByTargetPeriod):
            return self.temporal.source_periods
        return ()

    @property
    def uniform_filing_year_delta(self) -> int:
        """Return the single year offset every anchor shares, or zero.

        Only :class:`FilingYearOffset` states one uniform offset. The period
        offset and the expanding span carry a per-anchor year delta instead,
        which is why :attr:`has_variable_year_offset` exists.
        """
        return self.temporal.years if isinstance(self.temporal, FilingYearOffset) else 0

    @property
    def has_variable_year_offset(self) -> bool:
        """Whether the anchors carry per-anchor year deltas rather than one offset."""
        return isinstance(
            self.temporal,
            TargetPeriodOffset | PriorQuarterExpandingSpan | FilingYearOffsetByTargetPeriod,
        )

    @property
    def max_year_delta(self) -> int | None:
        """Return the absolute bound on anchor year deltas the member declares."""
        return temporal_max_year_delta(self.temporal)

    def required_period_anchors_for_target(self, target_period: str) -> tuple[tuple[int, str], ...]:
        """Return source year-offset and period anchors for a target period.

        Each year offset is the TOTAL distance from the target filing year, so
        a caller derives the source year as ``filing_year + year_delta`` and
        never adds :attr:`uniform_filing_year_delta` a second time.
        """
        return temporal_period_anchors(self.temporal, target_period=target_period)

    @model_validator(mode="after")
    def _validate_temporal_shape(self) -> PreviousFilingProvider:
        """Refuse a temporal member that names no source window for the declared casillas."""
        if isinstance(self.temporal, SameTargetContext) and self.grouping != "per_grupo_member":
            raise RegistryValidationError(
                "previous-filing same_target_context reads the target's own period and is only "
                "meaningful for the per_grupo_member fold; name the source window explicitly",
            )
        if isinstance(self.temporal, FiledCurrentPeriod):
            raise RegistryValidationError(
                "previous-filing cannot read a filed_current_period; that member belongs to the "
                "same-year annual-summary providers",
            )
        return self

    @model_validator(mode="after")
    def _validate_source_spec(self) -> PreviousFilingProvider:
        if self.source_casilla_ids and self.source_casilla_id is not None:
            raise RegistryValidationError(
                "previous-filing selector cannot declare both source_casilla_ids and source_casilla_id",
            )
        if self.required_source_casilla_ids is not None:
            source_ids = frozenset(_previous_filing_source_ids(self))
            required_ids = frozenset(self.required_source_casilla_ids)
            if not source_ids:
                raise RegistryValidationError(
                    "previous-filing required_source_casilla_ids requires declared source casillas",
                )
            if not required_ids <= source_ids:
                outside = sorted(required_ids - source_ids)
                raise RegistryValidationError(
                    "previous-filing required_source_casilla_ids must be a subset of source casillas "
                    f"(outside: {outside})",
                )
        return self


def _previous_filing_selector(binding: BindingDefinition) -> PreviousFilingProvider:
    selector = _selector_as_dict(binding)
    try:
        return PreviousFilingProvider.model_validate(selector)
    except ValueError as exc:
        hint = ""
        if "source_casillas" in selector:
            hint = "; use source_casilla_ids, not source_casillas"
        elif "source_output" in selector:
            hint = "; use source_casilla_id, not source_output"
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed previous-filing selector: {exc}{hint}",
        ) from exc


_PREVIOUS_FILING_OPS: frozenset[BindingAggregationOp] = frozenset(
    {
        BindingAggregationOp.SUM,
        BindingAggregationOp.COPY,
        BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS,
    },
)


def _validate_previous_filing_invariants(binding: BindingDefinition) -> None:
    """Lift the resolve-time previous-filing op/source invariants to build time.

    A previous_filing binding aggregates one or more source casillas under one of
    the supported ops. The op must be a member of :data:`_PREVIOUS_FILING_OPS`
    (the same closed set :func:`_aggregate_previous_filing_binding` accepts at
    resolve time); ``copy`` requires exactly one source casilla and
    ``prior_pagos_fraccionados`` requires exactly two (per quarter pair). These
    are determinable from the selector at build time, so a malformed pairing
    fails at snapshot construction rather than only on a taxpayer calculation.

    Only direct previous_filing bindings carry a source-casilla shape; a
    relation-targeted previous_filing slot is short-circuited (its value is
    produced by relation resolution, not this aggregator).
    """
    op = binding_aggregation_op(binding)
    if op not in _PREVIOUS_FILING_OPS:
        raise RegistryValidationError(
            f"binding {binding.id!r} uses unsupported previous-filing aggregation {op.value!r}",
        )
    if not is_direct_previous_filing_binding(binding):
        return
    selector = _previous_filing_selector(binding)
    source_ids = _previous_filing_source_ids(selector)
    if op == BindingAggregationOp.COPY and len(source_ids) != 1:
        raise RegistryValidationError(
            f"binding {binding.id!r} copy aggregation requires one source casilla",
        )
    if op == BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS and len(source_ids) != 2:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation requires exactly two "
            f"source casillas (positive-part casilla then minoracion casilla); got {source_ids!r}",
        )


def validate_previous_filing_binding(binding: BindingDefinition) -> list[str]:
    """Validate a previous_filing binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`PreviousFilingProvider` and lifts the previous-filing op/source
    invariants for a
    :class:`~cadrumo.domain.calculations.registry.BindingDefinition` to build
    time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, PreviousFilingProvider)
    if failures:
        return failures
    return invariant_diagnostics(binding, "previous-filing", _validate_previous_filing_invariants)


def is_direct_previous_filing_binding(binding: BindingDefinition) -> bool:
    """Whether ``binding`` carries a DIRECT previous-filing selector shape.

    Every real caller passes a ``source == "previous_filing"`` binding (the
    only source this predicate is meaningful for), so ``binding.provider`` is
    already hydrated into :class:`PreviousFilingProvider` by construction
    (the ``BindingProvider`` union hydrates it at construction). Reading
    through the declared model -- ``_previous_filing_selector``, the same
    helper :func:`previous_filing_observation_requirements` and
    :func:`_aggregate_previous_filing_binding` already call -- rather than
    string-literal ``dict.get()`` keys means a field rename on
    ``PreviousFilingProvider`` fails loud instead of silently making every
    direct binding register as non-direct: this predicate backs the
    registry-build refusal (``_validate_relation_sources.py``) that a
    ``previous_filing`` binding must satisfy the direct-selector shape or
    declare ``relation_prefill`` instead, so a silently wrong ``False`` here
    is a validation gate going quiet, not a benign miss.
    """
    selector = _previous_filing_selector(binding)
    if selector.source_casilla_ids:
        return True
    if selector.source_casilla_id is None:
        return False
    return not isinstance(selector.temporal, SameTargetContext)


def _previous_filing_source_ids(selector: PreviousFilingProvider) -> tuple[CasillaId, ...]:
    if selector.source_casilla_ids:
        return selector.source_casilla_ids
    if selector.source_casilla_id is not None:
        return (selector.source_casilla_id,)
    return ()


def previous_filing_binding_source_casilla_ids(binding: BindingDefinition) -> tuple[CasillaId, ...]:
    """Return the source casilla ids a ``previous_filing`` binding targets.

    The canonical, typed way to ask "which casilla(s) does this
    previous_filing binding read from" -- delegates to the same
    :func:`_previous_filing_source_ids` normalisation every other consumer of
    this selector uses, so a caller reading only the singular
    ``source_casilla_id`` key via a raw ``selector_as_dict(binding).get(...)``
    silently misses any binding declaring the plural ``source_casilla_ids``
    form instead, indistinguishable from "this binding targets no casilla at
    all". Reading through :class:`PreviousFilingProvider` also means a
    renamed ``source_casilla_id``/``source_casilla_ids`` field raises here,
    rather than silently returning an empty tuple for every binding.

    Returns an empty tuple for a binding that is not ``previous_filing`` at
    all -- a real, different fact from a malformed or drifted selector.
    """
    if binding.source is not BindingSourceKind.PREVIOUS_FILING:
        return ()
    return _previous_filing_source_ids(_previous_filing_selector(binding))


def _aggregate_previous_filing_binding(
    binding: BindingDefinition,
    values: list[Decimal],
    *,
    source_casilla_ids: tuple[CasillaId, ...] = (),
) -> Decimal:
    op = binding_aggregation_op(binding)
    if op in (BindingAggregationOp.SUM, BindingAggregationOp.COPY):
        return fold_sum_or_copy(
            op.value,
            values,
            subject=f"binding {binding.id!r}",
            copy_unit="source casilla",
        )
    if op == BindingAggregationOp.PRIOR_PAGOS_FRACCIONADOS:
        return _aggregate_prior_pagos_fraccionados(binding, values, source_casilla_ids=source_casilla_ids)
    raise RegistryValidationError(f"binding {binding.id!r} uses unsupported previous-filing aggregation {op.value!r}")


def _aggregate_prior_pagos_fraccionados(
    binding: BindingDefinition,
    values: list[Decimal],
    *,
    source_casilla_ids: tuple[CasillaId, ...],
) -> Decimal:
    """Compute the AEAT Modelo 130 casilla-05 identity from per-anchor pairs.

    casilla 05 = SUM over prior quarters q of max(0, casilla 07_q)
                 minus SUM over the same q of casilla 16_q

    The flat ``values`` list carries per-anchor groups in ``source_casilla_ids``
    order (``[07_q1, 16_q1, 07_q2, 16_q2, ...]``); the op slices that grouping,
    applies the positive-part to the first casilla (07) PER QUARTER before
    summing, and subtracts the sum of the second casilla (16). Both terms are
    load-bearing: a negative prior 07 contributes 0 (not its negative value),
    and the prior casilla-16 minoración is never dropped (per the
    aeat-modelo-130-instructions verbatim rule).
    """
    if len(source_casilla_ids) != 2:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation requires exactly two "
            f"source casillas (positive-part casilla then minoracion casilla); got {source_casilla_ids!r}",
        )
    group_size = len(source_casilla_ids)
    if len(values) % group_size != 0:
        raise RegistryValidationError(
            f"binding {binding.id!r} prior_pagos_fraccionados aggregation expected per-quarter pairs; "
            f"got {len(values)} values for {group_size} source casillas",
        )
    zero = Decimal("0")
    positive_part_total = zero
    minoracion_total = zero
    for index in range(0, len(values), group_size):
        positive_casilla_value = values[index]
        minoracion_casilla_value = values[index + 1]
        positive_part_total += positive_casilla_value if positive_casilla_value > zero else zero
        minoracion_total += minoracion_casilla_value
    return positive_part_total - minoracion_total
