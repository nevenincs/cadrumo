"""Registry-authoritative enum for export field classification.

This module is isolated from the registry compilation logic to allow
domain.user_profile to reference CasillaFieldKind without triggering
the full registry parse at CLI boot.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator


class CasillaFieldKind(StrEnum):
    """Registry-authoritative classification of how an export field is populated.

    Each member's string value matches the TOML literal used in registry
    source files (``modelo/<n>/exports/*.toml``), so serialisation is
    transparent across every persistence boundary.

    Attributes:
        LITERAL: Field emits a constant string declared in ``literal``.
        CASILLA: Field derives its value from a named casilla.
        BINDING: Field derives its value from a named binding.
        COMPUTED: Field is synthesised at export time via ``computed_key``.
        DRAFT: Field is drawn from a draft attribute via ``draft_attribute``.
        FILLER: Field is a fixed-width pad with no semantic value.
        HEADER: Field emits a filing fact selected by canonical ``producer_key``.
        PROJECTION: Field resolves one typed repeated-row ``projection_ref``.
        CHECKSUM: Field carries a record-level checksum.
    """

    LITERAL = "literal"
    CASILLA = "casilla"
    BINDING = "binding"
    COMPUTED = "computed"
    DRAFT = "draft"
    FILLER = "filler"
    HEADER = "header"
    PROJECTION = "projection"
    CHECKSUM = "checksum"


def _coerce_casilla_field_kind(value: object) -> object:
    """Coerce a TOML string literal to the canonical CasillaFieldKind member.

    Accepts a ``CasillaFieldKind`` instance directly (no-op) or a plain
    string matching one of the declared member values.  Rejects non-string
    and non-member inputs at the schema boundary.
    """
    from cadrumo.domain.calculations.registry.errors import RegistryValidationError as ValidationError

    if isinstance(value, CasillaFieldKind):
        return value
    if isinstance(value, str):
        try:
            return CasillaFieldKind(value)
        except ValueError:
            raise ValidationError(
                f"kind {value!r} is not a recognised CasillaFieldKind member; "
                f"expected one of {[m.value for m in CasillaFieldKind]}",
            ) from None
    raise ValidationError(f"kind must be a string, got {type(value).__name__!r}")


CasillaFieldKindValue = Annotated[CasillaFieldKind, BeforeValidator(_coerce_casilla_field_kind)]
"""Annotated CasillaFieldKind that coerces TOML string literals to enum members.

Use this as the field type on pydantic models that ingest TOML or JSON
payloads where ``kind`` is stored as a plain string.
"""
