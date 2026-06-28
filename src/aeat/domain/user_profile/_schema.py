"""Strict Pydantic records for the centralized user-profile schema.

Each schema section declares a :class:`SensitivityClass` that governs
the encryption tier applied when the section's data is persisted to the
secure DB backend.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.classification import SensitivityClass
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

    @field_validator("type", mode="before")
    @classmethod
    def _parse_type(cls, value: object) -> object:
        return _parse_str_enum(ProfileFieldType, value)

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, value: object) -> object:
        return _parse_sensitivity(value)

    @model_validator(mode="after")
    def _validate_enum_values(self) -> Self:
        if self.type is ProfileFieldType.ENUM and not self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum fields must declare enum_values")
        if self.type is not ProfileFieldType.ENUM and self.enum_values:
            raise UserProfileValidationError(f"field {self.key!r}: enum_values are only valid for enum fields")
        if len(set(self.enum_values)) != len(self.enum_values):
            raise UserProfileValidationError(f"field {self.key!r}: duplicate enum_values are not allowed")
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
