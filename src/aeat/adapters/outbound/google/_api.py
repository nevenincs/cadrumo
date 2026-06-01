"""Shared Google API request execution with typed-error translation.

Both the export/apply adapter and the pull adapter issue
google-api-python-client requests and must translate transport and
HTTP failures into the typed ``OutboundStorage*`` hierarchy. This module
holds the single canonical ``_execute`` they both route through.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict

from ...outbound.storage._errors import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
)


class _ExecutableRequest(Protocol):
    """Structural type for google-api-python-client request objects.

    ``google-api-python-client-stubs`` types the concrete
    ``HttpRequest`` class; any object with an ``execute()`` callable
    satisfies this protocol, which keeps the adapter decoupled from
    the concrete stub type while still narrowing away bare ``Any``.
    """

    def execute(self, http: object = None, num_retries: int = 0) -> Any: ...


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

    Covers the fields used by the calc-sheets adapter; additional fields
    returned by the API are silently ignored by TypedDict consumers.
    See https://developers.google.com/drive/api/reference/rest/v3/files.
    """

    name: str
    mimeType: str
    parents: list[str]
    webViewLink: str
    owners: list[dict[str, Any]]


class _GoogleSheetsRangeRequired(TypedDict):
    """Required fields for a Sheets ValueRange resource."""

    range: str


class GoogleSheetsRange(_GoogleSheetsRangeRequired, total=False):
    """Typed shape for a Sheets ``ValueRange`` resource.

    Covers fields returned by ``spreadsheets.values.get`` and
    ``spreadsheets.values.update``.
    See https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values.
    """

    majorDimension: str
    values: list[list[Any]]
    updatedRange: str
    updatedRows: int
    updatedColumns: int
    updatedCells: int


class _GoogleSpreadsheetRequired(TypedDict):
    """Required fields for a Sheets Spreadsheet resource."""

    spreadsheetId: str


class GoogleSpreadsheet(_GoogleSpreadsheetRequired, total=False):
    """Typed shape for a Sheets ``Spreadsheet`` resource.

    Covers top-level fields returned by ``spreadsheets.get``.
    See https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.
    """

    spreadsheetUrl: str
    properties: dict[str, Any]
    sheets: list[dict[str, Any]]


def execute_request(request: _ExecutableRequest, *, action: str) -> GoogleApiResponseBody:
    """Execute a google-api-python-client request, translating failures.

    HTTP 401/403 become :class:`OutboundStoragePermissionError`, HTTP 404
    becomes :class:`OutboundStorageNotFoundError`, and every other
    transport or unmapped HTTP failure becomes
    :class:`OutboundStorageNetworkError`. A typed ``OutboundStorageError``
    raised by a nested call (e.g. an ownership-verification refusal) is
    re-raised unchanged so it is never re-wrapped as a network error.

    Args:
        request: A google-api-python-client request object exposing
            ``execute()``.
        action: Stable action label used in error messages and context.

    Returns:
        The deserialised API response payload.

    Raises:
        OutboundStorageError: Re-raised unchanged when a nested call already raised a typed error.
        OutboundStoragePermissionError: On HTTP 401 or 403 responses.
        OutboundStorageNotFoundError: On HTTP 404 responses.
        OutboundStorageNetworkError: On any other transport or unmapped HTTP failure.
    """
    try:
        result: GoogleApiResponseBody = request.execute()
        return result
    except OutboundStorageError:
        raise
    except Exception as exc:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
            if status in (401, 403):
                raise OutboundStoragePermissionError(
                    f"Google {action} refused (HTTP {status}): {exc}",
                    suggestion="aeat config google login",
                    context={"action": action, "status": status},
                    translated_message="adapters.google.calc_sheets.errors.api_call_refused",
                ) from exc
            if status == 404:
                raise OutboundStorageNotFoundError(
                    f"Google {action} target not found (HTTP 404): {exc}",
                    context={"action": action},
                    translated_message="adapters.google.calc_sheets.errors.api_target_not_found",
                ) from exc
        raise OutboundStorageNetworkError(
            f"Google {action} failed: {exc}",
            context={"action": action},
            translated_message="adapters.google.calc_sheets.errors.api_call_failed",
        ) from exc
