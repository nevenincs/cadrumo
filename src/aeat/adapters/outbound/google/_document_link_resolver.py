"""Scope-compatible resolution of recorded document links.

Ledger evidence may start from a recorded :class:`AttachmentSource` link, but
the link is not stored as evidence by itself. :func:`resolve_document_link`
fetches reachable Drive content as bytes so the caller can persist those bytes
through :func:`aeat.domain.attachments.add_attachment_bytes`; the original link
remains provenance metadata on that byte-bearing attachment.

The resolver stays inside the integration's deliberate minimal-scope posture:
``drive.file`` can download Drive files the app created or the operator picked,
so a ``GOOGLE_DRIVE`` reference to such a file resolves. Operator-external
documents, arbitrary Drive files that require ``drive.readonly``, and Gmail
messages that require ``gmail.readonly`` are refused with
:class:`OutboundStoragePermissionError` instead of being silently stored as
links.
"""

from __future__ import annotations

import re
from typing import Final, Protocol, cast

from ....domain.attachments import AttachmentSource
from ...outbound.storage._errors import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)

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


class _DriveMediaRequest(Protocol):
    def execute(self) -> object: ...


class _DriveFilesResource(Protocol):
    def get_media(self, *, fileId: str) -> _DriveMediaRequest: ...  # noqa: N803


class _DriveService(Protocol):
    def files(self) -> _DriveFilesResource: ...


def parse_drive_file_id(reference: str) -> str | None:
    """Extract the Drive file id consumed by :func:`resolve_document_link`.

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
            return match.group("id")
    return None


def _drive_service(credentials: object) -> _DriveService:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            "googleapiclient is not importable",
            context={"dependency": "google-api-python-client"},
            suggestion="pip install aeat[google]",
        ) from exc
    # CAST-RATIONALE-GOOGLE-DRIVE-SERVICE: googleapiclient.build returns a
    # dynamic resource; the protocol pins the files().get_media().execute
    # surface used below.
    return cast(_DriveService, build("drive", "v3", credentials=credentials, cache_discovery=False))


def resolve_document_link(
    *,
    source: AttachmentSource,
    reference: str,
    credentials: object,
    service: _DriveService | None = None,
) -> bytes:
    """Resolve a recorded :class:`AttachmentSource` link to bytes.

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
        :class:`OutboundStoragePermissionError`: For Gmail links, arbitrary
            URLs, and Drive files outside the ``drive.file`` scope. The
            required sensitive scope is named in ``context["required_scope"]``.
        :class:`OutboundStorageValidationError`: For sources that are not
            remote documents, or a Drive reference with no recognisable file id.
    """
    if source is AttachmentSource.GMAIL:
        raise OutboundStoragePermissionError(
            "Gmail document-link resolution requires the sensitive gmail.readonly scope, "
            "which this integration does not request",
            context={"required_scope": _GMAIL_SCOPE, "source": source.value},
        )
    if source is AttachmentSource.GOOGLE_DRIVE:
        file_id = parse_drive_file_id(reference)
        if file_id is None:
            raise OutboundStorageValidationError(
                "Google Drive link does not contain a recognisable file id",
                context={"reference": reference},
            )
        drive_service = service if service is not None else _drive_service(credentials)
        return _download_drive_file_from_service(file_id, drive_service)
    if source is AttachmentSource.URL:
        raise OutboundStoragePermissionError(
            "resolving an arbitrary external URL is outside the granted drive.file scope; "
            "it requires drive.readonly (for Drive content) or manual download",
            context={"required_scope": _DRIVE_READONLY_SCOPE, "source": source.value},
        )
    raise OutboundStorageValidationError(
        f"document-link source {source.value!r} is not a resolvable remote document",
        context={"source": source.value},
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
            raise OutboundStoragePermissionError(
                f"Drive file {file_id!r} is not reachable under the drive.file scope "
                "(the app can only read files it created or the operator picked); "
                "reading an arbitrary operator file requires drive.readonly",
                context={"required_scope": _DRIVE_READONLY_SCOPE, "file_id": file_id},
            ) from exc
        raise OutboundStorageNetworkError(
            "Drive files.get_media failed",
            context={"file_id": file_id, "status": str(status) if status is not None else "unknown"},
        ) from exc
    if not isinstance(payload, (bytes, bytearray)):
        raise OutboundStorageNetworkError(
            "Drive files.get_media returned a non-bytes payload",
            context={"file_id": file_id},
        )
    return bytes(payload)


__all__ = [
    "parse_drive_file_id",
    "resolve_document_link",
]
