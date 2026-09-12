"""Typed query and provenance-bearing result contracts for governed facts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from .....core.filing_year import FilingYear
from .....core.period import RegistrySelectorPeriodCode
from ..errors import RegistryValidationError
from ..ids import LegalRefId, RegistryRevisionNodeId, SourceRefId
from ..period_selector_match import selector_period_matches_request
from ..schema_base import (
    DateAxis,
    DateAxisField,
    RegistryModel,
    RevisionReviewStatusField,
    SourceCitation,
)
from ..schema_references import PeriodSelector, RegistryValidityWindow, TemporalProjectionDirection
from .schema import (
    BracketFactPayload,
    EntitySetFactPayload,
    EventFactPayload,
    FactId,
    FactOwnership,
    FactOwnershipField,
    FactProviderId,
    FactSelector,
    FactVariantId,
    GovernedFact,
    GovernedFactCatalogue,
    GovernedFactFamily,
    GovernedFactVariant,
    MappingFactPayload,
    MultiOutputFactPayload,
    OverrideFactPayload,
    ScalarFactPayload,
)

__all__ = [
    "BracketFactQuery",
    "EntitySetFactQuery",
    "EventFactQuery",
    "GovernedFactQuery",
    "MappingFactQuery",
    "MultiOutputFactQuery",
    "OverrideFactQuery",
    "ResolvedBracketFact",
    "ResolvedEntitySetFact",
    "ResolvedEventFact",
    "ResolvedGovernedFact",
    "ResolvedMappingFact",
    "ResolvedMultiOutputFact",
    "ResolvedOverrideFact",
    "ResolvedScalarFact",
    "ScalarFactQuery",
    "resolve_governed_fact",
]


class _FactQuery(RegistryModel):
    """Coordinates shared by every closed governed-fact query family."""

    fact_id: FactId
    date_axis: DateAxisField
    effective_date: date
    selectors: tuple[FactSelector, ...] = ()
    filing_year: FilingYear | None = None
    period: RegistrySelectorPeriodCode | None = None

    @model_validator(mode="after")
    def _validate_selector_coordinates(self) -> _FactQuery:
        names = [selector.name for selector in self.selectors]
        if len(set(names)) != len(names):
            raise RegistryValidationError("governed fact query selector names must be unique")
        if (self.filing_year is None) != (self.period is None):
            raise RegistryValidationError("governed fact query filing_year and period must be declared together")
        if self.filing_year is not None and self.date_axis is not DateAxis.FILING_PERIOD:
            raise RegistryValidationError("governed fact filing_year/period coordinates require the filing_period axis")
        return self


class ScalarFactQuery(_FactQuery):
    """Select one scalar fact variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.SCALAR] = GovernedFactFamily.SCALAR


class BracketFactQuery(_FactQuery):
    """Select one bracket fact variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.BRACKET] = GovernedFactFamily.BRACKET


class MappingFactQuery(_FactQuery):
    """Select one mapping fact variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.MAPPING] = GovernedFactFamily.MAPPING


class EntitySetFactQuery(_FactQuery):
    """Select one entity-set fact variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.ENTITY_SET] = GovernedFactFamily.ENTITY_SET


class OverrideFactQuery(_FactQuery):
    """Select one explicit override variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.OVERRIDE] = GovernedFactFamily.OVERRIDE


