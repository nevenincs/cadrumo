"""Shared validating identifiers and hash-payload primitives.

Provides :class:`ModeloIdentifier` for modelo-code shape validation and
:func:`canonical_decimal_string` for hash-stable decimal payloads. Invalid
modelo-code shapes raise :class:`DomainValidationError`, matching the domain
validation contract used by Pydantic-backed records.

This module is deliberately narrower than the registry-backed modelo catalogue.
:class:`ModeloIdentifier` preserves leading zeros and validates the textual
identifier shape only; it does not prove that a modelo is present in the bundled
registry or in the closed :class:`core.Modelo` enum. Callers that need a
loadable revision must ask the registry authority.
"""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors import DomainValidationError

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for the textual AEAT modelo-code shape.

    The type preserves the incoming string and accepts three digits plus an
    optional uppercase suffix. It is suitable for lightweight domain records and
    Pydantic schemas that need syntactic validation without importing the
    registry authority. It is not a membership check against the current
    registry or the closed :class:`core.Modelo` enum.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> ModeloIdentifier:
        if not _MODELO_RE.match(value):
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

    This helper does not round, quantize, localize, or format amounts for
    display. Callers that need a legal scale or currency presentation must
    enforce that contract before or after using this hash-normalization helper.
    """
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
