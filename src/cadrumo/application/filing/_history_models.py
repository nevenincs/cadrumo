"""Strict filing-history records for encrypted filing-state persistence.

:class:`ModeloHistory` groups :class:`ModeloHistoryEntry` rows by
:class:`ModeloIdentifier` before :class:`ModeloHistoryRepository` stores the
aggregate in encrypted AUDIT-class persistence.

The payload is intentionally narrower than the modelo filing-record catalogue:
it records local filing history rows by modelo and period, while
:class:`~ModeloRecord` carries the richer current /
superseded filing lifecycle for calculation revisions.

See Also:
    :class:`application.filing.ModeloHistoryRepository`
        Encrypted AUDIT-class repository that stores these payloads.
    :mod:`domain.modelos`
        Work-unit filing records and supersession history for calculation
        revisions.
    :class:`~ModeloRecordCatalogue`
        Current/superseded filing-record catalogue that owns the authoritative
        work-unit filing lifecycle.
    :mod:`application.calculations`
        Past-filing casilla observations used by cross-period calculation
        resolvers.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain.identifiers import ModeloIdentifier


class ModeloHistoryEntry(BaseModel):
    """One local filing-history row for a :class:`ModeloIdentifier` and :class:`Period`."""

    model_config = _STRICT_FROZEN

    modelo: ModeloIdentifier
    period: Period
    submitted_at: datetime
    status: str = Field(min_length=1, max_length=32)


class ModeloHistory(BaseModel):
    """Per-modelo tuple of :class:`ModeloHistoryEntry` rows for one :class:`ModeloIdentifier`."""

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
