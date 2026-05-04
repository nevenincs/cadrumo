"""Strict filing-history records for encrypted filing-state persistence."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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

    entries: tuple[FilingHistoryEntry, ...]


__all__ = [
    "FilingHistory",
    "FilingHistoryEntry",
]
