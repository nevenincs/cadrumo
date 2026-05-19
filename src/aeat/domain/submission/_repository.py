"""Governed-persistence repository for submitted-filing audit records.

Submitted filings capture uploaded payload bytes, AEAT responses, and
identity-bearing filing context. They are stored as encrypted byte
objects in the primary SQL backend at AUDIT sensitivity; no plaintext
submission JSON or envelope file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from ...adapters.persistence.storage import SensitivityClass
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...core.logging import get_logger
from ._models import SubmittedFiling

_log = get_logger(__name__)


class SubmissionRepository(SecureBoundRepository[SubmittedFiling]):
    """Repository over encrypted SQL-backed submitted filing records."""

    namespace: ClassVar[str] = "aeat.domain.submission.records"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[SubmittedFiling]] = SubmittedFiling

    def extract_identifier(self, payload: SubmittedFiling) -> str:
        return payload.submission_id

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository."""

        return tuple(self.iter_ids())

    def iter_submissions(self) -> Iterator[SubmittedFiling]:
        """Yield every persisted submission, in lexicographic id order.

        Audit-record enumeration is resilient: rows that fail
        classification or schema-version gates are logged and skipped
        rather than aborting the iteration. Diagnostic surfaces depend
        on listing all healthy submissions even when a single row is
        unreadable.
        """

        for submission_id in self.iter_ids():
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
