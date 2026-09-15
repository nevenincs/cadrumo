"""Opaque IVA-deduction authority axes projected from the facts registry."""

from __future__ import annotations

from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError


class IvaDeductionFactKind(str):
    """Opaque deduction-kind token projected from governed fact 0085."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated deduction-kind token."""
        if not _registry_validated:
            raise TypeError("IvaDeductionFactKind tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("IvaDeductionFactKind token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("IvaDeductionFactKind must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose the projected deduction-kind token to Pydantic."""
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


class IvaDeductionEvidenceAuthority(str):
    """Opaque evidence-authority token projected from governed fact 0085."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated deduction-evidence authority token."""
        if not _registry_validated:
            raise TypeError(
                "IvaDeductionEvidenceAuthority tokens must be projected from the facts registry",
            )
        if not isinstance(value, str) or not value:
            raise ValueError("IvaDeductionEvidenceAuthority token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str) -> Self:
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("IvaDeductionEvidenceAuthority must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose the projected evidence-authority token to Pydantic."""
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


__all__ = [
    "IvaDeductionEvidenceAuthority",
    "IvaDeductionFactKind",
]
