"""Shared Google API request execution with typed-error translation.

Both :mod:`adapters.outbound.google.calc_sheets_apply` and
:mod:`adapters.outbound.google.calc_sheets_pull` issue
``google-api-python-client`` requests. This module provides the single
:func:`~adapters.outbound.google.api.execute_request` boundary they route
through so transport failures, HTTP failures, and quota responses become the typed
:class:`~adapters.outbound.storage.OutboundStorageError` hierarchy
instead of endpoint-specific ``HttpError`` strings.

See Also:
    :class:`~adapters.outbound.google.api.GoogleDriveFile`,
    :class:`~adapters.outbound.google.api.GoogleSheetsRange`, and
    :class:`~adapters.outbound.google.api.GoogleSpreadsheet` document the
    shared response shapes the calc Sheets adapters cast at their call sites.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from ....application.operator_actions._models import PreconditionVerdict
from ....application.operator_actions._preconditions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..storage.errors import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
)

if TYPE_CHECKING:
    import httplib2
    from googleapiclient.http import HttpMock

_GOOGLE_API_NUM_RETRIES = 3
_RATE_LIMIT_MARKERS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "RATE_LIMIT_EXCEEDED",
    "RESOURCE_EXHAUSTED",
}


def _external_verdict(condition_id: str, **facts: object) -> PreconditionVerdict:
    """Build one API-owned terminal verdict."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts={
            ("operation" if key == "action" else key): value
            for key, value in facts.items()
            if isinstance(value, (str, int, bool))
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=(
            NoRecoveryOutcome.SAFETY
            if condition_id != "google.api.target_not_found"
            else NoRecoveryOutcome.OPERATOR_DECISION
        ),
    )


class _ExecutableRequest(Protocol):
    """Structural type for google-api-python-client request objects.

    ``google-api-python-client-stubs`` types the concrete ``HttpRequest`` class.
    This protocol captures the part
    :func:`~adapters.outbound.google.api.execute_request` needs: the
    ``execute()`` method with optional ``http`` and ``num_retries`` parameters
    for Google client retry handling. ``http`` mirrors ``HttpRequest.execute``'s
    own stub type (``httplib2.Http | HttpMock | None``) rather than a bare
    ``object`` so the real ``HttpRequest`` the production callers and tests
    construct satisfies this protocol structurally.
    """

    def execute(
        self,
        http: httplib2.Http | HttpMock | None = ...,
        num_retries: int = ...,
    ) -> GoogleApiResponseBody: ...


# The google-api-python-client wire protocol returns JSON-decoded dicts whose
# exact shape varies per endpoint. The single ``execute_request`` helper routes
# dozens of distinct calls, so its return type cannot be narrowed to a single
# TypedDict without a per-endpoint overload explosion. Call-sites annotate their
# local variables with the appropriate typed shape below and cast once at the
# boundary; the cast is documented here as the intentional type-system escape.
# CAST-RATIONALE-GOOGLE-API-RESPONSE: google-api-python-client returns
# ``dict[str, Any]`` from ``execute()``. The TypedDicts below make the
# expected shape explicit at each call-site; a single ``cast`` at the
# assignment narrows the type without repeating the escape everywhere.
GoogleApiResponseBody = dict[str, Any]


class _GoogleDriveFileRequired(TypedDict):
    """Required fields for a Google Drive Files resource response."""

    id: str


class GoogleDriveFile(_GoogleDriveFileRequired, total=False):
    """Typed shape for a Google Drive Files resource response.

    Covers the file metadata fields consumed by
    :mod:`adapters.outbound.google.calc_sheets_apply` and
    :mod:`adapters.outbound.google.calc_sheets_pull`. Additional fields
    returned by Drive are ignored by :class:`typing.TypedDict` consumers.

    See https://developers.google.com/drive/api/reference/rest/v3/files.
    """

    name: str
    mimeType: str
    parents: list[str]
    webViewLink: str
    owners: list[dict[str, Any]]


class _GoogleSheetsRangeRequired(TypedDict):
    """Required fields for a Sheets ``ValueRange`` resource."""

    range: str


class GoogleSheetsRange(_GoogleSheetsRangeRequired, total=False):
    """Typed shape for a Sheets ``ValueRange`` resource.

    Covers fields returned by ``spreadsheets.values.get`` and
    ``spreadsheets.values.update`` through
    :func:`~adapters.outbound.google.api.execute_request`.

    See https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values.
    """

    majorDimension: str
    values: list[list[Any]]
    updatedRange: str
    updatedRows: int
    updatedColumns: int
    updatedCells: int


class _GoogleSpreadsheetRequired(TypedDict):
    """Required fields for a Sheets ``Spreadsheet`` resource."""

    spreadsheetId: str


class GoogleSpreadsheet(_GoogleSpreadsheetRequired, total=False):
    """Typed shape for a Sheets ``Spreadsheet`` resource.

    Covers top-level fields returned by ``spreadsheets.get`` through
    :func:`~adapters.outbound.google.api.execute_request`.

    See https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.
    """

    spreadsheetUrl: str
    properties: dict[str, Any]
    sheets: list[dict[str, Any]]


