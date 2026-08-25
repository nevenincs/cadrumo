"""Input-kind schema axis for registry casillas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .errors import RegistryValidationError

__all__ = ["InputKind", "InputKindValue"]


class InputKind(StrEnum):
    """Registry-authoritative classification of how a casilla value is supplied."""

    MANUAL = "manual"
    BOUND = "bound"
    COMPUTED = "computed"
    INFORMATIONAL = "informational"
    PROJECTION_ONLY = "projection_only"


def _coerce_input_kind(value: object) -> object:
    """Coerce a TOML string literal to the canonical InputKind member."""
    if isinstance(value, InputKind):
        return value
    if isinstance(value, str):
        try:
            return InputKind(value)
        except ValueError:
            raise RegistryValidationError(
                f"input_kind {value!r} is not a recognised InputKind member; "
                f"expected one of {[member.value for member in InputKind]}",
            ) from None
    raise RegistryValidationError(f"input_kind must be a string, got {type(value).__name__!r}")


InputKindValue = Annotated[InputKind, BeforeValidator(_coerce_input_kind)]
"""Annotated InputKind that coerces TOML string literals to enum members."""
