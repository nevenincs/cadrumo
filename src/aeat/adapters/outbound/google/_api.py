"""Shared Google API request execution with typed-error translation.

Both the export/apply adapter and the pull adapter issue
google-api-python-client requests and must translate transport and
HTTP failures into the typed ``OutboundStorage*`` hierarchy. This module
holds the single canonical ``_execute`` they both route through.
"""

from __future__ import annotations

from typing import Any

from ...outbound.storage._errors import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
)


def execute_request(request: Any, *, action: str) -> Any:
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
    """
    try:
        return request.execute()
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
