"""Governed-persistence repository for submitted-filing audit records.

Submitted filings capture uploaded payload bytes, AEAT responses, and
identity-bearing filing context. They are stored as encrypted byte
objects in the primary SQL backend at AUDIT sensitivity; no plaintext
submission JSON or envelope file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage import Envelope, SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._models import SubmittedFiling

_log = get_logger(__name__)

_SUBMISSION_ENVELOPE_VERSION = 1
_SUBMISSION_NAMESPACE = "aeat.domain.submission.records"


class SubmissionRepository:
    """Repository over encrypted SQL-backed submitted filing records."""

    def __init__(self, *, store_dir: Path | None = None) -> None:
        del store_dir
        self._objects = SecureObjectRepository()

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostic messages."""

        return Path("db://secure_objects") / _SUBMISSION_NAMESPACE

    def envelope_path_for(self, submission_id: str) -> Path:
        """Return a logical object marker for ``submission_id``."""

        safe_repository_id(submission_id, context="submission_id")
        return self.store_dir / submission_id

    def lock_target_for(self, submission_id: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""

        safe_repository_id(submission_id, context="submission_id")
        return self.store_dir / f"{submission_id}.lock"

    def load(self, submission_id: str) -> SubmittedFiling | None:
        """Return the persisted submission or ``None`` if absent."""

        safe_repository_id(submission_id, context="submission_id")
        record = self._objects.load(
            _SUBMISSION_NAMESPACE,
            submission_id,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_SUBMISSION_ENVELOPE_VERSION,
        )
        if record is None:
            _log.debug("submission object not found for id %s", submission_id)
            return None
        envelope = Envelope[SubmittedFiling].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.AUDIT:
            raise ClassificationError(
                f"submission {submission_id} has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.AUDIT}",
            )
        if envelope.schema_version > _SUBMISSION_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"submission {submission_id} is at version {envelope.schema_version}; "
                f"consumer supports up to {_SUBMISSION_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(self, filing: SubmittedFiling) -> None:
        """Persist ``filing`` in the encrypted database object store."""

        safe_repository_id(filing.submission_id, context="submission_id")
        envelope = Envelope[SubmittedFiling](
            schema_version=_SUBMISSION_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.AUDIT,
            payload=filing,
        )
        self._objects.save(
            namespace=_SUBMISSION_NAMESPACE,
            object_key=filing.submission_id,
            classification=SensitivityClass.AUDIT,
            schema_version=_SUBMISSION_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.info(
            "saved submission object for id %s modelo=%s status=%s",
            filing.submission_id,
            filing.modelo,
            filing.status,
        )

    def delete(self, submission_id: str) -> bool:
        """Remove the persisted submission for ``submission_id``."""

        safe_repository_id(submission_id, context="submission_id")
        deleted = self._objects.delete(_SUBMISSION_NAMESPACE, submission_id)
        if deleted:
            _log.info("deleted submission object for id %s", submission_id)
        return deleted

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository."""

        ids: list[str] = []
        for record in self._objects.list_records(
            _SUBMISSION_NAMESPACE,
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_SUBMISSION_ENVELOPE_VERSION,
        ):
            envelope = Envelope[SubmittedFiling].model_validate_json(record.payload.decode("utf-8"))
            ids.append(envelope.payload.submission_id)
        return tuple(sorted(ids))

    def iter_submissions(self) -> Iterator[SubmittedFiling]:
        """Yield every persisted submission, in lexicographic id order."""

        for submission_id in self.list_submission_ids():
            try:
                payload = self.load(submission_id)
            except (ClassificationError, EnvelopeVersionError):
                _log.warning(
                    "iter_submissions: skipping submission id=%s due to secure-object error",
                    submission_id,
                    exc_info=True,
                )
                continue
            if payload is not None:
                yield payload


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "SubmissionRepository",
]
