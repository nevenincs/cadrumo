"""Shared Google API request execution with typed-error translation.

Both the export/apply adapter and the pull adapter issue
google-api-python-client requests and must translate transport and
HTTP failures into the typed ``OutboundStorage*`` hierarchy. This module
holds the single canonical ``_execute`` they both route through.
"""

from __future__ import annotations

from typing import Any, Protocol

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

    def execute(self, http: object = None, num_retries: int = 0) -> Any: ...  # noqa: D102


# The google-api-python-client wire protocol returns JSON-decoded dicts whose
# exact shape varies per endpoint. A TypedDict alias per endpoint would be
# overly rigid here because the same helper routes dozens of distinct calls.
# We name the return type explicitly so call-sites document what they expect,
# even though the container is still a plain dict at runtime.
GoogleApiResponseBody = dict[str, Any]


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
