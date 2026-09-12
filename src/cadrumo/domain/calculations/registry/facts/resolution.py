"""Typed query and provenance-bearing result contracts for governed facts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from ..errors import RegistryValidationError
from ..ids import LegalRefId, SourceRefId
from ..schema_base import (
    DateAxisField,
    RegistryModel,
    RevisionReviewStatusField,
    SourceCitation,
)
from .schema import (
    BracketFactPayload,
    EntitySetFactPayload,
    EventFactPayload,
    FactId,
    FactOwnershipField,
    FactSelector,
    FactVariantId,
    GovernedFactCatalogue,
    GovernedFactFamily,
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

    @model_validator(mode="after")
    def _validate_selector_coordinates(self) -> _FactQuery:
        names = [selector.name for selector in self.selectors]
        if len(set(names)) != len(names):
            raise RegistryValidationError("governed fact query selector names must be unique")
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
    matched_selectors: tuple[FactSelector, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    source_citations: tuple[SourceCitation, ...] = ()
    review_status: RevisionReviewStatusField
    ownership: FactOwnershipField
    authority_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_resolution_context(self) -> _ResolvedFact:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("resolved governed fact valid_to must be on or after valid_from")
        if self.effective_date < self.valid_from or (self.valid_to is not None and self.effective_date > self.valid_to):
            raise RegistryValidationError("resolved governed fact effective_date must fall within its validity window")
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
    candidates = tuple(
        variant
        for variant in fact.variants
        if variant.date_axis is query.date_axis
        and variant.valid_from <= query.effective_date
        and (variant.valid_to is None or query.effective_date <= variant.valid_to)
        and _selector_identity(variant.selectors) == query_selectors
    )
    if not candidates:
        raise RegistryValidationError(f"governed fact {query.fact_id!r} has no variant for the exact query context")
    superseded = {variant_id for candidate in candidates for variant_id in candidate.precedence_over}
    winners = tuple(candidate for candidate in candidates if candidate.variant_id not in superseded)
    if len(winners) != 1:
        raise RegistryValidationError(
            f"governed fact {query.fact_id!r} query is ambiguous across variants "
            f"{sorted(candidate.variant_id for candidate in candidates)!r}",
        )
    winner = winners[0]
    return _RESOLVED_FACT_ADAPTER.validate_python(
        {
            "family": fact.family,
            "fact_id": fact.fact_id,
            "variant_id": winner.variant_id,
            "date_axis": winner.date_axis,
            "effective_date": query.effective_date,
            "valid_from": winner.valid_from,
            "valid_to": winner.valid_to,
            "matched_selectors": winner.selectors,
            "payload": winner.payload,
            "legal_refs": winner.legal_refs,
            "source_refs": winner.source_refs,
            "source_citations": winner.source_citations,
            "review_status": winner.review_status,
            "ownership": winner.ownership,
            "authority_digest": authority_digest,
        },
    )


def _selector_identity(selectors: tuple[FactSelector, ...]) -> frozenset[tuple[str, type[object], object]]:
    return frozenset((selector.name, type(selector.value), selector.value) for selector in selectors)
