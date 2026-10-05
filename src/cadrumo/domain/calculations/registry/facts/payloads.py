"""Closed payload shapes admitted by the governed-facts registry."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, ValidationInfo, field_validator, model_validator

from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.type_guards import is_object_collection
from ..errors import RegistryValidationError
from ..schema_base import RegistryModel, coerce_enum_member
from ..schema_scalars import DecimalValue
from .atoms import FactAtom, FactAtomField, OptionalFactAtomField


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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
    def _validate_unique_keys(self) -> MappingFactPayload:
        keys = [(type(entry.key), entry.key) for entry in self.entries]
        if len(set(keys)) != len(keys):
            raise RegistryValidationError("fact mapping keys must be unique")
        return self


@pydantic_validation_boundary
def _coerce_entity_set(value: object) -> object:
    """Materialise immutable entity-set data parsed from a TOML array."""
    if is_object_collection(value):
        return frozenset(value)
    return value


EntitySetField = Annotated[frozenset[str], BeforeValidator(_coerce_entity_set)]


class EntitySetFactPayload(RegistryModel):
    """A closed set of stable entity tokens."""

    kind: Literal[GovernedFactFamily.ENTITY_SET] = GovernedFactFamily.ENTITY_SET
    entities: EntitySetField = frozenset()

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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
