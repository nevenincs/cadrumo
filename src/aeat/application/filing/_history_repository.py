"""Governed-persistence repository for filing-history records.

Filing history contains submitted modelos, periods, timestamps, and AEAT
status evidence. Records are stored as encrypted byte objects in the
primary SQL backend at :class:`SensitivityClass` ``AUDIT`` via a
:class:`SecureObjectRepository`; no plaintext filing-history JSON or envelope
file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, override

from pydantic import BaseModel

from ...adapters.persistence.storage import (
    APPLICATION_FILING_HISTORY_NAMESPACE,
    SensitivityClass,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ._history_models import ModeloHistory
from ._runtime_repository import (
    resolve_application_filing_bucket_id,
    secure_objects_for_application_filing_bucket,
)


class ModeloHistoryRepository(SecureBoundRepository[ModeloHistory]):
    """Repository over encrypted SQL-backed filing history records."""

    namespace: ClassVar[str] = APPLICATION_FILING_HISTORY_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = APPLICATION_FILING_HISTORY_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = APPLICATION_FILING_HISTORY_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ModeloHistory

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is None:
            self._bucket_id = resolve_application_filing_bucket_id(bucket_id)
            objects = secure_objects_for_application_filing_bucket(self._bucket_id)
        super().__init__(objects=objects)

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    @override
    def extract_identifier(self, payload: ModeloHistory) -> str:
        return str(payload.modelo)

    def list_modelos(self) -> tuple[str, ...]:
        """Return every modelo persisted in this repository, sorted."""
        return tuple(sorted(self.iter_ids()))

    def iter_histories(self) -> Iterator[tuple[str, ModeloHistory]]:
        """Yield ``(modelo, history)`` tuples of :class:`ModeloHistory` for every persisted modelo."""
        for history in self.iter_records():
            yield str(history.modelo), history


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "ModeloHistory",
    "ModeloHistoryRepository",
]
