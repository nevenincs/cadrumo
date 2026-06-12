"""Scope-compatible resolution of recorded document links.

A ledger row may carry recorded Gmail/Drive/URL document links (the offline
doclink feature stores the link reference as evidence metadata; it never fetches
the remote content). This resolver fetches the content **within the integration's
deliberate minimal-scope posture**: the granted ``drive.file`` scope lets the app
download Drive files it created or the operator explicitly picked, so a
``GOOGLE_DRIVE`` link to such a file resolves. Operator-external documents —
arbitrary Drive files (need ``drive.readonly``) and Gmail messages (need
``gmail.readonly``) — are **sensitive scopes the integration does not request**;
those links are refused with a typed, actionable error rather than silently
failing. Expanding to sensitive scopes is a security-posture decision (Google app
verification + re-consent), tracked separately.
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
    """Extract a Drive file id from a Drive URL or a bare id; ``None`` if absent."""
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
            suggestion="uv sync",
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
    """Resolve a recorded document link to its bytes, within the granted scopes.

    Args:
        source: The recorded link's :class:`AttachmentSource`.
        reference: The link reference (Drive URL / file id, Gmail link, or URL).
        credentials: Google OAuth credentials carrying the granted scopes.
        service: Optional pre-built Drive ``v3`` service. When ``None`` (the
            production path) the service is built from ``credentials``; tests
            inject a transport-only seam here so the fetch path runs without a
            live network or real credentials.

    Returns:
        The fetched document bytes (only for ``GOOGLE_DRIVE`` links the
        ``drive.file`` scope can reach).

    Raises:
        OutboundStoragePermissionError: For Gmail links and Drive files outside
            the ``drive.file`` scope — the required sensitive scope is named in
            the error ``context["required_scope"]``.
        OutboundStorageValidationError: For sources that are not remote documents
            or a Drive reference with no recognisable file id.
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
