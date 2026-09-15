"""Opaque capital-goods vocabulary tokens projected from fact 0130.

The token classes intentionally carry no local membership list.  Membership,
descriptions, legal scope, and the acquisition-year floor are selected by the
dated LIVA capital-goods fact at the registry boundary.
"""

from __future__ import annotations

from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError


class BienInversionKind(str):
    """Opaque LIVA capital-goods kind token projected from fact 0130."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a capital-goods kind token after registry validation."""
        if not _registry_validated:
            raise TypeError("BienInversionKind tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("BienInversionKind token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("BienInversionKind must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose registry-only validation and string serialization to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token for diagnostics."""
        return str(self)


class BienInversionDisposalRegime(str):
    """Opaque LIVA disposal-regime token projected from fact 0130."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a disposal-regime token after registry validation."""
        if not _registry_validated:
            raise TypeError("BienInversionDisposalRegime tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("BienInversionDisposalRegime token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("BienInversionDisposalRegime must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose registry-only validation and string serialization to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical token for diagnostics."""
        return str(self)


__all__ = ["BienInversionDisposalRegime", "BienInversionKind"]
