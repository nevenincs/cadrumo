"""Canonical Drive evidence acquisition with per-request worker admission.

This module translates provider bytes/metadata only. Custody and ledger effects
remain application/domain policy, and credentials never leave this adapter.
"""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from ....application.ledger.evidence_ingestion_operation_ports import EvidenceAcquisitionListing
from ....application.ledger.evidence_sweep_ports import EvidenceSweepDocument, EvidenceSweepFileNotReachableError
from ....core.external_constants import PDF_MIME_TYPE
from ....domain.attachments.enums import AttachmentSource
from ..storage.errors import OutboundStoragePermissionError, OutboundStorageValidationError
from ..storage.factory import build_google_credentials
from .document_link_resolver import list_drive_folder_documents, parse_drive_file_id, resolve_document_link

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

_DRIVE_FOLDER_URL = re.compile(r"/folders/(?P<id>[A-Za-z0-9_-]{10,})")


def sniff_document_mime_type(reference: str, data: bytes) -> str:
    """Retain the existing evidence provenance sniff and filename fallback."""
    if data.startswith(b"%PDF-"):
        return PDF_MIME_TYPE
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    guessed, _ = mimetypes.guess_type(reference)
    return guessed or "application/octet-stream"


def parse_drive_folder_reference(reference: str) -> str:
    """Resolve the existing folder URL grammar or canonical bare Drive ID."""
    match = _DRIVE_FOLDER_URL.search(reference.strip())
    folder_id = str(match.group("id")) if match is not None else parse_drive_file_id(reference)
    if folder_id is None:
        raise OutboundStorageValidationError(
            translated_message="cli.app.ledger.evidence.pull_all_errors.folder_id_unrecognised",
            context={"reference": reference},
        )
    return folder_id


class DriveEvidenceAcquisition:
    """Lazy credentials for one exact profile, admitted before each outbound call."""

    def __init__(self, *, profile_id: UUID, before_read: Callable[[], None]) -> None:
        """Retain a profile identity without credential discovery or provider I/O."""
        self._profile_id = profile_id
        self._before_read = before_read
        self._credentials: Credentials | None = None

    def _admitted_credentials(self) -> Credentials:
        self._before_read()
        if self._credentials is None:
            self._credentials = build_google_credentials(profile=str(self._profile_id))
        return self._credentials

    def fetch(self, *, source: AttachmentSource, reference: str) -> bytes:
        """Reuse the scope-preserving canonical document byte resolver."""
        credentials = self._admitted_credentials()
        return resolve_document_link(
            source=source, reference=reference, credentials=credentials, before_request=self._before_read
        )

    def list_folder(self, reference: str) -> EvidenceAcquisitionListing:
        """Reuse canonical ordered pagination under renewed request authority."""
        folder_id = parse_drive_folder_reference(reference)
        credentials = self._admitted_credentials()
        listing = list_drive_folder_documents(
            folder_id=folder_id, credentials=credentials, before_request=self._before_read
        )
        return EvidenceAcquisitionListing(
            folder_id=folder_id,
            documents=tuple(
                EvidenceSweepDocument(file_id=row.file_id, name=row.name, mime_type=row.mime_type)
                for row in listing.documents
            ),
            skipped_non_document_count=listing.skipped_non_document_count,
        )

    def fetch_folder_document(self, document: EvidenceSweepDocument) -> bytes:
        """Translate exactly the canonical per-file permission refusal."""
        try:
            return self.fetch(
                source=AttachmentSource.GOOGLE_DRIVE, reference=f"https://drive.google.com/file/d/{document.file_id}"
            )
        except OutboundStoragePermissionError as error:
            raise EvidenceSweepFileNotReachableError from error

    def mime_type(self, reference: str, data: bytes) -> str:
        """Return the existing provenance MIME without introducing a byte gate."""
        return sniff_document_mime_type(reference, data)
