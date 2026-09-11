"""Closed schema contracts for registry-governed facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Final, Literal

from pydantic import BeforeValidator, Field, ValidationInfo, field_validator, model_validator

from .....core.frozen_mapping import FROZEN_MAPPING
from ..errors import RegistryValidationError
from ..ids import LegalRefId, SourceRefId
from ..schema_base import (
    DateAxisField,
    RegistryModel,
    RevisionReviewStatusField,
    SourceCitation,
    coerce_enum_member,
)
from ..schema_scalars import DecimalValue

__all__ = [
    "TAGGED_FACT_ATOM_CONTEXT",
    "BracketFactPayload",
    "BracketFactRow",
    "EntitySetFactPayload",
    "EventFactPayload",
    "FactId",
    "FactOwnership",
    "FactPayload",
    "FactSelector",
    "FactVariantId",
    "GovernedFact",
    "GovernedFactCatalogue",
    "GovernedFactFamily",
    "GovernedFactVariant",
    "MappingFactEntry",
    "MappingFactPayload",
    "MultiOutputFactPayload",
    "MultiOutputFactRow",
    "NamedFactValue",
    "OverrideFactPayload",
    "ScalarFactPayload",
    "tagged_fact_atom_json",
]


_REGISTRY_ID_PATTERN = r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$"
FactId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REGISTRY_ID_PATTERN)]
FactVariantId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REGISTRY_ID_PATTERN)]
FactAtom = str | int | Decimal | bool | date

#: Validation-context key a reader sets when every non-string fact atom arrives
#: in its tagged JSON form. JSON carries a decimal or a date only as a string,
#: which the ``FactAtom`` union would read back as text; the tag keeps the type.
TAGGED_FACT_ATOM_CONTEXT: Final = "tagged_fact_atoms"
_DECIMAL_TAG: Final = "$decimal"
_DATE_TAG: Final = "$date"
_INT_TAG: Final = "$int"
_BOOL_TAG: Final = "$bool"


def tagged_fact_atom_json(value: FactAtom | None) -> object:
    """Return the lossless JSON form of one fact atom.

    A string stays a bare JSON string. Every other atom becomes a single-key
    object naming its type: ``{"$decimal": "0.40"}``, ``{"$date": "2025-01-01"}``,
    ``{"$int": 5}`` and ``{"$bool": true}``. ``None`` stays ``null``.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return {_BOOL_TAG: value}
    if isinstance(value, int):
        return {_INT_TAG: value}
    if isinstance(value, Decimal):
        return {_DECIMAL_TAG: str(value)}
    return {_DATE_TAG: value.isoformat()}


def _hydrate_tagged_fact_atom(value: object, info: ValidationInfo) -> object:
    """Rebuild a tagged fact atom when the reader declares the tagged JSON form.

    Outside that context the value is the compiler's own typed atom and passes
    through. Inside it, only a bare string or exactly one known tag carrying a
    canonical payload is accepted: an unknown tag, a malformed payload, or an
    untagged non-string value is refused rather than guessed from its shape.
    """
    if not (isinstance(info.context, Mapping) and info.context.get(TAGGED_FACT_ATOM_CONTEXT)):
        return value
    if value is None or isinstance(value, str):
        return value
    if not isinstance(value, Mapping) or len(value) != 1:
        raise RegistryValidationError("a non-string fact atom must be a single tagged value")
    ((tag, payload),) = value.items()
    if tag == _DECIMAL_TAG and isinstance(payload, str):
        try:
            decimal = Decimal(payload)
        except InvalidOperation as exc:
            raise RegistryValidationError(f"fact atom {_DECIMAL_TAG} is not a decimal: {payload!r}") from exc
        if not decimal.is_finite() or str(decimal) != payload:
            raise RegistryValidationError(f"fact atom {_DECIMAL_TAG} is not a canonical finite decimal: {payload!r}")
        return decimal
    if tag == _DATE_TAG and isinstance(payload, str):
        try:
            parsed = date.fromisoformat(payload)
        except ValueError as exc:
            raise RegistryValidationError(f"fact atom {_DATE_TAG} is not an ISO date: {payload!r}") from exc
        if parsed.isoformat() != payload:
            raise RegistryValidationError(f"fact atom {_DATE_TAG} is not a canonical ISO date: {payload!r}")
        return parsed
    if tag == _INT_TAG and isinstance(payload, int) and not isinstance(payload, bool):
        return payload
    if tag == _BOOL_TAG and isinstance(payload, bool):
        return payload
    raise RegistryValidationError(f"fact atom tag {tag!r} is unknown or carries a payload of the wrong type")


