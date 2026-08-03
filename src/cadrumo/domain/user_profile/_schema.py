"""Strict Pydantic records for the centralized user-profile schema.

Each schema section declares a :class:`SensitivityClass` that governs
the encryption tier applied when the section's data is persisted to the
secure DB backend.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.classification import SensitivityClass
from ...core.decimal import coerce_decimal_strict
from ._errors import UserProfileNotFoundError, UserProfileValidationError

_SchemaId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$"),
]
_SectionKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
_FieldKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
_FieldPath = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=160,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$",
    ),
]
_Selector = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
_Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]


class ProfileFieldType(StrEnum):
    """Closed catalogue of field types allowed by the profile schema TOML."""

    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    MONEY = "money"
    DATE = "date"
    EMAIL = "email"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"


class ProfileSnapshotPolicy(StrEnum):
    """Accepted profile snapshot stale-check policies."""

    IMMUTABLE_SECURE_SNAPSHOT_HASH = "immutable_secure_snapshot_hash"


class ProfileRemovePolicy(StrEnum):
    """Accepted profile removal policies."""

    LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS = "live_profile_tombstone_retain_snapshots"


def _parse_str_enum(enum_type: type[StrEnum], value: object) -> object:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        return enum_type(value)
    return value


def _parse_sensitivity(value: object) -> object:
    if isinstance(value, SensitivityClass):
        return value
    if isinstance(value, str):
        return SensitivityClass(value)
    return value


class ProfileFieldDefinition(BaseModel):
    """One field declared inside a user-profile schema section."""

    model_config = _STRICT_FROZEN

    key: _FieldKey
    type: ProfileFieldType
    required: bool = False
    nullable: bool = False
    sensitivity: SensitivityClass
    effective_dated: bool = False
    description: _Description
    enum_values: tuple[str, ...] = Field(default=())
    model_selectors: tuple[_Selector, ...] = Field(default=())
    export_headers: tuple[_Selector, ...] = Field(default=())
    schedule_predicates: tuple[_Selector, ...] = Field(default=())
    legal_refs: tuple[_Description, ...] = Field(default=())
    minimum: Decimal | None = None
    maximum: Decimal | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _parse_type(cls, value: object) -> object:
        return _parse_str_enum(ProfileFieldType, value)

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, value: object) -> object:
        return _parse_sensitivity(value)

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def _parse_decimal_bound(cls, value: object) -> object:
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, str | int):
            try:
                return coerce_decimal_strict(value)
            except (InvalidOperation, ValueError) as exc:
                raise UserProfileValidationError(f"invalid decimal bound {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _validate_enum_values(self) -> Self:
        if self.type is ProfileFieldType.ENUM and not self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum fields must declare enum_values")
        if self.type is not ProfileFieldType.ENUM and self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum_values are only valid for enum fields")
        if len(set(self.enum_values)) != len(self.enum_values):
            raise UserProfileValidationError(f"field {self.key!r}: duplicate enum_values are not allowed")
        numeric_types = {ProfileFieldType.INTEGER, ProfileFieldType.DECIMAL, ProfileFieldType.MONEY}
        if (self.minimum is not None or self.maximum is not None) and self.type not in numeric_types:
            raise UserProfileValidationError(f"field {self.key!r}: numeric bounds are only valid for numeric fields")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise UserProfileValidationError(f"field {self.key!r}: minimum must be less than or equal to maximum")
        return self


class ProfileSectionDefinition(BaseModel):
    """A top-level section in the user-profile schema."""

    model_config = _STRICT_FROZEN

    key: _SectionKey
    title: _Description
    sensitivity: SensitivityClass
    effective_dated: bool = False
    repeatable: bool = False
    fields: tuple[ProfileFieldDefinition, ...] = Field(min_length=1)

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, value: object) -> object:
        return _parse_sensitivity(value)

    @model_validator(mode="after")
    def _validate_unique_fields(self) -> Self:
        keys = tuple(field.key for field in self.fields)
        if len(set(keys)) != len(keys):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise UserProfileValidationError(f"section {self.key!r}: duplicate field keys {duplicates!r}")
        return self


class ProfileSchemaDefinition(BaseModel):
    """The committed centralized user-profile schema."""

    model_config = _STRICT_FROZEN

    id: _SchemaId
    version: int = Field(ge=1)
    title: _Description
    snapshot_policy: ProfileSnapshotPolicy
    remove_policy: ProfileRemovePolicy
    sections: tuple[ProfileSectionDefinition, ...] = Field(min_length=1)

    @field_validator("snapshot_policy", mode="before")
    @classmethod
    def _parse_snapshot_policy(cls, value: object) -> object:
        return _parse_str_enum(ProfileSnapshotPolicy, value)

    @field_validator("remove_policy", mode="before")
    @classmethod
    def _parse_remove_policy(cls, value: object) -> object:
        return _parse_str_enum(ProfileRemovePolicy, value)

    @model_validator(mode="after")
    def _validate_unique_sections(self) -> Self:
        keys = tuple(section.key for section in self.sections)
        if len(set(keys)) != len(keys):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise UserProfileValidationError(f"duplicate section keys {duplicates!r}")
        return self

    @property
    def field_paths(self) -> tuple[str, ...]:
        """Canonical dotted field paths declared by the schema."""
        return tuple(f"{section.key}.{field.key}" for section in self.sections for field in section.fields)

    def section(self, key: str) -> ProfileSectionDefinition:
        """Return a :class:`ProfileSectionDefinition` by canonical section key."""
        for section in self.sections:
            if section.key == key:
                return section
        raise UserProfileNotFoundError(f"unknown user-profile section {key!r}")

    def field(self, path: _FieldPath) -> ProfileFieldDefinition:
        """Return a field by canonical dotted path.

        Returns:
            The :class:`ProfileFieldDefinition` for the given path.
        """
        section_key, field_key = path.split(".", 1)
        section = self.section(section_key)
        for field in section.fields:
            if field.key == field_key:
                return field
        raise UserProfileNotFoundError(f"unknown user-profile field {path!r}")


NUMERIC_PROFILE_FIELD_TYPES: frozenset[ProfileFieldType] = frozenset(
    {ProfileFieldType.INTEGER, ProfileFieldType.DECIMAL, ProfileFieldType.MONEY},
)
"""The field types whose values are numbers, and whose bounds therefore bind.

