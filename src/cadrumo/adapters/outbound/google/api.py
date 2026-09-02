"""Shared Google API request execution with typed-error translation.

Both :mod:`adapters.outbound.google.calc_sheets_apply` and
:mod:`adapters.outbound.google.calc_sheets_pull` issue
``google-api-python-client`` requests. This module provides the single
:func:`~adapters.outbound.google.api.execute_request` boundary they route
through so transport failures, HTTP failures, and quota responses become the typed
:class:`~adapters.outbound.storage.OutboundStorageError` hierarchy
instead of endpoint-specific ``HttpError`` strings.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, cast

from ....application.operator_actions.models import PreconditionVerdict
from ....application.operator_actions.preconditions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.type_guards import is_object_dict, is_object_list
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


class _ExecutableRequest[ResponseBodyT](Protocol):
    """Structural type for google-api-python-client request objects.

    ``google-api-python-client-stubs`` types the concrete ``HttpRequest`` class.
    This protocol captures the part
    :func:`~adapters.outbound.google.api.execute_request` needs: the
    ``execute()`` method with optional ``http`` and ``num_retries`` parameters
    for Google client retry handling. The response body is a type parameter so a
    stub-typed request (whose ``execute`` returns a per-endpoint ``TypedDict``)
    keeps that precise type through :func:`execute_request` instead of widening
    to the untyped body. ``http`` mirrors ``HttpRequest.execute``'s
    own stub type (``httplib2.Http | HttpMock | None``) rather than a bare
    ``object`` so the real ``HttpRequest`` the production callers and tests
    construct satisfies this protocol structurally.
    """

    def execute(
        self,
        http: httplib2.Http | HttpMock | None = ...,
        num_retries: int = ...,
    ) -> ResponseBodyT: ...


def execute_request[ResponseBodyT](request: _ExecutableRequest[ResponseBodyT], *, action: str) -> ResponseBodyT:
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
        if not is_object_dict(result):
            raise OutboundStorageNetworkError(
                f"Google {action} returned a non-mapping response body",
                context={"action": action, "response_type": type(result).__name__},
                translated_message="adapters.google.calc_sheets.errors.api_call_failed",
                precondition_verdict=_external_verdict(
                    "google.api.response_not_mapping", action=action, response_type=type(result).__name__
                ),
            )
        return cast(ResponseBodyT, result)
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
    if not is_object_dict(payload):
        return None
    raw_error = payload.get("error")
    if not is_object_dict(raw_error):
        return None

    markers: list[str] = []
    status = raw_error.get("status")
    if isinstance(status, str):
        markers.append(status)

    errors = raw_error.get("errors")
    if is_object_list(errors):
        for entry in errors:
            if not is_object_dict(entry):
                continue
            reason = entry.get("reason")
            if isinstance(reason, str):
                markers.append(reason)

    details = raw_error.get("details")
    if is_object_list(details):
        for entry in details:
            if not is_object_dict(entry):
                continue
            reason = entry.get("reason")
            if isinstance(reason, str):
                markers.append(reason)

    return next((marker for marker in markers if marker in _RATE_LIMIT_MARKERS), None)
