"""Canonical invariant for materialised operator-action arguments."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from .identifier_grammar import FIELD_KEY_PATTERN, NAMESPACED_ID_PATTERN

_STRICT_FROZEN_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_assignment=True,
)


def _validate_evidence_id_pairing(
    source: ActionArgumentSource | None,
    source_evidence_id: str | None,
) -> None:
    """Carry ``source_evidence_id`` exactly when the source is condition evidence."""
    from_condition_evidence = source is ActionArgumentSource.CONDITION_EVIDENCE
    if from_condition_evidence and source_evidence_id is None:
        raise ValueError("condition-evidence action arguments require source_evidence_id")
    if not from_condition_evidence and source_evidence_id is not None:
        raise ValueError("only condition-evidence action arguments can carry source_evidence_id")


class ActionArgumentResolution(BaseModel):
    """One resolved or missing argument with its factual provenance."""

    model_config = _STRICT_FROZEN_CONFIG

    argument_name: str = Field(pattern=FIELD_KEY_PATTERN, min_length=1, max_length=120)
    status: ActionArgumentStatus
    value: str | int | bool | Decimal | None = None
    source: ActionArgumentSource | None = None
    source_key: str | None = Field(default=None, pattern=FIELD_KEY_PATTERN, min_length=1, max_length=160)
    source_evidence_id: str | None = Field(
        default=None,
        pattern=NAMESPACED_ID_PATTERN,
        min_length=3,
        max_length=160,
    )

    @model_validator(mode="after")
    def _validate_resolution(self) -> Self:
        """Keep resolved and missing argument states mutually exclusive."""
        if self.status is not ActionArgumentStatus.RESOLVED:
            carried = (self.value, self.source, self.source_key, self.source_evidence_id)
            if any(fact is not None for fact in carried):
                raise ValueError("missing action arguments cannot carry value or source")
            return self
        if any(fact is None for fact in (self.value, self.source, self.source_key)):
            raise ValueError("resolved action arguments require value, source, and source_key")
        _validate_evidence_id_pairing(self.source, self.source_evidence_id)
        return self


__all__ = ["ActionArgumentResolution"]
