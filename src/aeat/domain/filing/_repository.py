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
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ._runtime_repository import resolve_filing_repository_bucket_id, secure_objects_for_filing_bucket
from ._schema import ModeloDraft


class ModeloDraftRepository(SecureBoundRepository[ModeloDraft]):
    """Repository over encrypted SQL-backed filing drafts."""

    namespace: ClassVar[str] = "aeat.domain.filing.drafts"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.FINANCIAL
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[ModeloDraft]] = ModeloDraft

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is None:
            self._bucket_id = resolve_filing_repository_bucket_id(bucket_id)
            objects = secure_objects_for_filing_bucket(self._bucket_id)
        super().__init__(objects=objects)

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""

        return self._bucket_id

    def extract_identifier(self, payload: ModeloDraft) -> str:
        return payload.draft_id

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository."""

        return tuple(self.iter_ids())

    def iter_drafts(self) -> Iterator[ModeloDraft]:
        """Yield every persisted draft, in lexicographic id order."""

        return self.iter_records()


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "ModeloDraftRepository",
]
