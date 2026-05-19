"""Governed-persistence repository for filing-history records.

Filing history contains submitted modelos, periods, timestamps, and AEAT
status evidence. Records are stored as encrypted byte objects in the
primary SQL backend at AUDIT sensitivity; no plaintext filing-history
JSON or envelope file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ._history_models import FilingHistory


class FilingHistoryRepository(SecureBoundRepository[FilingHistory]):
    """Repository over encrypted SQL-backed filing history records."""

    namespace: ClassVar[str] = "aeat.application.filing.history"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[FilingHistory]] = FilingHistory

    def extract_identifier(self, payload: FilingHistory) -> str:
        return str(payload.modelo)

    def list_modelos(self) -> tuple[str, ...]:
        """Return every modelo persisted in this repository, sorted."""

        return tuple(self.iter_ids())

    def iter_histories(self) -> Iterator[tuple[str, FilingHistory]]:
        """Yield ``(modelo, history)`` tuples for every persisted modelo."""

        for history in self.iter_records():
            yield str(history.modelo), history


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingHistory",
    "FilingHistoryRepository",
]
