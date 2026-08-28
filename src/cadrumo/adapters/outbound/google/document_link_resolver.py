"""Scope-compatible resolution of recorded document links.

Ledger evidence may start from a recorded
:class:`~domain.attachments.AttachmentSource` link, but the link is not
stored as evidence by itself.
:func:`~adapters.outbound.google.resolve_document_link` fetches reachable
Drive content as bytes so the caller can persist those bytes through
:func:`~domain.attachments.add_attachment`; the original link remains
provenance metadata on that byte-bearing attachment.
:func:`~adapters.outbound.google.list_drive_folder_documents` extends the
same minimal-scope posture to a *folder*: it lists the PDF/image children of a
``drive.file``-reachable folder so a caller can bulk-fetch every invoice in one
sweep instead of resolving one document link at a time.

The resolver stays inside the integration's deliberate minimal-scope posture:
``drive.file`` can download Drive files the app created or the operator picked,
so a ``GOOGLE_DRIVE`` reference to such a file resolves. Operator-external
documents, arbitrary Drive files that require ``drive.readonly``, and Gmail
messages that require ``gmail.readonly`` are refused with
:exc:`~adapters.outbound.storage.OutboundStoragePermissionError` instead
of being silently stored as links.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.external_constants import PDF_MIME_TYPE
from ....domain.attachments import AttachmentSource
from ..storage import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
    next_drive_page_token,
)
from ._api import execute_request
from ._preconditions import google_terminal_refusal

# .../d/<ID>/... (file, spreadsheets, document) | ...?id=<ID> | bare <ID>.
# The bare form requires >=25 chars so a hyphenated English token (e.g.
# "not-a-drive-reference") is not mistaken for a file id and sent to the network;
# real Drive ids are ~28-44 chars. The URL-embedded forms are unambiguous from
# context so they accept the shorter >=10.
_DRIVE_ID_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"/d/(?P<id>[A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=(?P<id>[A-Za-z0-9_-]{10,})"),
    re.compile(r"^(?P<id>[A-Za-z0-9_-]{25,})$"),
)

_GMAIL_SCOPE: Final[str] = "https://www.googleapis.com/auth/gmail.readonly"
_DRIVE_READONLY_SCOPE: Final[str] = "https://www.googleapis.com/auth/drive.readonly"

# The bulk folder sweep filters to the document kinds an invoice PDF/scan can
# take. This mirrors the CLI's ``_sniff_document_mime_type`` fallback set for
# consistency between the single-doclink and folder-sweep paths.
_INVOICE_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {PDF_MIME_TYPE, "image/png", "image/jpeg"},
)
_DRIVE_FOLDER_MIME_TYPE: Final[str] = "application/vnd.google-apps.folder"
_DRIVE_LIST_PAGE_SIZE: Final[int] = 100


class DocumentLinkPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the document-link adapter."""

    API_CLIENT_AVAILABLE = "google.document_link.api_client_available"
    REMOTE_SOURCE_SUPPORTED = "google.document_link.remote_source_supported"
    DRIVE_REFERENCE_IDENTIFIED = "google.document_link.drive_reference_identified"
    SOURCE_SCOPE_SUFFICIENT = "google.document_link.source_scope_sufficient"
    FILE_SCOPE_SUFFICIENT = "google.document_link.file_scope_sufficient"
    MEDIA_TRANSPORT_AVAILABLE = "google.document_link.media_transport_available"
    MEDIA_PAYLOAD_BYTES = "google.document_link.media_payload_bytes"
    FOLDER_SCOPE_SUFFICIENT = "google.document_link.folder_scope_sufficient"
    FOLDER_FILES_LIST_VALID = "google.document_link.folder_files_list_valid"
    FOLDER_ENTRY_VALID = "google.document_link.folder_entry_valid"
    FOLDER_PAGINATION_VALID = "google.document_link.folder_pagination_valid"


