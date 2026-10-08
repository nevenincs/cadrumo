"""Typed query and provenance-bearing result contracts for governed facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Final, Literal

from pydantic import Field, TypeAdapter, model_validator

from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.filing_year import FilingYear
from .....core.period import RegistrySelectorPeriodCode
from ..errors import GovernedFactNotApplicableError, RegistryValidationError
from ..ids import LegalRefId, RegistryRevisionNodeId, SourceRefId
from ..period_selector_match import selector_period_matches_request
from ..schema_base import (
    DateAxis,
    DateAxisField,
    RegistryModel,
    RevisionReviewStatusField,
    SourceCitation,
)
from ..schema_references import (
    DateSupportEnvelope,
    PeriodSelector,
    RegistryValidityWindow,
    TemporalProjectionDirection,
    TemporalSupportEnvelope,
)
from .payloads import (
    BracketFactPayload,
    EntitySetFactPayload,
    EventFactPayload,
    GovernedFactFamily,
    MappingFactPayload,
    MultiOutputFactPayload,
    OverrideFactPayload,
    ScalarFactPayload,
)
from .schema import (
    FactId,
    FactProviderId,
    GovernedFact,
    GovernedFactCatalogue,
)
from .variants import FactOwnership, FactOwnershipField, FactSelector, GovernedFactVariant

__all__ = [
    "UNIQUE_REFERENCES_REQUIREMENT",
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
    "optional_unique_mapping_tokens",
    "required_mapping_entry",
    "resolve_governed_fact",
    "resolve_validated_governed_fact",
    "unique_mapping_tokens",
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
    @pydantic_validation_boundary
    def _validate_selector_coordinates(self) -> _FactQuery:
        names = [selector.name for selector in self.selectors]
        if len(set(names)) != len(names):
            raise ValueError("governed fact query selector names must be unique")
        if (self.filing_year is None) != (self.period is None):
            raise ValueError("governed fact query filing_year and period must be declared together")
        if self.filing_year is not None and self.date_axis is not DateAxis.FILING_PERIOD:
            raise ValueError("governed fact filing_year/period coordinates require the filing_period axis")
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
    variant_id: RegistryRevisionNodeId
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
    source_variant_id: RegistryRevisionNodeId
    source_revision_ids: tuple[RegistryRevisionNodeId, ...] = Field(min_length=1)
    source_provider_id: FactProviderId | None = None
    projection_direction: TemporalProjectionDirection = TemporalProjectionDirection.AUTHORED
    projected_from_date: date | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_resolution_context(self) -> _ResolvedFact:
        _validate_resolved_window_order(self)
        _validate_resolved_projection_direction(self)
        _validate_resolved_provenance_context(self)
        return self


def _validate_resolved_window_order(fact: _ResolvedFact) -> None:
    if fact.valid_to is not None and fact.valid_to < fact.valid_from:
        raise ValueError("resolved governed fact valid_to must be on or after valid_from")


def _validate_resolved_projection_direction(fact: _ResolvedFact) -> None:
    inside_window = fact.effective_date >= fact.valid_from and (
        fact.valid_to is None or fact.effective_date <= fact.valid_to
    )
    if fact.projection_direction is TemporalProjectionDirection.AUTHORED:
        _validate_authored_projection(fact, inside_window)
    elif fact.projection_direction is TemporalProjectionDirection.BACKWARD:
        _validate_backward_projection(fact)
    else:
        _validate_forward_projection(fact)


def _validate_authored_projection(fact: _ResolvedFact, inside_window: bool) -> None:
    if not inside_window or fact.projected_from_date is not None:
        raise ValueError("authored governed fact resolution must fall within its validity window")


def _validate_backward_projection(fact: _ResolvedFact) -> None:
    if fact.projected_from_date is None or fact.projected_from_date <= fact.effective_date:
        raise ValueError("backward fact projection must originate after the query coordinate")


def _validate_forward_projection(fact: _ResolvedFact) -> None:
    if fact.projected_from_date is None or fact.projected_from_date >= fact.effective_date:
        raise ValueError("forward fact projection must originate before the query coordinate")


def _validate_resolved_provenance_context(fact: _ResolvedFact) -> None:
    if len(set(fact.source_revision_ids)) != len(fact.source_revision_ids):
        raise ValueError("resolved governed fact source revision ids must be unique")
    names = [selector.name for selector in fact.matched_selectors]
    if len(set(names)) != len(names):
        raise ValueError("resolved governed fact selector names must be unique")
    cited = {citation.source_ref for citation in fact.source_citations}
    if not cited.issubset(set(fact.source_refs)):
        raise ValueError("resolved governed fact citations must name a declared source_ref")
    if not fact.legal_refs and not fact.source_refs:
        raise ValueError("resolved governed fact must retain legal or source evidence")


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


def required_mapping_entry(entries: Mapping[str, str], key: str, *, subject: str) -> str:
    """Return the stripped value of one required mapping-fact entry.

    ``subject`` names the mapping in the refusal, so each consumer keeps its own
    diagnostic wording.

    Raises:
        RegistryValidationError: When ``key`` is absent or blank.
    """
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"{subject} is missing {key!r}")
    return value.strip()


UNIQUE_REFERENCES_REQUIREMENT: Final = "must contain unique references"


def _unique_tokens(
    value: str,
    key: str,
    *,
    subject: str,
    requirement: str,
    separator: str,
    refuse_empty: bool,
) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in value.split(separator) if token.strip())
    if (refuse_empty and not tokens) or len(tokens) != len(set(tokens)):
        raise RegistryValidationError(f"{subject} {key!r} {requirement}")
    return tokens


def unique_mapping_tokens(
    entries: Mapping[str, str],
    key: str,
    *,
    subject: str,
    requirement: str = "must contain unique tokens",
    separator: str = ",",
    refuse_empty: bool = True,
) -> tuple[str, ...]:
    """Return the stripped, non-empty separated tokens of one required entry, in order.

    ``subject`` and ``requirement`` word the refusal, so each consumer keeps its
    own diagnostic. ``refuse_empty=False`` admits a present entry made only of
    separators, such as ``",,"``, as an empty tuple.

    Raises:
        RegistryValidationError: When the entry is absent or blank, repeats a
            token, or (unless ``refuse_empty`` is false) yields no token.
    """
    return _unique_tokens(
        required_mapping_entry(entries, key, subject=subject),
        key,
        subject=subject,
        requirement=requirement,
        separator=separator,
        refuse_empty=refuse_empty,
    )


def optional_unique_mapping_tokens(
    entries: Mapping[str, str],
    key: str,
    *,
    subject: str,
    requirement: str = "must contain unique tokens",
) -> tuple[str, ...]:
    """Return the stripped, non-empty comma-separated tokens of one optional entry, in order.

    An absent or blank entry, or one made only of separators, declares no token
    and yields an empty tuple. ``subject`` and ``requirement`` word the refusal.

    Raises:
        RegistryValidationError: When the entry repeats a token.
    """
    value = entries.get(key)
    if value is None or not value.strip():
        return ()
    return _unique_tokens(value, key, subject=subject, requirement=requirement, separator=",", refuse_empty=False)


def resolve_governed_fact(
    catalogue: GovernedFactCatalogue,
    query: GovernedFactQuery,
    *,
    authority_digest: str,
    support: TemporalSupportEnvelope,
) -> ResolvedGovernedFact:
    """Resolve one query through the variant window containing it."""
    fact = catalogue.facts.get(query.fact_id)
    if fact is None:
        raise RegistryValidationError(f"governed fact {query.fact_id!r} is not registered")
    return resolve_validated_governed_fact(fact, query, authority_digest=authority_digest, support=support)


def resolve_validated_governed_fact(
    fact: GovernedFact,
    query: GovernedFactQuery,
    *,
    authority_digest: str,
    support: TemporalSupportEnvelope,
) -> ResolvedGovernedFact:
    """Resolve one query from an already validated immutable fact.

    Published component readers validate a governed fact while decoding its
    content-addressed component.  Runtime point reads must not wrap that model
    in a new ``GovernedFactCatalogue`` and validate the same static graph again
    for every temporal query.

    ``support`` is the registry's single filing-year envelope, the same one that
    gates modelo revisions: a coordinate outside it is refused, a first variant
    omitting ``valid_from`` reaches its floor, and an open final variant carries
    past its horizon. An explicit endpoint is a legal boundary, so a coordinate
    in a gap between explicit windows resolves to nothing rather than to the
    nearest variant.
    """
    query_selectors = _validate_fact_query(fact, query, support)
    date_support = support.date_envelope()
    windows = fact.materialized_windows(date_support)
    track = _matching_fact_track(fact, query, query_selectors, windows)
    candidates = _containing_fact_candidates(track, query.effective_date)
    if not candidates:
        raise GovernedFactNotApplicableError(
            fact_id=query.fact_id,
            effective_date=query.effective_date,
            date_axis=query.date_axis.value,
        )
    winner, winner_window = _select_fact_winner(query, fact, candidates)
    source_revision_ids = _winner_source_revision_ids(winner)
    projection_direction, projected_from_date = _resolved_projection_context(date_support, query.effective_date)
    return _materialize_resolved_fact(
        fact,
        query,
        winner,
        winner_window,
        authority_digest,
        source_revision_ids,
        projection_direction,
        projected_from_date,
    )


def _validate_fact_query(
    fact: GovernedFact,
    query: GovernedFactQuery,
    support: TemporalSupportEnvelope,
) -> frozenset[tuple[str, type[object], object]]:
    if fact.fact_id != query.fact_id:
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} query was paired with {fact.fact_id!r}",
        )
    if fact.family is not query.family:
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} has family {fact.family.value!r}, not {query.family.value!r}",
        )
    query_selectors = _selector_identity(query.selectors)
    coordinate_year = query.filing_year if query.filing_year is not None else query.effective_date.year
    if not support.admits_coordinate(coordinate_year):
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} query year {coordinate_year} falls outside the supported filing years"
        )
    return query_selectors


def _matching_fact_track(
    fact: GovernedFact,
    query: _FactQuery,
    query_selectors: frozenset[tuple[str, type[object], object]],
    windows: Mapping[RegistryRevisionNodeId, RegistryValidityWindow],
) -> tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...]:
    return tuple(
        (variant, windows[variant.variant_id])
        for variant in fact.variants
        if variant.date_axis is query.date_axis
        and _selector_identity(variant.selectors) == query_selectors
        and _period_matches(variant.period_selector, query)
    )


def _containing_fact_candidates(
    track: tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...],
    effective_date: date,
) -> tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...]:
    return tuple((variant, window) for variant, window in track if window.contains_date(effective_date))


def _select_fact_winner(
    query: _FactQuery,
    fact: GovernedFact,
    candidates: tuple[tuple[GovernedFactVariant, RegistryValidityWindow], ...],
) -> tuple[GovernedFactVariant, RegistryValidityWindow]:
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
    return winners[0]


def _winner_source_revision_ids(winner: GovernedFactVariant) -> tuple[RegistryRevisionNodeId, ...]:
    return tuple(winner.source_revision_ids) if winner.ownership is FactOwnership.GENERATED else (winner.variant_id,)


def _resolved_projection_context(
    support: DateSupportEnvelope,
    effective_date: date,
) -> tuple[TemporalProjectionDirection, date | None]:
    projected_coordinate = support.projection_coordinate(effective_date)
    if projected_coordinate is not None and projected_coordinate != effective_date:
        return TemporalProjectionDirection.FORWARD, projected_coordinate
    return TemporalProjectionDirection.AUTHORED, None


def _materialize_resolved_fact(
    fact: GovernedFact,
    query: _FactQuery,
    winner: GovernedFactVariant,
    winner_window: RegistryValidityWindow,
    authority_digest: str,
    source_revision_ids: tuple[RegistryRevisionNodeId, ...],
    projection_direction: TemporalProjectionDirection,
    projected_from_date: date | None,
) -> ResolvedGovernedFact:
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


def _transitive_precedence(
    variant_id: RegistryRevisionNodeId,
    fact: GovernedFact,
) -> frozenset[RegistryRevisionNodeId]:
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    pending = list(edges.get(variant_id, ()))
    reached: set[RegistryRevisionNodeId] = set()
    while pending:
        current = pending.pop()
        if current in reached:
            continue
        reached.add(current)
        pending.extend(edges.get(current, ()))
    return frozenset(reached)
