"""Canonical invariant for materialised operator-action arguments."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._operator_action_enums import ActionArgumentSource, ActionArgumentStatus

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_assignment=True,
)
_FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
_NAMESPACED_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"


class ActionArgumentResolution(BaseModel):
    """One resolved or missing argument with its factual provenance."""

    model_config = _STRICT_FROZEN_CONFIG

    argument_name: str = Field(pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=120)
    status: ActionArgumentStatus
    value: str | int | bool | Decimal | None = None
    source: ActionArgumentSource | None = None
    source_key: str | None = Field(default=None, pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=160)
    source_evidence_id: str | None = Field(
        default=None,
        pattern=_NAMESPACED_ID_PATTERN,
        min_length=3,
        max_length=160,
    )

    @model_validator(mode="after")
    def _validate_resolution(self) -> Self:
        """Keep resolved and missing argument states mutually exclusive."""
        if self.status is ActionArgumentStatus.RESOLVED:
            if self.value is None or self.source is None or self.source_key is None:
                raise ValueError("resolved action arguments require value, source, and source_key")
            if self.source is ActionArgumentSource.CONDITION_EVIDENCE and self.source_evidence_id is None:
                raise ValueError("condition-evidence action arguments require source_evidence_id")
            if self.source is not ActionArgumentSource.CONDITION_EVIDENCE and self.source_evidence_id is not None:
                raise ValueError("only condition-evidence action arguments can carry source_evidence_id")
        elif (
            self.value is not None
            or self.source is not None
            or self.source_key is not None
            or self.source_evidence_id is not None
        ):
            raise ValueError("missing action arguments cannot carry value or source")
        return self


__all__ = ["ActionArgumentResolution"]
