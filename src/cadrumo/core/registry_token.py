"""Opaque text tokens whose membership a registry projection establishes.

A registry-projected vocabulary carries no closed Python member list: the dated
registry owns which tokens exist and what they mean. These bases hold only the
structural contract every such token shares, so a vocabulary type declares its
docstring and nothing else unless its diagnostics or boundary differ.

- :class:`StrictRegistryToken` admits only already projected tokens at a typed
  model boundary and serializes them as text.
- :class:`TextProjectedRegistryToken` projects a non-empty text value at the
  model boundary.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError


class RegistryToken(str):
    """Text token constructible only at a registry projection boundary."""

    __slots__ = ()

    #: Names the token in diagnostics; the class name when unset.
    _vocabulary_label: ClassVar[str | None] = None
    #: Names the authority in the refusal raised for unprojected construction.
    _projection_source: ClassVar[str] = "facts registry"
    #: Replaces the default empty-token refusal when the vocabulary words it differently.
    _empty_value_message: ClassVar[str | None] = None

    @classmethod
    def _diagnostic_label(cls) -> str:
        return cls._vocabulary_label or cls.__name__

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct only when called by the registry projection boundary."""
        if not _registry_validated:
            raise TypeError(f"{cls._diagnostic_label()} tokens must be projected from the {cls._projection_source}")
        if not isinstance(value, str) or not value:
            raise ValueError(cls._empty_value_message or f"{cls._diagnostic_label()} token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @property
    def value(self) -> str:
        """Return the canonical registry token text."""
        return str(self)


class StrictRegistryToken(RegistryToken):
    """Registry token a typed model accepts only once it has been projected."""

    __slots__ = ()

    #: The error a typed model boundary raises for an unprojected value.
    _refusal_error: ClassVar[type[Exception]] = CoreValidationError

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise cls._refusal_error(f"{cls._diagnostic_label()} must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only a projected token and serialize it as text."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)


class TextProjectedRegistryToken(RegistryToken):
    """Registry token a typed model projects from its non-empty text form."""

    __slots__ = ()

    #: Names the token in the refusals raised at the model boundary.
    _boundary_subject: ClassVar[str]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Project the text token through the registry boundary."""
        return core_schema.no_info_after_validator_function(
            cls._project_pydantic,
            core_schema.str_schema(min_length=1),
        )

    @classmethod
    def _project_pydantic(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls.from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{cls._boundary_subject} must be a non-empty structural token") from exc
        raise TypeError(f"{cls._boundary_subject} must be a string token")


__all__ = ["RegistryToken", "StrictRegistryToken", "TextProjectedRegistryToken"]
