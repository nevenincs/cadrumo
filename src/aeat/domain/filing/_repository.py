"""Governed-persistence repository for filing drafts.

Filing drafts carry exact casilla arithmetic and tax due values. They
are stored as encrypted byte objects in the primary SQL backend at
FINANCIAL sensitivity; no plaintext draft JSON or envelope file lands
on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ._schema import FilingDraft


class FilingDraftRepository(SecureBoundRepository[FilingDraft]):
    """Repository over encrypted SQL-backed filing drafts."""

    namespace: ClassVar[str] = "aeat.domain.filing.drafts"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.FINANCIAL
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[FilingDraft]] = FilingDraft

    def extract_identifier(self, payload: FilingDraft) -> str:
        return payload.draft_id

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository."""

        return tuple(self.iter_ids())

    def iter_drafts(self) -> Iterator[FilingDraft]:
        """Yield every persisted draft, in lexicographic id order."""

        return self.iter_records()


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingDraftRepository",
]