FactAtomField = Annotated[FactAtom, BeforeValidator(_hydrate_tagged_fact_atom)]
"""A fact atom that also accepts its tagged JSON form when a reader declares it."""
OptionalFactAtomField = Annotated[FactAtom | None, BeforeValidator(_hydrate_tagged_fact_atom)]
"""An optional fact atom that also accepts its tagged JSON form when a reader declares it."""


class GovernedFactFamily(StrEnum):
    """The complete set of payload semantics admitted by the facts registry."""

    SCALAR = "scalar"
    BRACKET = "bracket"
    MAPPING = "mapping"
    ENTITY_SET = "entity_set"
    OVERRIDE = "override"
    EVENT = "event"
    MULTI_OUTPUT = "multi_output"


GovernedFactFamilyField = Annotated[
    GovernedFactFamily,
    BeforeValidator(coerce_enum_member(GovernedFactFamily)),
]


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


class NamedFactValue(RegistryModel):
    """A named typed result used by mapping and multi-output payloads."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value: FactAtomField
    unit: str | None = Field(default=None, min_length=1, max_length=64)


class ScalarFactPayload(RegistryModel):
    """One typed scalar value."""

    kind: Literal[GovernedFactFamily.SCALAR] = GovernedFactFamily.SCALAR
    value_type: Literal["decimal"] | None = None
    value: FactAtomField
    unit: str = Field(min_length=1, max_length=64)

    @field_validator("value", mode="after")
    @classmethod
    def _materialise_declared_decimal(cls, value: FactAtom, info: ValidationInfo) -> FactAtom:
        """Materialise an authored decimal without treating ordinary strings as numbers."""
        if info.data.get("value_type") != "decimal":
            return value
        if isinstance(value, Decimal) and value.is_finite():
            return value
        if not isinstance(value, str):
            raise RegistryValidationError("decimal fact value_type requires a decimal string")
        try:
            decimal = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise RegistryValidationError("decimal fact value_type requires a valid decimal string") from exc
        if not decimal.is_finite():
            raise RegistryValidationError("decimal fact value_type requires a finite decimal")
        return decimal


class BracketFactRow(RegistryModel):
    """One half-open numeric band and its scalar result."""

    lower_bound: DecimalValue
    upper_bound: DecimalValue | None = None
    value: DecimalValue

    @model_validator(mode="after")
    def _validate_bounds(self) -> BracketFactRow:
        if self.upper_bound is not None and self.upper_bound <= self.lower_bound:
            raise RegistryValidationError("fact bracket upper_bound must be greater than lower_bound")
        return self


class BracketFactPayload(RegistryModel):
    """An ordered, non-overlapping numeric bracket schedule."""

    kind: Literal[GovernedFactFamily.BRACKET] = GovernedFactFamily.BRACKET
    unit: str = Field(min_length=1, max_length=64)
    brackets: tuple[BracketFactRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_brackets(self) -> BracketFactPayload:
        ordered = sorted(self.brackets, key=lambda row: row.lower_bound)
        if tuple(ordered) != self.brackets:
            raise RegistryValidationError("fact brackets must be declared in ascending lower_bound order")
        for previous, current in pairwise(ordered):
            if previous.upper_bound is None or current.lower_bound < previous.upper_bound:
                raise RegistryValidationError("fact brackets must not overlap or follow an open-ended bracket")
        return self


class MappingFactEntry(RegistryModel):
    """One exact key-to-value mapping entry."""

    key: FactAtomField
    value_type: Literal["decimal"] | None = None
    value: FactAtomField

    @field_validator("value", mode="after")
    @classmethod
    def _materialise_declared_decimal(cls, value: FactAtom, info: ValidationInfo) -> FactAtom:
        """Materialise an authored mapping Decimal without coercing ordinary strings."""
        if info.data.get("value_type") != "decimal":
            return value
        if isinstance(value, Decimal):
            if value.is_finite():
                return value
            raise RegistryValidationError("decimal mapping value_type requires a finite decimal")
        if not isinstance(value, str):
            raise RegistryValidationError("decimal mapping value_type requires a decimal string")
        try:
            decimal = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise RegistryValidationError("decimal mapping value_type requires a valid decimal string") from exc
        if not decimal.is_finite():
            raise RegistryValidationError("decimal mapping value_type requires a finite decimal")
        return decimal


class MappingFactPayload(RegistryModel):
    """A typed finite mapping whose keys remain explicit schema data."""

    kind: Literal[GovernedFactFamily.MAPPING] = GovernedFactFamily.MAPPING
    entries: tuple[MappingFactEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_keys(self) -> MappingFactPayload:
        keys = [(type(entry.key), entry.key) for entry in self.entries]
        if len(set(keys)) != len(keys):
            raise RegistryValidationError("fact mapping keys must be unique")
        return self


def _coerce_entity_set(value: object) -> object:
    """Materialise immutable entity-set data parsed from a TOML array."""
    if isinstance(value, (tuple, list, set, frozenset)):
        return frozenset(value)
    return value


EntitySetField = Annotated[frozenset[str], BeforeValidator(_coerce_entity_set)]


class EntitySetFactPayload(RegistryModel):
    """A closed set of stable entity tokens."""

    kind: Literal[GovernedFactFamily.ENTITY_SET] = GovernedFactFamily.ENTITY_SET
    entities: EntitySetField = frozenset()

    @model_validator(mode="after")
    def _validate_entities(self) -> EntitySetFactPayload:
        if any(not entity.strip() for entity in self.entities):
            raise RegistryValidationError("fact entity tokens must contain non-whitespace text")
        return self


class OverrideFactPayload(RegistryModel):
    """A result that supersedes named variants under explicit selectors."""

    kind: Literal[GovernedFactFamily.OVERRIDE] = GovernedFactFamily.OVERRIDE
    override_code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value: OptionalFactAtomField = None
    unit: str | None = Field(default=None, min_length=1, max_length=64)


class EventFactPayload(RegistryModel):
    """A legally meaningful event with optional structured outputs."""

    kind: Literal[GovernedFactFamily.EVENT] = GovernedFactFamily.EVENT
    event_date: date
    event_code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    outputs: tuple[NamedFactValue, ...] = ()

    @model_validator(mode="after")
    def _validate_outputs(self) -> EventFactPayload:
        names = [output.name for output in self.outputs]
        if len(set(names)) != len(names):
            raise RegistryValidationError("event output names must be unique")
        return self


class MultiOutputFactRow(RegistryModel):
    """One numeric band producing several named values together."""

    lower_bound: DecimalValue
    upper_bound: DecimalValue | None = None
    outputs: tuple[NamedFactValue, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _validate_row(self) -> MultiOutputFactRow:
        if self.upper_bound is not None and self.upper_bound <= self.lower_bound:
            raise RegistryValidationError("multi-output upper_bound must be greater than lower_bound")
        names = [output.name for output in self.outputs]
        if len(set(names)) != len(names):
            raise RegistryValidationError("multi-output names must be unique within a band")
        return self


class MultiOutputFactPayload(RegistryModel):
    """A band schedule whose match returns more than one named result."""

    kind: Literal[GovernedFactFamily.MULTI_OUTPUT] = GovernedFactFamily.MULTI_OUTPUT
    bands: tuple[MultiOutputFactRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_bands(self) -> MultiOutputFactPayload:
        ordered = sorted(self.bands, key=lambda row: row.lower_bound)
        if tuple(ordered) != self.bands:
            raise RegistryValidationError("multi-output bands must be declared in ascending lower_bound order")
        for previous, current in pairwise(ordered):
            if previous.upper_bound is None or current.lower_bound < previous.upper_bound:
                raise RegistryValidationError("multi-output bands must not overlap or follow an open-ended band")
        return self


FactPayload = Annotated[
    ScalarFactPayload
    | BracketFactPayload
    | MappingFactPayload
    | EntitySetFactPayload
    | OverrideFactPayload
    | EventFactPayload
    | MultiOutputFactPayload,
    Field(discriminator="kind"),
]


class GovernedFactVariant(RegistryModel):
    """One immutable, evidence-bearing redaction or validity interval."""

    variant_id: FactVariantId
    selectors: tuple[FactSelector, ...] = ()
    date_axis: DateAxisField
    valid_from: date
    valid_to: date | None = None
    payload: FactPayload
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    source_citations: tuple[SourceCitation, ...] = ()
    review_status: RevisionReviewStatusField
    ownership: FactOwnershipField
    precedence_over: tuple[FactVariantId, ...] = ()

    @model_validator(mode="after")
    def _validate_variant(self) -> GovernedFactVariant:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("governed fact valid_to must be on or after valid_from")
        selector_names = [selector.name for selector in self.selectors]
        if len(set(selector_names)) != len(selector_names):
            raise RegistryValidationError("governed fact selector names must be unique")
        if self.variant_id in self.precedence_over:
            raise RegistryValidationError("governed fact variant cannot take precedence over itself")
        if len(set(self.precedence_over)) != len(self.precedence_over):
            raise RegistryValidationError("governed fact precedence targets must be unique")
        cited = {citation.source_ref for citation in self.source_citations}
        if not cited.issubset(set(self.source_refs)):
            raise RegistryValidationError("governed fact citations must name a declared source_ref")
        if not self.legal_refs and not self.source_refs:
            raise RegistryValidationError("governed fact variant must declare legal or source evidence")
        return self


class GovernedFact(RegistryModel):
    """A stable semantic fact and all legally distinct variants of that fact."""

    fact_id: FactId
    family: GovernedFactFamilyField
    variants: tuple[GovernedFactVariant, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_fact(self) -> GovernedFact:
        variant_ids = [variant.variant_id for variant in self.variants]
        if len(set(variant_ids)) != len(variant_ids):
            raise RegistryValidationError(f"governed fact {self.fact_id!r} variant ids must be unique")
        if any(variant.payload.kind != self.family for variant in self.variants):
            raise RegistryValidationError(
                f"governed fact {self.fact_id!r} variants must use the declared {self.family!r} family"
            )
        known_ids = set(variant_ids)
        for variant in self.variants:
            unknown = set(variant.precedence_over) - known_ids
            if unknown:
                raise RegistryValidationError(
                    f"governed fact {self.fact_id!r} precedence names unknown variants {sorted(unknown)!r}"
                )
        return self


class GovernedFactCatalogue(RegistryModel):
    """Governed facts keyed by their stable semantic identity."""

    facts: Annotated[Mapping[FactId, GovernedFact], FROZEN_MAPPING] = Field(default_factory=dict, validate_default=True)

    @model_validator(mode="after")
    def _validate_fact_keys(self) -> GovernedFactCatalogue:
        for fact_id, fact in self.facts.items():
            if fact_id != fact.fact_id:
                raise RegistryValidationError(
                    f"governed fact catalogue key {fact_id!r} does not match fact_id {fact.fact_id!r}",
                )
        return self