Mirrors the set :meth:`ProfileFieldDefinition._validate_enum_values` already
uses to decide where ``minimum`` / ``maximum`` may be declared, so the types
that may CARRY a bound and the types that are CHECKED against one cannot
drift apart.
"""


def numeric_value_refusal(field: ProfileFieldDefinition, value: object) -> str | None:
    """Return why ``value`` fails ``field``'s numeric declaration, or ``None``.

    The single authority for "is this a legal value for this numeric field".
    It exists because the declaration was inert: ``minimum`` and ``maximum``
    were validated for their own coherence at schema build and then never
    compared to anything, so a participation percentage declared ``0..100``
    accepted ``999`` on write and carried it into an attribution calculation
    unchallenged. Both the write door and the readers that consume these
    facts ask this one function, rather than each forming its own opinion.

    Numbers are :class:`~decimal.Decimal` (or :class:`int`), never
    :class:`float`. These are financial quantities -- a participation
    percentage and an assigned base that divide a taxable amount between
    members -- so binary floating point is the wrong carrier: its rounding
    is invisible at the point of entry and shows up as a cent that does not
    reconcile in a filing. ``bool`` is rejected despite being an ``int``
    subclass, because ``True`` is an answer to a different question and
    would otherwise silently satisfy a numeric field as ``1``.

    Absence is not this rule's business. A ``None`` value is a cleared or
    unanswered field, which the required-field check judges; refusing it
    here would report one missing field as two unrelated faults.

    Non-finite values need no check: the fact carrier's own union rejects a
    ``NaN`` or infinite :class:`~decimal.Decimal` before it can be
    constructed, so an unorderable value cannot reach a bound comparison.

    Args:
        field: The declaration the value must satisfy.
        value: The value carried by the fact, after the fact carrier has
            restored its type.

    Returns:
        An instructive message naming the field and the range it accepts,
        or ``None`` when the value is admissible or the field is not
        numeric.
    """
    if field.type not in NUMERIC_PROFILE_FIELD_TYPES or value is None:
        return None
    accepted = _accepted_range_clause(field)
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return f"{field.key} must be a number{accepted}; got {value!r}"
    if field.minimum is not None and value < field.minimum:
        return f"{field.key} must be a number{accepted}; got {value}"
    if field.maximum is not None and value > field.maximum:
        return f"{field.key} must be a number{accepted}; got {value}"
    return None


def _accepted_range_clause(field: ProfileFieldDefinition) -> str:
    """Render the declared bounds as an operator-facing phrase.

    Both bounds are INCLUSIVE, and the wording says so: a percentage
    declared ``0..100`` must accept exactly ``0`` and exactly ``100``, and
    a refusal that does not state which end is included leaves the operator
    guessing at the boundary that just refused them.
    """
    minimum, maximum = field.minimum, field.maximum
    if minimum is not None and maximum is not None:
        return f" from {minimum} to {maximum} inclusive"
    if minimum is not None:
        return f" no less than {minimum}"
    if maximum is not None:
        return f" no greater than {maximum}"
    return ""
