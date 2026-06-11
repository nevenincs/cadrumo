"""Strict filing-history records for encrypted filing-state persistence."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain._identifiers import ModeloIdentifier


class ModeloHistoryEntry(BaseModel):
    """One recorded filing event observed by the local filing-state store."""

    model_config = _STRICT_FROZEN

    modelo: ModeloIdentifier
    period: Period
    submitted_at: datetime
    status: str = Field(min_length=1, max_length=32)


class ModeloHistory(BaseModel):
    """Per-modelo filing history persisted as an encrypted audit envelope."""

    model_config = _STRICT_FROZEN

    modelo: ModeloIdentifier
    entries: tuple[ModeloHistoryEntry, ...]

    @model_validator(mode="after")
    def _entries_match_modelo(self) -> ModeloHistory:
        for entry in self.entries:
            if entry.modelo != self.modelo:
                raise ValueError(
                    f"ModeloHistory.modelo={self.modelo!r} disagrees with entry modelo={entry.modelo!r}",
                )
        return self


__all__ = [
    "ModeloHistory",
    "ModeloHistoryEntry",
]