def execute_request(request: _ExecutableRequest, *, action: str) -> GoogleApiResponseBody:
    """Execute a google-api-python-client request, translating failures.

    Runs ``request.execute(num_retries=3)`` and returns the decoded JSON
    payload unchanged. HTTP 401/403 responses become
    :exc:`~adapters.outbound.storage.OutboundStoragePermissionError`, HTTP
    404 responses become
    :exc:`~adapters.outbound.storage.OutboundStorageNotFoundError`, HTTP
    429 responses and recognised Google quota markers become
    :exc:`~adapters.outbound.storage.OutboundStorageQuotaError`, and every
    other transport or unmapped HTTP failure becomes
    :exc:`~adapters.outbound.storage.OutboundStorageNetworkError`. A typed
    :exc:`~adapters.outbound.storage.OutboundStorageError` raised by a
    nested call is re-raised unchanged so ownership and validation refusals are
    never re-wrapped as network errors.

    Args:
        request: A google-api-python-client request object exposing
            ``execute()``.
        action: Stable action label used in error messages and context.

    Returns:
        The deserialised API response payload.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageError`: Re-raised
            unchanged when a nested call already raised a typed
            outbound-storage error.
        :exc:`~adapters.outbound.storage.OutboundStoragePermissionError`:
            On HTTP 401 or 403 responses that are not quota refusals.
        :exc:`~adapters.outbound.storage.OutboundStorageQuotaError`: On
            HTTP 429 responses or HTTP 403 responses carrying a recognised
            Google quota marker.
        :exc:`~adapters.outbound.storage.OutboundStorageNotFoundError`: On
            HTTP 404 responses.
        :exc:`~adapters.outbound.storage.OutboundStorageNetworkError`: On
            any other transport or unmapped HTTP failure.
    """
    try:
        result = request.execute(num_retries=_GOOGLE_API_NUM_RETRIES)
        if not isinstance(result, dict):
            raise OutboundStorageNetworkError(
                f"Google {action} returned a non-mapping response body",
                context={"action": action, "response_type": type(result).__name__},
                translated_message="adapters.google.calc_sheets.errors.api_call_failed",
                precondition_verdict=_external_verdict(
                    "google.api.response_not_mapping", action=action, response_type=type(result).__name__
                ),
            )
        return result
    except OutboundStorageError:
        raise
    except Exception as exc:
        _raise_mapped_google_http_error(exc, action=action)
        raise OutboundStorageNetworkError(
            f"Google {action} failed: {exc}",
            context={"action": action},
            translated_message="adapters.google.calc_sheets.errors.api_call_failed",
            precondition_verdict=_external_verdict("google.api.transport_unavailable", action=action),
        ) from exc


def _raise_mapped_google_http_error(exc: Exception, *, action: str) -> None:
    """Raise the typed outbound-storage error matching a Google HTTP status, else return.

    Returns without raising when the failure is not an ``HttpError`` or carries no
    mapped status, leaving the caller to wrap it as a generic network failure.
    """
    from googleapiclient.errors import HttpError

    if not isinstance(exc, HttpError):
        return
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
    quota_marker = _quota_marker(exc)
    if status == 429 or (status == 403 and quota_marker is not None):
        raise OutboundStorageQuotaError(
            f"Google {action} exhausted quota (HTTP {status}): {exc}",
            context={"action": action, "status": status, "quota_marker": quota_marker or "HTTP_429"},
            translated_message="errors.refused.refused_outbound_storage_quota",
            precondition_verdict=_external_verdict(
                "google.api.quota_exhausted",
                action=action,
                status=status,
                quota_marker=quota_marker or "HTTP_429",
            ),
        ) from exc
    if status in (401, 403):
        raise OutboundStoragePermissionError(
            f"Google {action} refused (HTTP {status}): {exc}",
            context={"action": action, "status": status},
            translated_message="adapters.google.calc_sheets.errors.api_call_refused",
            precondition_verdict=_external_verdict("google.api.permission_denied", action=action, status=status),
        ) from exc
    if status == 404:
        raise OutboundStorageNotFoundError(
            f"Google {action} target not found (HTTP 404): {exc}",
            context={"action": action},
            translated_message="adapters.google.calc_sheets.errors.api_target_not_found",
            precondition_verdict=_external_verdict("google.api.target_not_found", action=action),
        ) from exc


def _quota_marker(error: Exception) -> str | None:
    """Return a recognised quota marker from a Google ``HttpError`` payload.

    Google may signal quota exhaustion through an HTTP 429 status, a 403 with
    ``error.status=RESOURCE_EXHAUSTED``, or nested ``reason`` fields such as
    ``rateLimitExceeded``.
    :func:`~adapters.outbound.google.api.execute_request` uses this helper
    to route those 403 responses to
    :exc:`~adapters.outbound.storage.OutboundStorageQuotaError` instead of
    the generic permission refusal.
    """
    content = getattr(error, "content", b"")
    body = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_error = payload.get("error")
    if not isinstance(raw_error, dict):
        return None

    markers: list[str] = []
    status = raw_error.get("status")
    if isinstance(status, str):
        markers.append(status)

    errors = raw_error.get("errors")
    if isinstance(errors, list):
        for entry in errors:
            if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
                markers.append(entry["reason"])

    details = raw_error.get("details")
    if isinstance(details, list):
        for entry in details:
            if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
                markers.append(entry["reason"])

    return next((marker for marker in markers if marker in _RATE_LIMIT_MARKERS), None)
