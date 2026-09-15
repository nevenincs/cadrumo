"""Opaque descendant-relationship tokens projected from the facts authority."""

from __future__ import annotations

from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError


class DescendantRelacion(str):
    """Registry-projected relationship token carried by a descendant record.

    Membership, default meaning, and Art. 58.2 entitlement are governed by
    fact ``lirpf-art-81-maternity-descendant-relations``. This type retains
    only the opaque token shape and cannot mint an unprojected value.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a token; only the registry projection may set the guard."""
        if not _registry_validated:
            raise TypeError("DescendantRelacion tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("DescendantRelacion token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("DescendantRelacion must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Register strict projected-token validation with Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the persisted registry token."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the persisted token for diagnostics."""
        return str(self)


__all__ = ["DescendantRelacion"]
