"""Exact selectors, ownership, and temporal revisions for governed facts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Literal, override

from pydantic import BeforeValidator, Field, ValidationInfo, field_validator, model_validator

from .....core.errors.hierarchy import pydantic_validation_boundary
from ..errors import RegistryValidationError
from ..ids import LegalRefId, RegistryRevisionNodeId, RevisionId, SourceRefId
from ..revision_contracts import RegistryTemporalDeltaDeclaration
from ..schema_base import (
    DateAxis,
    DateAxisField,
    RegistryModel,
    RevisionReviewStatusField,
    SourceCitation,
    coerce_enum_member,
)
from .atoms import FactAtom, FactAtomField
from .payloads import FactPayload


class FactOwnership(StrEnum):
    """Whether a variant is reviewed source data or a reproducible projection."""

    AUTHORED = "authored"
    GENERATED = "generated"


FactOwnershipField = Annotated[FactOwnership, BeforeValidator(coerce_enum_member(FactOwnership))]


class FactSelector(RegistryModel):
    """One typed, exact-match coordinate of a governed variant."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value_type: Literal["decimal"] | None = None
    value: FactAtomField

    @field_validator("value", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _materialise_declared_decimal(cls, value: FactAtom, info: ValidationInfo) -> FactAtom:
        """Materialise exact authored decimal selectors without float coercion."""
        if info.data.get("value_type") != "decimal":
            return value
        if isinstance(value, Decimal):
            if value.is_finite():
                return value
            raise RegistryValidationError("decimal fact selector value_type requires a finite decimal")
        if not isinstance(value, str):
            raise RegistryValidationError("decimal fact selector value_type requires a decimal string")
        try:
            decimal = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise RegistryValidationError("decimal fact selector value_type requires a valid decimal string") from exc
        if not decimal.is_finite():
            raise RegistryValidationError("decimal fact selector value_type requires a finite decimal")
        return decimal


class GovernedFactVariant(RegistryTemporalDeltaDeclaration):
    """One evidence-bearing fact revision on an exact semantic track.

    ``variant_id`` is the stable revision identity. Bounds are delta-authored
    against the registry's single filing-year support envelope: an explicit date
    is a legal endpoint and nothing projects past it, the first variant of a
    track may omit its lower endpoint to reach the envelope floor, and an omitted
    upper endpoint stays open up to the envelope ceiling.
    """

    variant_id: RegistryRevisionNodeId
    selectors: tuple[FactSelector, ...] = ()
    date_axis: DateAxisField
    payload: FactPayload
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    source_citations: tuple[SourceCitation, ...] = ()
    review_status: RevisionReviewStatusField
    ownership: FactOwnershipField
    source_revision_ids: tuple[RevisionId, ...] = Field(default=(), exclude_if=lambda value: not value)
    precedence_over: tuple[RegistryRevisionNodeId, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_variant(self) -> GovernedFactVariant:
        _validate_variant_identity_declarations(self)
        _validate_variant_evidence_scope(self)
        _validate_variant_ownership(self)
        return self

    @override
    def revision_identity(self) -> str:
        """Return the stable fact revision identity used by shared predecessor mechanics."""
        return self.variant_id


def _validate_variant_identity_declarations(variant: GovernedFactVariant) -> None:
    selector_names = [selector.name for selector in variant.selectors]
    if len(set(selector_names)) != len(selector_names):
        raise RegistryValidationError("governed fact selector names must be unique")
    if variant.variant_id in variant.precedence_over:
        raise RegistryValidationError("governed fact variant cannot take precedence over itself")
    if len(set(variant.precedence_over)) != len(variant.precedence_over):
        raise RegistryValidationError("governed fact precedence targets must be unique")


def _validate_variant_evidence_scope(variant: GovernedFactVariant) -> None:
    if variant.period_selector is not None and variant.date_axis is not DateAxis.FILING_PERIOD:
        raise RegistryValidationError("governed fact period_selector requires the filing_period date axis")
    cited = {citation.source_ref for citation in variant.source_citations}
    if not cited.issubset(set(variant.source_refs)):
        raise RegistryValidationError("governed fact citations must name a declared source_ref")
    if not variant.legal_refs and not variant.source_refs:
        raise RegistryValidationError("governed fact variant must declare legal or source evidence")


def _validate_variant_ownership(variant: GovernedFactVariant) -> None:
    source_revision_ids = variant.source_revision_ids
    if len(set(source_revision_ids)) != len(source_revision_ids):
        raise RegistryValidationError("governed fact source revision ids must be unique")
    if variant.ownership is FactOwnership.GENERATED and not source_revision_ids:
        raise RegistryValidationError("generated governed fact variant must retain its source revision ids")
    if variant.ownership is FactOwnership.AUTHORED and source_revision_ids:
        raise RegistryValidationError("authored governed fact variant cannot claim generated source revisions")
