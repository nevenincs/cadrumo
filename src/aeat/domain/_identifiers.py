"""Shared validating identifiers and identifier-derivation primitives.

Provides :class:`ModeloIdentifier` for official modelo codes and
:func:`canonical_decimal_string` for hash-stable decimal payloads. Invalid
modelo codes raise :class:`DomainValidationError`, matching the domain
validation contract used by Pydantic-backed records.
"""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ._errors import DomainValidationError

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo official code."""

    __slots__ = ()

    def __new__(cls, value: str) -> ModeloIdentifier:
        if not isinstance(value, str) or not _MODELO_RE.match(value):
            raise DomainValidationError(f"Invalid modelo identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_MODELO_RE.pattern),
        )


def canonical_decimal_string(value: Decimal) -> str:
    """Render a :class:`~decimal.Decimal` into a stable fixed-point string for hashing.

    Used by domain ``derive_*_id`` helpers to canonicalise monetary fields
    before they enter a SHA-256 hash payload, so two semantically equal
    amounts (``Decimal("10")`` vs ``Decimal("10.00")``) hash to the same
    identifier. Zero collapses to ``"0"`` regardless of input precision;
    non-zero values are normalised (trailing zeros removed) and formatted
    without exponent notation.
    """
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
