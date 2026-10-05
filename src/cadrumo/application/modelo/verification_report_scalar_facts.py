"""Bounded scalar facts preserving verification decimal and integer types."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.identifier_grammar import FIELD_KEY_PATTERN
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError

_FindingFactKey = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=FIELD_KEY_PATTERN)]


_FindingFactText = Annotated[str, Field(max_length=4_096)]


_FindingFactInteger = Annotated[int, Field(ge=-(10**64), le=10**64)]


_FindingFactValue = _FindingFactText | _FindingFactInteger | bool


def _validate_decimal_fact_value(value: _FindingFactValue) -> None:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("decimal verification fact requires a decimal string")
    try:
        decimal_value = Decimal(value)
    except Exception:
        raise ValueError("decimal verification fact is invalid") from None
    if not _decimal_fact_is_bounded(decimal_value):
        raise ValueError("decimal verification fact exceeds the public result bound")


class ModeloVerificationFactProjection(BaseModel):
    """One bounded immutable locale fact without an open-ended object schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: _FindingFactKey
    value_kind: Literal["text", "integer", "boolean", "decimal"]
    value: _FindingFactValue

    @model_validator(mode="after")
    def _value_matches_kind(self) -> Self:
        if self.value_kind == "text" and not isinstance(self.value, str):
            raise ValueError("text verification fact requires a string value")
        if self.value_kind == "integer" and type(self.value) is not int:
            raise ValueError("integer verification fact requires an integer value")
        if self.value_kind == "boolean" and type(self.value) is not bool:
            raise ValueError("boolean verification fact requires a boolean value")
        if self.value_kind == "decimal":
            _validate_decimal_fact_value(self.value)
        return self

    def typed_value(self) -> str | int | bool | Decimal:
        """Restore the domain fact's own type, decimals included."""
        return Decimal(str(self.value)) if self.value_kind == "decimal" else self.value

    @classmethod
    def from_fact(cls, key: str, value: str | int | bool | Decimal) -> ModeloVerificationFactProjection:
        """Copy one typed domain fact into its bounded JSON representation."""
        kind: Literal["text", "integer", "boolean", "decimal"]
        if isinstance(value, bool):
            kind = "boolean"
            wire_value: str | int | bool = value
        elif isinstance(value, int):
            kind = "integer"
            wire_value = value
        elif isinstance(value, Decimal):
            if not _decimal_fact_is_bounded(value):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            kind = "decimal"
            wire_value = str(value)
        else:
            if len(value) > 4_096:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            kind = "text"
            wire_value = value
        return cls(key=key, value_kind=kind, value=wire_value)


def _decimal_fact_is_bounded(value: Decimal) -> bool:
    """Apply the public fact bounds without changing a decimal value."""
    if not value.is_finite():
        return False
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        return False
    return len(parts.digits) + max(exponent, 0) <= 64 and max(-exponent, 0) <= 32


def verification_fact_value_is_bounded(value: str | int | bool | Decimal) -> bool:
    """Check one fact against the immutable public DTO's scalar bounds."""
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return -(10**64) <= value <= 10**64
    if isinstance(value, Decimal):
        return _decimal_fact_is_bounded(value) and len(str(value)) <= 128
    return len(value) <= 4_096
