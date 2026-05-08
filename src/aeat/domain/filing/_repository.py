"""Governed-persistence repository for filing drafts.

Filing drafts carry exact casilla arithmetic and tax due values. They
are stored as encrypted byte objects in the primary SQL backend at
FINANCIAL sensitivity; no plaintext draft JSON or envelope file lands
on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage import Envelope, SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._schema import FilingDraft

_log = get_logger(__name__)

_DRAFT_ENVELOPE_VERSION = 1
_DRAFT_NAMESPACE = "aeat.domain.filing.drafts"


class FilingDraftRepository:
    """Repository over encrypted SQL-backed filing drafts."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostics."""

        return Path("db://secure_objects") / _DRAFT_NAMESPACE

    def envelope_path_for(self, draft_id: str) -> Path:
        """Return a logical path marker for code that reports draft locations."""

        safe_repository_id(draft_id, context="draft_id")
        return self.store_dir / draft_id

    def lock_target_for(self, draft_id: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""

        safe_repository_id(draft_id, context="draft_id")
        return self.store_dir / f"{draft_id}.lock"

    def load(self, draft_id: str) -> FilingDraft | None:
        """Return the persisted draft or ``None`` if absent."""

        safe_repository_id(draft_id, context="draft_id")
        record = self._objects.load(
            _DRAFT_NAMESPACE,
            draft_id,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_DRAFT_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[FilingDraft].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"filing draft {draft_id} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _DRAFT_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"filing draft {draft_id} is at version {envelope.schema_version}; "
                f"consumer supports up to {_DRAFT_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(self, draft: FilingDraft) -> None:
        """Persist ``draft`` in the encrypted database object store."""

        safe_repository_id(draft.draft_id, context="draft_id")
        envelope = Envelope[FilingDraft](
            schema_version=_DRAFT_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=draft,
        )
        self._objects.save(
            namespace=_DRAFT_NAMESPACE,
            object_key=draft.draft_id,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_DRAFT_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.debug("saved filing draft modelo=%s period=%s", draft.modelo, draft.period)

    def delete(self, draft_id: str) -> bool:
        """Remove a persisted draft."""

        safe_repository_id(draft_id, context="draft_id")
        deleted = self._objects.delete(_DRAFT_NAMESPACE, draft_id)
        if deleted:
            _log.debug("deleted filing draft %s", draft_id)
        return deleted

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository."""

        ids: list[str] = []
        for record in self._objects.list_records(
            _DRAFT_NAMESPACE,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_DRAFT_ENVELOPE_VERSION,
        ):
            envelope = Envelope[FilingDraft].model_validate_json(record.payload.decode("utf-8"))
            ids.append(envelope.payload.draft_id)
        return tuple(sorted(ids))

    def iter_drafts(self) -> Iterator[FilingDraft]:
        """Yield every persisted draft, in lexicographic id order."""

        for draft_id in self.list_draft_ids():
            payload = self.load(draft_id)
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingDraftRepository",
]
