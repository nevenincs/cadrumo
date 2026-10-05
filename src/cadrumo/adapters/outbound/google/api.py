"""Shared Google API request execution with typed-error translation.

Both :mod:`adapters.outbound.google.calc_sheets_apply` and
:mod:`adapters.outbound.google.calc_sheets_pull` issue
``google-api-python-client`` requests. This module provides the single
:func:`~adapters.outbound.google.api.execute_request` boundary they route
through so transport failures, HTTP failures, and quota responses become the typed
:class:`~adapters.outbound.storage.errors.OutboundStorageError` hierarchy
instead of endpoint-specific ``HttpError`` strings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, NoReturn, Protocol, cast

from ....application.operator_actions.models import PreconditionVerdict
from ....application.operator_actions.preconditions import no_action_precondition_verdict
from ....core.google_http_error import google_http_status, google_quota_marker
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.type_guards import is_object_dict
from ..storage.errors import (
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
)
from ._preconditions import google_terminal_refusal
from .sign_in_state import ended_grant_refusal

if TYPE_CHECKING:
    import httplib2
    from google.auth.credentials import Credentials
    from googleapiclient._apis.drive.v3.resources import DriveResource
    from googleapiclient._apis.sheets.v4.resources import SheetsResource
    from googleapiclient.http import HttpMock

_GOOGLE_API_NUM_RETRIES = 3


class RequestRetryPolicy(StrEnum):
    """Whether a request may be re-sent after a transient failure.

    The Google client re-sends a request whose response was lost, so a retried
    create can apply twice. Every call names its policy; only a request whose
    repetition leaves the same remote state may be ``REPLAY_SAFE``.
    """

    REPLAY_SAFE = "replay_safe"
    SINGLE_ATTEMPT = "single_attempt"


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


def _refuse_missing_googleapiclient(
    exc: ImportError, *, service_name: str, version: str, condition_id: str
) -> NoReturn:
    """Refuse, naming the service, when the optional discovery client is absent."""
    error = OutboundStorageNetworkError(
        f"googleapiclient not importable: {exc}",
        translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
    )
    raise google_terminal_refusal(
        error,
        condition_id=condition_id,
        facts={
            "client_available": False,
            "dependency": "google_api_python_client",
            "service_name": service_name,
            "service_version": version,
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    ) from exc


# `google-api-python-client-stubs` types `build` per (service, version) LITERAL,
# so each service spells its own literals; only the import guard is shared. The
# caller names the terminal condition because each adapter owns its own closed
# condition set.
def drive_v3_service(credentials: Credentials, *, unavailable_condition_id: str) -> DriveResource:
    """Build the Drive v3 service, refusing when the optional client is not installed."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        _refuse_missing_googleapiclient(exc, service_name="drive", version="v3", condition_id=unavailable_condition_id)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def sheets_v4_service(credentials: Credentials, *, unavailable_condition_id: str) -> SheetsResource:
    """Build the Sheets v4 service, refusing when the optional client is not installed."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        _refuse_missing_googleapiclient(exc, service_name="sheets", version="v4", condition_id=unavailable_condition_id)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


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


def execute_request[ResponseBodyT](
    request: _ExecutableRequest[ResponseBodyT], *, action: str, retry: RequestRetryPolicy
) -> ResponseBodyT:
    """Execute a google-api-python-client request, translating failures.

    Runs ``request.execute`` with the client's transient-failure retries for a
    ``REPLAY_SAFE`` request and a single attempt for a ``SINGLE_ATTEMPT`` one,
    and returns the decoded JSON payload unchanged. A failed single attempt
    that carries no definitive HTTP refusal leaves the remote effect unknown;
    the resulting network error says so. HTTP 401/403 responses become
    :exc:`~adapters.outbound.storage.errors.OutboundStoragePermissionError`, HTTP
    404 responses become
    :exc:`~adapters.outbound.storage.errors.OutboundStorageNotFoundError`, HTTP
    429 responses and recognised Google quota markers become
    :exc:`~adapters.outbound.storage.errors.OutboundStorageQuotaError`, and every
    other transport or unmapped HTTP failure becomes
    :exc:`~adapters.outbound.storage.errors.OutboundStorageNetworkError`. A typed
    :exc:`~adapters.outbound.storage.errors.OutboundStorageError` raised by a
    nested call is re-raised unchanged so ownership and validation refusals are
    never re-wrapped as network errors. A credential refresh that Google
    answers by ending the grant becomes
    :exc:`~adapters.outbound.google.errors.GoogleAuthSignInRequiredError`; the
    request it was for has not taken effect, so no uncertainty is reported.

    Args:
        request: A google-api-python-client request object exposing
            ``execute()``.
        action: Stable action label used in error messages and context.
        retry: Whether the request may be re-sent after a transient failure.

    Returns:
        The deserialised API response payload.

    Raises:
        :exc:`~adapters.outbound.google.errors.GoogleAuthSignInRequiredError`:
            When Google reports the stored grant as revoked or expired.
        :exc:`~adapters.outbound.storage.errors.OutboundStorageError`: Re-raised
            unchanged when a nested call already raised a typed
            outbound-storage error.
        :exc:`~adapters.outbound.storage.errors.OutboundStoragePermissionError`:
            On HTTP 401 or 403 responses that are not quota refusals.
        :exc:`~adapters.outbound.storage.errors.OutboundStorageQuotaError`: On
            HTTP 429 responses or HTTP 403 responses carrying a recognised
            Google quota marker.
        :exc:`~adapters.outbound.storage.errors.OutboundStorageNotFoundError`: On
            HTTP 404 responses.
        :exc:`~adapters.outbound.storage.errors.OutboundStorageNetworkError`: On
            any other transport or unmapped HTTP failure.
    """
    try:
        result = request.execute(num_retries=_GOOGLE_API_NUM_RETRIES if retry is RequestRetryPolicy.REPLAY_SAFE else 0)
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
        ended_grant = ended_grant_refusal(exc, action=action)
        if ended_grant is not None:
            raise ended_grant from exc
        _raise_mapped_google_http_error(exc, action=action)
        effect_uncertain = retry is RequestRetryPolicy.SINGLE_ATTEMPT
        raise OutboundStorageNetworkError(
            f"Google {action} failed: {exc}",
            context={"action": action, "effect_uncertain": effect_uncertain},
            translated_message="adapters.google.calc_sheets.errors.api_call_failed",
            precondition_verdict=_external_verdict(
                "google.api.transport_unavailable",
                action=action,
                **({"effect_uncertain": True} if effect_uncertain else {}),
            ),
        ) from exc


def _raise_mapped_google_http_error(exc: Exception, *, action: str) -> None:
    """Raise the typed outbound-storage error matching a Google HTTP status, else return.

    Returns without raising when the failure is not an ``HttpError`` or carries no
    mapped status, leaving the caller to wrap it as a generic network failure.
    """
    from googleapiclient.errors import HttpError

    if not isinstance(exc, HttpError):
        return
    status = google_http_status(exc)
    quota_marker = google_quota_marker(exc)
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
