"""Lossless decimal facts with identical input and output wire schemas."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class PublicDecimal(BaseModel):
    """An explicit decimal discriminator preserves a fact's scalar type."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    decimal: str

    @model_validator(mode="after")
    def _canonical_decimal(self) -> Self:
        try:
            parsed = Decimal(self.decimal)
        except InvalidOperation:
            raise ValueError("invalid decimal fact") from None
        if not parsed.is_finite() or str(parsed) != self.decimal:
            raise ValueError("decimal fact must be finite and canonical")
        return self


type PublicScalar = str | int | bool | PublicDecimal


class PublicNamedScalar(BaseModel):
    """One named fact in an immutable, duplicate-free collection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str
    value: PublicScalar


def project_facts(values: Mapping[str, str | int | bool | Decimal]) -> tuple[PublicNamedScalar, ...]:
    """Give unordered facts a deterministic transport order."""
    return tuple(PublicNamedScalar(key=key, value=project_scalar(value)) for key, value in sorted(values.items()))


def restore_facts(values: tuple[PublicNamedScalar, ...]) -> dict[str, str | int | bool | Decimal]:
    """Refuse duplicate names rather than silently dropping a fact."""
    if len({item.key for item in values}) != len(values):
        raise ValueError("duplicate public fact name")
    return {item.key: restore_scalar(item.value) for item in values}


def project_scalar(value: str | int | bool | Decimal) -> PublicScalar:
    """Preserve strings, booleans and integers; explicitly tag decimal facts."""
    return PublicDecimal(decimal=str(value)) if isinstance(value, Decimal) else value


def restore_scalar(value: PublicScalar) -> str | int | bool | Decimal:
    """Restore only the decimal variant to its canonical arithmetic value."""
    return Decimal(value.decimal) if isinstance(value, PublicDecimal) else value
