"""Typed query and provenance-bearing result contracts for governed facts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..errors import RegistryValidationError
from ..schema_base import DateAxisField, LegalRefs, RegistryModel, RevisionReviewStatusField, SourceCitation, SourceRefs
from .schema import (
    BracketFactPayload,
    EntitySetFactPayload,
    EventFactPayload,
    FactId,
    FactOwnershipField,
    FactSelector,
    FactVariantId,
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
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(min_length=1)
    review_status: RevisionReviewStatusField
    ownership: FactOwnershipField
    authority_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_resolution_context(self) -> _ResolvedFact:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("resolved governed fact valid_to must be on or after valid_from")
        if self.effective_date < self.valid_from or (
            self.valid_to is not None and self.effective_date > self.valid_to
        ):
            raise RegistryValidationError("resolved governed fact effective_date must fall within its validity window")
        names = [selector.name for selector in self.matched_selectors]
        if len(set(names)) != len(names):
            raise RegistryValidationError("resolved governed fact selector names must be unique")
        cited = {citation.source_ref for citation in self.source_citations}
        if not cited.issubset(set(self.source_refs)):
            raise RegistryValidationError("resolved governed fact citations must name a declared source_ref")
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
