"""Syntax-validated Modelo identifiers.

``Modelo`` is the generic three-digit identifier/value primitive. Registry
membership and product-scope partitions are resolved at their owning domain
boundary rather than while constructing an identifier.
"""

from __future__ import annotations

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError

__all__ = ["Modelo"]


class Modelo(str):
    """Three-digit Modelo identifier; published authority owns membership."""

    __slots__ = ()

    def __new__(cls, value: str) -> Modelo:
        """Validate and construct one three-digit Modelo identifier."""
        raw = str(value)
        if len(raw) != 3 or not raw.isascii() or not raw.isdigit():
            raise CoreValidationError(f"modelo code must be a three-digit ASCII string, got {value!r}")
        return str.__new__(cls, raw)

    @property
    def value(self) -> str:
        """Return the stable string representation used on the wire."""
        return str(self)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Validate from and serialize to the canonical JSON string shape."""
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=r"^[0-9]{3}$"),
            serialization=core_schema.to_string_ser_schema(),
        )
