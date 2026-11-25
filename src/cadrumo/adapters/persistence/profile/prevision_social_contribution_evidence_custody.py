"""Attachment custody for the certificate bytes a pension contribution record rests on.

The record's ``evidence_fingerprint`` is the sha256 of the certificate held in
the profile's encrypted attachment custody. This adapter binds the family's
custody port to that existing store: it keeps a certificate's bytes through the
attachment service, which writes the content-addressed blob and its manifest,
and it answers whether a fingerprint still names intact bytes.

A blob that is missing, and a blob whose stored bytes no longer hash to the
address they are filed under, both answer "not held": the fingerprint then names
no evidence. A storage failure is never read as absence.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final, override

from ....application.aggregation.prevision_social_contribution_repository import (
    PrevisionSocialContributionEvidenceCustody,
    PrevisionSocialContributionPersistenceError,
)
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.errors import AttachmentNotFoundError, AttachmentPersistenceError, AttachmentValidationError
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ..storage.attachment import AttachmentStore
from ..storage.errors import STORED_RECORD_FAILURES

__all__ = ["PREVISION_SOCIAL_CERTIFICATE_ROLE", "PrevisionSocialContributionEvidenceCustodyAdapter"]

PREVISION_SOCIAL_CERTIFICATE_ROLE: Final = "prevision_social_contribution_certificate"
"""The manifest metadata value that marks a custody object as a pension contribution certificate."""

_SOURCE_COMMAND: Final = "aeat app ledger prevision-social record"


class PrevisionSocialContributionEvidenceCustodyAdapter(PrevisionSocialContributionEvidenceCustody):
    """Keep and check certificate bytes in one profile's encrypted attachment store."""

    def __init__(self, *, store: AttachmentStore, bucket_id: str) -> None:
        """Bind the profile's attachment store and the bucket its manifests belong to."""
        self._store = store
        self._bucket_id = bucket_id

    @override
    def holds(self, fingerprint: str) -> bool:
        """Return whether custody holds bytes that still hash to ``fingerprint``."""
        try:
            self._store.verify_blob(fingerprint)
        except (AttachmentNotFoundError, AttachmentValidationError):
            return False
        except (AttachmentPersistenceError, *STORED_RECORD_FAILURES) as exc:
            raise PrevisionSocialContributionPersistenceError("prevision_social_custody_holds") from exc
        return True

    def ingest(self, *, source_path: Path, data: bytes, mime_type: str, captured_at: datetime) -> str:
        """Keep ``data`` through the attachment service and return the sha256 it is addressed by."""
        try:
            attachment = add_attachment(
                self._store,
                content=AttachmentBytesContent(data=data),
                request=AttachmentIngestionRequest(
                    kind=AttachmentKind.OTHER,
                    source=AttachmentSource.LOCAL_FILE,
                    source_reference=str(source_path),
                    mime_type=mime_type,
                    captured_at=captured_at,
                    bucket_id=self._bucket_id,
                    source_command=_SOURCE_COMMAND,
                    metadata={"role": PREVISION_SOCIAL_CERTIFICATE_ROLE},
                ),
            )
        except (AttachmentPersistenceError, AttachmentValidationError, *STORED_RECORD_FAILURES) as exc:
            raise PrevisionSocialContributionPersistenceError("prevision_social_custody_ingest") from exc
        return attachment.attachment_id