class EventFactQuery(_FactQuery):
    """Select one governed event variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.EVENT] = GovernedFactFamily.EVENT


class MultiOutputFactQuery(_FactQuery):
    """Select one multi-output fact variant at an exact temporal coordinate."""

    family: Literal[GovernedFactFamily.MULTI_OUTPUT] = GovernedFactFamily.MULTI_OUTPUT


GovernedFactQuery = Annotated[
    ScalarFactQuery
    | BracketFactQuery
    | MappingFactQuery
    | EntitySetFactQuery
    | OverrideFactQuery
    | EventFactQuery
    | MultiOutputFactQuery,
    Field(discriminator="family"),
]


class _ResolvedFact(RegistryModel):
    """Identity, matched context, and evidence retained by every resolution."""

    fact_id: FactId
    variant_id: FactVariantId
    date_axis: DateAxisField
    effective_date: date
    valid_from: date
    valid_to: date | None = None
    authored_valid_from: date | None = None
    authored_valid_to: date | None = None
    matched_selectors: tuple[FactSelector, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    source_citations: tuple[SourceCitation, ...] = ()
    review_status: RevisionReviewStatusField
    ownership: FactOwnershipField
    authority_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_variant_id: FactVariantId
    source_revision_ids: tuple[RegistryRevisionNodeId, ...] = Field(min_length=1)
    source_provider_id: FactProviderId | None = None
    projection_direction: TemporalProjectionDirection = TemporalProjectionDirection.AUTHORED
    projected_from_date: date | None = None

    @model_validator(mode="after")
    def _validate_resolution_context(self) -> _ResolvedFact:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("resolved governed fact valid_to must be on or after valid_from")
        inside_window = self.effective_date >= self.valid_from and (
            self.valid_to is None or self.effective_date <= self.valid_to
        )
        if self.projection_direction is TemporalProjectionDirection.AUTHORED:
            if not inside_window or self.projected_from_date is not None:
                raise RegistryValidationError("authored governed fact resolution must fall within its validity window")
        elif self.projection_direction is TemporalProjectionDirection.BACKWARD:
            if self.projected_from_date is None or self.projected_from_date <= self.effective_date:
                raise RegistryValidationError("backward fact projection must originate after the query coordinate")
        elif self.projected_from_date is None or self.projected_from_date >= self.effective_date:
            raise RegistryValidationError("forward fact projection must originate before the query coordinate")
        if len(set(self.source_revision_ids)) != len(self.source_revision_ids):
            raise RegistryValidationError("resolved governed fact source revision ids must be unique")
        names = [selector.name for selector in self.matched_selectors]
        if len(set(names)) != len(names):
            raise RegistryValidationError("resolved governed fact selector names must be unique")
        cited = {citation.source_ref for citation in self.source_citations}
        if not cited.issubset(set(self.source_refs)):
            raise RegistryValidationError("resolved governed fact citations must name a declared source_ref")
        if not self.legal_refs and not self.source_refs:
            raise RegistryValidationError("resolved governed fact must retain legal or source evidence")
        return self


class ResolvedScalarFact(_ResolvedFact):
    """A resolved scalar payload with its complete authority context."""

    family: Literal[GovernedFactFamily.SCALAR] = GovernedFactFamily.SCALAR
    payload: ScalarFactPayload


class ResolvedBracketFact(_ResolvedFact):
    """A resolved bracket payload with its complete authority context."""

    family: Literal[GovernedFactFamily.BRACKET] = GovernedFactFamily.BRACKET
    payload: BracketFactPayload


class ResolvedMappingFact(_ResolvedFact):
    """A resolved mapping payload with its complete authority context."""

    family: Literal[GovernedFactFamily.MAPPING] = GovernedFactFamily.MAPPING
    payload: MappingFactPayload


class ResolvedEntitySetFact(_ResolvedFact):
    """A resolved entity-set payload with its complete authority context."""

    family: Literal[GovernedFactFamily.ENTITY_SET] = GovernedFactFamily.ENTITY_SET
    payload: EntitySetFactPayload


class ResolvedOverrideFact(_ResolvedFact):
    """A resolved override payload with its complete authority context."""

    family: Literal[GovernedFactFamily.OVERRIDE] = GovernedFactFamily.OVERRIDE
    payload: OverrideFactPayload


class ResolvedEventFact(_ResolvedFact):
    """A resolved event payload with its complete authority context."""

    family: Literal[GovernedFactFamily.EVENT] = GovernedFactFamily.EVENT
    payload: EventFactPayload


class ResolvedMultiOutputFact(_ResolvedFact):
    """A resolved multi-output payload with its complete authority context."""

    family: Literal[GovernedFactFamily.MULTI_OUTPUT] = GovernedFactFamily.MULTI_OUTPUT
    payload: MultiOutputFactPayload


ResolvedGovernedFact = Annotated[
    ResolvedScalarFact
    | ResolvedBracketFact
    | ResolvedMappingFact
    | ResolvedEntitySetFact
    | ResolvedOverrideFact
    | ResolvedEventFact
    | ResolvedMultiOutputFact,
    Field(discriminator="family"),
]

_RESOLVED_FACT_ADAPTER: TypeAdapter[ResolvedGovernedFact] = TypeAdapter(ResolvedGovernedFact)


def resolve_governed_fact(
    catalogue: GovernedFactCatalogue,
    query: GovernedFactQuery,
    *,
    authority_digest: str,
) -> ResolvedGovernedFact:
    """Resolve one exact query while retaining its complete authority context."""
    fact = catalogue.facts.get(query.fact_id)
    if fact is None:
        raise RegistryValidationError(f"governed fact {query.fact_id!r} is not registered")
    if fact.family is not query.family:
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} has family {fact.family.value!r}, not {query.family.value!r}",
        )
    query_selectors = _selector_identity(query.selectors)
    if fact.support is not None and not fact.support.admits_coordinate(query.effective_date):
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} query falls outside its hard support boundaries"
        )
    windows = fact.materialized_windows()
    track = tuple(
        (variant, windows[variant.variant_id])
        for variant in fact.variants
        if variant.date_axis is query.date_axis
        and _selector_identity(variant.selectors) == query_selectors
        and _period_matches(variant.period_selector, query)
    )
    candidates = tuple((variant, window) for variant, window in track if window.contains_date(query.effective_date))
    projection_direction = TemporalProjectionDirection.AUTHORED
    projected_from_date: date | None = None
    if not candidates:
        candidates, projection_direction, projected_from_date = _projection_candidates(
            fact,
            track,
            effective_date=query.effective_date,
        )
    if not candidates:
        raise RegistryValidationError(f"governed fact {query.fact_id!r} has no variant for the exact query context")
    candidate_variants = tuple(variant for variant, _window in candidates)
    superseded = {
        variant_id
        for candidate in candidate_variants
        for variant_id in _transitive_precedence(candidate.variant_id, fact)
    }
    winners = tuple(candidate for candidate in candidates if candidate[0].variant_id not in superseded)
    if len(winners) != 1:
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} query is ambiguous across variants "
            f"{sorted(candidate.variant_id for candidate, _window in candidates)!r}",
        )
    winner, winner_window = winners[0]
    source_revision_ids: tuple[RegistryRevisionNodeId, ...] = (
        tuple(winner.source_revision_ids) if winner.ownership is FactOwnership.GENERATED else (winner.variant_id,)
    )
    projected_coordinate = (
        fact.support.projection_coordinate(query.effective_date) if fact.support is not None else query.effective_date
    )
    if projected_coordinate is not None and projected_coordinate != query.effective_date:
        projection_direction = TemporalProjectionDirection.FORWARD
        projected_from_date = projected_coordinate
    return _RESOLVED_FACT_ADAPTER.validate_python(
        {
            "family": fact.family,
            "fact_id": fact.fact_id,
            "variant_id": winner.variant_id,
            "date_axis": winner.date_axis,
            "effective_date": query.effective_date,
            "valid_from": winner_window.valid_from,
            "valid_to": winner_window.valid_to,
            "authored_valid_from": winner.valid_from,
            "authored_valid_to": winner.valid_to,
            "matched_selectors": winner.selectors,
            "payload": winner.payload,
            "legal_refs": winner.legal_refs,
            "source_refs": winner.source_refs,
            "source_citations": winner.source_citations,
            "review_status": winner.review_status,
            "ownership": winner.ownership,
            "authority_digest": authority_digest,
            "source_variant_id": winner.variant_id,
            "source_revision_ids": source_revision_ids,
            "source_provider_id": fact.provider_id,
            "projection_direction": projection_direction,
            "projected_from_date": projected_from_date,
        },
    )


def _selector_identity(selectors: tuple[FactSelector, ...]) -> frozenset[tuple[str, type[object], object]]:
    return frozenset((selector.name, type(selector.value), selector.value) for selector in selectors)


def _period_matches(period_selector: PeriodSelector | None, query: _FactQuery) -> bool:
    if period_selector is None:
        return query.period is None
    if query.period is None:
        return False
    return (
        query.filing_year is not None
        and period_selector.includes_year(query.filing_year)
        and any(
            selector_period_matches_request(selector_period, query.period)
            for selector_period in period_selector.periods_for_year(query.filing_year)
        )
    )


def _projection_candidates(
    fact: GovernedFact,
    track: tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...],
    *,
    effective_date: date,
) -> tuple[
    tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...],
    TemporalProjectionDirection,
    date | None,
]:
    support = fact.support
    if support is None or not support.admits_coordinate(effective_date) or not track:
        return (), TemporalProjectionDirection.AUTHORED, None
    before = tuple(item for item in track if item[1].valid_to is not None and item[1].valid_to < effective_date)
    after = tuple(item for item in track if item[1].valid_from > effective_date)
    # A hole between two authored windows is missing authority, not permission
    # to interpolate from either side.
    if before and after:
        return (), TemporalProjectionDirection.AUTHORED, None
    if before:
        boundary = max(item[1].valid_to for item in before)
        return (
            tuple(item for item in before if item[1].valid_to == boundary),
            TemporalProjectionDirection.FORWARD,
            boundary,
        )
    if after:
        boundary = min(item[1].valid_from for item in after)
        return (
            tuple(item for item in after if item[1].valid_from == boundary),
            TemporalProjectionDirection.BACKWARD,
            boundary,
        )
    return (), TemporalProjectionDirection.AUTHORED, None


def _transitive_precedence(variant_id: FactVariantId, fact: GovernedFact) -> frozenset[FactVariantId]:
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    pending = list(edges.get(variant_id, ()))
    reached: set[FactVariantId] = set()
    while pending:
        current = pending.pop()
        if current in reached:
            continue
        reached.add(current)
        pending.extend(edges.get(current, ()))
    return frozenset(reached)
