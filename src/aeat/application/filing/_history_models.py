"""Strict filing-history records for encrypted filing-state persistence."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain._identifiers import ModeloIdentifier

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FilingHistoryEntry(BaseModel):
    """One recorded filing event observed by the local filing-state store."""

    model_config = _STRICT_FROZEN

    modelo: ModeloIdentifier
    period: str = Field(min_length=1, max_length=16)
    submitted_at: datetime
    status: str = Field(min_length=1, max_length=32)


class FilingHistory(BaseModel):
    """Per-modelo filing history persisted as an encrypted audit envelope."""

    model_config = _STRICT_FROZEN

    modelo: ModeloIdentifier
    entries: tuple[FilingHistoryEntry, ...]

    @model_validator(mode="after")
    def _entries_match_modelo(self) -> FilingHistory:
        for entry in self.entries:
            if entry.modelo != self.modelo:
                raise ValueError(
                    f"FilingHistory.modelo={self.modelo!r} disagrees with entry modelo={entry.modelo!r}",
                )
        return self


__all__ = [
    "FilingHistory",
    "FilingHistoryEntry",
]
