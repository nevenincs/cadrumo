"""The tagged factual scalar a Modelo work review carries in its findings and blockers."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


def _validate_review_fact_scalar(kind: Literal["str", "int", "bool", "decimal", "none"], value: str) -> None:
    """Validate the admitted scalar's exact canonical lexical representation."""
    if kind == "bool" and value not in {"true", "false"}:
        raise ValueError("review boolean fact must be canonical")
    if kind == "int" and str(int(value)) != value:
        raise ValueError("review integer fact must be canonical")
    if kind == "decimal":
        decimal = Decimal(value)
        if not decimal.is_finite() or str(decimal) != value:
            raise ValueError("review decimal fact must be finite and canonical")


class ModeloWorkReviewFact(BaseModel):
    """One tagged factual scalar in a schema-visible immutable sequence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str = Field(min_length=1, max_length=128)
    kind: Literal["str", "int", "bool", "decimal", "none"]
    value: str | None = Field(max_length=4096)

    @classmethod
    def from_value(cls, key: str, value: str | int | bool | Decimal | None) -> Self:
        """Preserve the precise canonical scalar type in an explicit tag."""
        if value is None:
            return cls(key=key, kind="none", value=None)
        if isinstance(value, bool):
            return cls(key=key, kind="bool", value="true" if value else "false")
        if isinstance(value, int):
            return cls(key=key, kind="int", value=str(value))
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("review decimal fact must be finite")
            return cls(key=key, kind="decimal", value=str(value))
        return cls(key=key, kind="str", value=value)

    def to_value(self) -> str | int | bool | Decimal | None:
        """Decode one exact factual scalar without a generic object payload."""
        if self.kind == "none":
            return None
        if self.value is None:
            raise ValueError("review fact value is missing")
        if self.kind == "bool":
            return self.value == "true"
        if self.kind == "int":
            return int(self.value)
        if self.kind == "decimal":
            return Decimal(self.value)
        return self.value

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if self.kind == "none":
            if self.value is not None:
                raise ValueError("none review fact must have no value")
        elif self.value is None:
            raise ValueError("review fact value is required")
        else:
            _validate_review_fact_scalar(self.kind, self.value)
        return self