def _document_link_terminal_refusal(
    error: OutboundStorageError,
    condition: DocumentLinkPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> OutboundStorageError:
    """Return ``error``'s typed equivalent carrying this adapter's terminal verdict."""
    return google_terminal_refusal(
        error,
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


class _DriveMediaRequest(Protocol):
    def execute(self) -> object: ...


class _DriveFilesListRequest(Protocol):
    def execute(self, num_retries: int = ...) -> dict[str, Any]: ...


class _DriveFilesResource(Protocol):
    def get_media(self, *, fileId: str) -> _DriveMediaRequest: ...  # noqa: N803

    def list(
        self,
        *,
        q: str,
        fields: str,
        pageSize: int,  # noqa: N803
        pageToken: str = ...,  # noqa: N803
    ) -> _DriveFilesListRequest: ...


class _DriveService(Protocol):
    def files(self) -> _DriveFilesResource: ...


class DriveFolderDocument(BaseModel):
    """One PDF/image child of a ``drive.file``-reachable Drive folder.

    Returned by :func:`list_drive_folder_documents`; carries just enough
    metadata for a caller to fetch the file (:attr:`file_id`) and report it
    to the operator (:attr:`name`, :attr:`mime_type`).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    file_id: str = Field(validation_alias="id", min_length=1)
    name: str = Field(min_length=1)
    mime_type: str = Field(alias="mimeType", min_length=1)

    @field_validator("file_id", "name", "mime_type")
    @classmethod
    def _require_non_blank_wire_value(cls, value: str) -> str:
        """Reject blank Drive resource values before a listing can consume them."""
        if not value.strip():
            raise ValueError("must not be blank")
        return value


@dataclass(frozen=True)
class DriveFolderListing:
    """The result of listing one Drive folder's invoice-shaped children.

    ``documents`` carries the PDF/image files the sweep will fetch;
    ``skipped_non_document_count`` records how many folder children were
    filtered out for carrying a non-invoice MIME type (e.g. a nested folder
    or an unrelated file), so the caller can report an honest total.
    """

    documents: tuple[DriveFolderDocument, ...]
    skipped_non_document_count: int


def parse_drive_file_id(reference: str) -> str | None:
    """Extract the Drive file id consumed by :func:`~adapters.outbound.google.resolve_document_link`.

    Args:
        reference: A Drive URL, ``?id=...`` link, bare Drive file id, or
            non-Drive reference.

    Returns:
        The parsed Drive file id, or ``None`` when ``reference`` does not carry
        a recognisable Drive id.
    """
    candidate = reference.strip()
    for pattern in _DRIVE_ID_PATTERNS:
        match = pattern.search(candidate)
        if match:
            drive_id = match.group("id")
            if isinstance(drive_id, str):
                return drive_id
    return None


def _drive_service(credentials: object) -> _DriveService:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise _document_link_terminal_refusal(
            OutboundStorageNetworkError(
                "googleapiclient is not importable",
                context={"dependency": "google-api-python-client"},
            ),
            DocumentLinkPreconditionCondition.API_CLIENT_AVAILABLE,
            facts={"dependency": "google_api_python_client", "client_available": False},
            outcome=NoRecoveryOutcome.SAFETY,
        ) from exc

    # dynamic resource; the protocol pins the files().get_media().execute
    # surface used below.
    # CAST-RATIONALE-thirdparty: googleapiclient build() returns an untyped Resource
    return cast(_DriveService, build("drive", "v3", credentials=credentials, cache_discovery=False))


def resolve_document_link(
    *,
    source: AttachmentSource,
    reference: str,
    credentials: object,
    service: _DriveService | None = None,
) -> bytes:
    """Resolve a recorded :class:`~domain.attachments.AttachmentSource` link to bytes.

    Args:
        source: The recorded link source.
        reference: The link reference (Drive URL / file id, Gmail link, or URL).
        credentials: Google OAuth credentials carrying the granted scopes.
        service: Optional pre-built Drive ``v3`` service. When ``None`` (the
            production path) the service is built from ``credentials``; tests
            inject a transport-only seam here so the fetch path runs without a
            live network or real credentials.

    Returns:
        The fetched document bytes for ``GOOGLE_DRIVE`` links the ``drive.file``
        scope can reach.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStoragePermissionError`:
            For Gmail links, arbitrary URLs, and Drive files outside the
            ``drive.file`` scope. The required sensitive scope is named in
            ``context["required_scope"]``.
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`:
            For sources that are not remote documents, or a Drive reference
            with no recognisable file id.
    """
    if source is AttachmentSource.GMAIL:
        raise _document_link_terminal_refusal(
            OutboundStoragePermissionError(
                "Gmail document-link resolution requires the sensitive gmail.readonly scope, "
                "which this integration does not request",
                context={"required_scope": _GMAIL_SCOPE, "source": source.value},
            ),
            DocumentLinkPreconditionCondition.SOURCE_SCOPE_SUFFICIENT,
            facts={"source": source.value, "required_scope": _GMAIL_SCOPE, "scope_sufficient": False},
            outcome=NoRecoveryOutcome.SAFETY,
        )
    if source is AttachmentSource.GOOGLE_DRIVE:
        file_id = parse_drive_file_id(reference)
        if file_id is None:
            raise _document_link_terminal_refusal(
                OutboundStorageValidationError(
                    "Google Drive link does not contain a recognisable file id",
                    context={"reference": reference},
                ),
                DocumentLinkPreconditionCondition.DRIVE_REFERENCE_IDENTIFIED,
                facts={"source": source.value, "reference_identified": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            )
        drive_service = service if service is not None else _drive_service(credentials)
        return _download_drive_file_from_service(file_id, drive_service)
    if source is AttachmentSource.URL:
        raise _document_link_terminal_refusal(
            OutboundStoragePermissionError(
                "resolving an arbitrary external URL is outside the granted drive.file scope; "
                "it requires drive.readonly (for Drive content) or manual download",
                context={"required_scope": _DRIVE_READONLY_SCOPE, "source": source.value},
            ),
            DocumentLinkPreconditionCondition.SOURCE_SCOPE_SUFFICIENT,
            facts={"source": source.value, "required_scope": _DRIVE_READONLY_SCOPE, "scope_sufficient": False},
            outcome=NoRecoveryOutcome.SAFETY,
        )
    raise _document_link_terminal_refusal(
        OutboundStorageValidationError(
            f"document-link source {source.value!r} is not a resolvable remote document",
            context={"source": source.value},
        ),
        DocumentLinkPreconditionCondition.REMOTE_SOURCE_SUPPORTED,
        facts={"source": source.value, "remote_source_supported": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _download_drive_file_from_service(file_id: str, service: _DriveService) -> bytes:
    request = service.files().get_media(fileId=file_id)
    try:
        payload = request.execute()
    except OutboundStorageError:
        raise
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        # drive.file cannot see files the app did not create / the operator did
        # not pick — Google returns 403/404. Surface the scope-upgrade path.
        if status in (403, 404):
            raise _document_link_terminal_refusal(
                OutboundStoragePermissionError(
                    f"Drive file {file_id!r} is not reachable under the drive.file scope "
                    "(the app can only read files it created or the operator picked); "
                    "reading an arbitrary operator file requires drive.readonly",
                    context={"required_scope": _DRIVE_READONLY_SCOPE, "file_id": file_id},
                ),
                DocumentLinkPreconditionCondition.FILE_SCOPE_SUFFICIENT,
                facts={
                    "file_id": file_id,
                    "required_scope": _DRIVE_READONLY_SCOPE,
                    "status": str(status),
                    "scope_sufficient": False,
                },
                outcome=NoRecoveryOutcome.SAFETY,
            ) from exc
        raise _document_link_terminal_refusal(
            OutboundStorageNetworkError(
                "Drive files.get_media failed",
                context={"file_id": file_id, "status": str(status) if status is not None else "unknown"},
            ),
            DocumentLinkPreconditionCondition.MEDIA_TRANSPORT_AVAILABLE,
            facts={
                "file_id": file_id,
                "status": str(status) if status is not None else "unknown",
                "transport_available": False,
            },
            outcome=NoRecoveryOutcome.SAFETY,
        ) from exc
    if not isinstance(payload, (bytes, bytearray)):
        raise _document_link_terminal_refusal(
            OutboundStorageValidationError(
                "Drive files.get_media returned a non-bytes payload",
                context={"file_id": file_id},
            ),
            DocumentLinkPreconditionCondition.MEDIA_PAYLOAD_BYTES,
            facts={"file_id": file_id, "payload_bytes": False, "payload_type": type(payload).__name__},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    return bytes(payload)


def list_drive_folder_documents(
    *,
    folder_id: str,
    credentials: object,
    service: _DriveService | None = None,
) -> DriveFolderListing:
    """List the PDF/image children of a ``drive.file``-reachable Drive folder.

    Stays inside the same minimal-scope posture as
    :func:`resolve_document_link`: ``drive.file`` only lists files the app
    created or the operator explicitly picked, so a folder the operator has
    not shared with the app (or does not own under this scope) surfaces no
    children rather than a permission escalation. A non-existent or
    unreachable ``folder_id`` maps Google's 403/404 to the same
    :exc:`~adapters.outbound.storage.OutboundStoragePermissionError`
    scope-named refusal :func:`resolve_document_link` uses, so the two
    fetch surfaces read the same way.

    Args:
        folder_id: The Drive folder id (parsed the same way a document
            reference is via :func:`parse_drive_file_id`, or passed as a bare id).
        credentials: Google OAuth credentials carrying the granted scopes.
        service: Optional pre-built Drive ``v3`` service (test seam).

    Returns:
        A :class:`DriveFolderListing` naming every PDF/image child plus a
        count of filtered-out non-document children.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStoragePermissionError`:
            When the folder is not reachable under the ``drive.file`` scope.
        :exc:`~adapters.outbound.storage.OutboundStorageNetworkError`:
            On any other transport or unmapped Drive failure.
    """
    drive_service = service if service is not None else _drive_service(credentials)
    documents: list[DriveFolderDocument] = []
    skipped = 0
    for document in _iter_drive_folder_files(drive_service, folder_id=folder_id):
        mime_type = document.mime_type
        if mime_type == _DRIVE_FOLDER_MIME_TYPE:
            continue
        if mime_type not in _INVOICE_MIME_TYPES:
            skipped += 1
            continue
        documents.append(document)
    return DriveFolderListing(documents=tuple(documents), skipped_non_document_count=skipped)


def _iter_drive_folder_files(drive_service: _DriveService, *, folder_id: str) -> Iterator[DriveFolderDocument]:
    """Yield every raw Drive child of ``folder_id`` across pages, mapping scope refusals.

    A 403/404 (or any permission refusal without an already-named ``required_scope``)
    is remapped to the same ``drive.file``-scope refusal :func:`resolve_document_link`
    uses, so both fetch surfaces read identically.
    """
    query = f"'{folder_id}' in parents and trashed = false"
    page_token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        files = drive_service.files()
        if page_token is None:
            request = files.list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=_DRIVE_LIST_PAGE_SIZE,
            )
        else:
            request = files.list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=_DRIVE_LIST_PAGE_SIZE,
                pageToken=page_token,
            )
        try:
            response = execute_request(
                # CAST-RATIONALE-thirdparty: Google Drive SDK request object is untyped at the client boundary
                cast("Any", request),
                action="drive.files.list",
            )
        except OutboundStoragePermissionError as exc:
            context = dict(exc.context or {})
            if "required_scope" in context:
                raise
            raise _document_link_terminal_refusal(
                OutboundStoragePermissionError(
                    f"Drive folder {folder_id!r} is not reachable under the drive.file scope "
                    "(the app can only list files/folders it created or the operator picked); "
                    "reading an arbitrary operator folder requires drive.readonly",
                    context={"required_scope": _DRIVE_READONLY_SCOPE, "folder_id": folder_id, **context},
                ),
                DocumentLinkPreconditionCondition.FOLDER_SCOPE_SUFFICIENT,
                facts={"folder_id": folder_id, "required_scope": _DRIVE_READONLY_SCOPE, "scope_sufficient": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ) from exc
        # CAST-RATIONALE-thirdparty: Google Drive files-list is an untyped JSON API response
        raw_files = response.get("files", [])
        if not isinstance(raw_files, list):
            raise _document_link_terminal_refusal(
                OutboundStorageValidationError(
                    "Drive files.list returned a non-list files field",
                    context={"action": "drive.files.list", "folder_id": folder_id},
                ),
                DocumentLinkPreconditionCondition.FOLDER_FILES_LIST_VALID,
                facts={"folder_id": folder_id, "files_list_valid": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            )
        for entry_index, raw_file in enumerate(raw_files):
            yield _drive_folder_document_from_response(raw_file, folder_id=folder_id, entry_index=entry_index)
        # CAST-RATIONALE-thirdparty: Google Drive nextPageToken is an untyped JSON API response
        raw_page_token = response.get("nextPageToken")
        try:
            page_token = next_drive_page_token(
                raw_page_token,
                seen_tokens=seen_tokens,
                action="drive.files.list",
            )
        except OutboundStorageNetworkError as exc:
            token_state = "repeated" if isinstance(raw_page_token, str) else "non_string"
            raise _document_link_terminal_refusal(
                OutboundStorageValidationError(
                    "Drive files.list returned an invalid nextPageToken",
                    context={
                        "action": "drive.files.list",
                        "folder_id": folder_id,
                        "page_token_state": token_state,
                    },
                ),
                DocumentLinkPreconditionCondition.FOLDER_PAGINATION_VALID,
                facts={"folder_id": folder_id, "page_token_state": token_state, "page_token_valid": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ) from exc
        if not page_token:
            break


def _drive_folder_document_from_response(
    raw_file: object,
    *,
    folder_id: str,
    entry_index: int,
) -> DriveFolderDocument:
    """Validate a successful ``files.list`` row before callers classify it."""
    if not isinstance(raw_file, Mapping):
        raise _document_link_terminal_refusal(
            OutboundStorageValidationError(
                "Drive files.list returned a malformed file entry",
                context={"action": "drive.files.list", "folder_id": folder_id, "entry_index": str(entry_index)},
            ),
            DocumentLinkPreconditionCondition.FOLDER_ENTRY_VALID,
            facts={"folder_id": folder_id, "entry_index": entry_index, "entry_mapping": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    try:
        return DriveFolderDocument.model_validate(raw_file)
    except ValidationError as exc:
        raise _document_link_terminal_refusal(
            OutboundStorageValidationError(
                "Drive files.list returned a malformed file entry",
                context={"action": "drive.files.list", "folder_id": folder_id, "entry_index": str(entry_index)},
            ),
            DocumentLinkPreconditionCondition.FOLDER_ENTRY_VALID,
            facts={"folder_id": folder_id, "entry_index": entry_index, "entry_mapping": True},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc


__all__ = [
    "DriveFolderDocument",
    "DriveFolderListing",
    "list_drive_folder_documents",
    "parse_drive_file_id",
    "resolve_document_link",
]
