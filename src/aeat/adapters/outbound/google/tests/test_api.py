"""Real-behavior tests for the Google API request executor.

Exercises :func:`execute_request` end-to-end using a minimal concrete
object that satisfies the ``_ExecutableRequest`` protocol — no mocks,
no patches.  The tests verify the typed response shape, HTTP error
translation, and the re-raise contract for nested
``OutboundStorage*`` errors.
"""

from __future__ import annotations

import pytest

from .....adapters.outbound.storage._errors import (
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
)
from .._api import GoogleApiResponseBody, _ExecutableRequest, execute_request

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


# ---------------------------------------------------------------------------
# Minimal concrete request objects that satisfy _ExecutableRequest
# ---------------------------------------------------------------------------


class _SuccessRequest:
    """Returns a fixed payload dict from execute()."""

    def __init__(self, payload: GoogleApiResponseBody) -> None:
        self._payload = payload

    def execute(self, http: object = None, num_retries: int = 0) -> GoogleApiResponseBody:
        return self._payload


class _RaisingRequest:
    """Raises the supplied exception from execute()."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def execute(self, http: object = None, num_retries: int = 0) -> GoogleApiResponseBody:
        raise self._exc


class _RetryRecordingRequest:
    """Records the retry count passed through the Google request boundary."""

    def __init__(self, payload: GoogleApiResponseBody) -> None:
        self._payload = payload
        self.seen_num_retries: int | None = None

    def execute(self, http: object = None, num_retries: int = 0) -> GoogleApiResponseBody:
        self.seen_num_retries = num_retries
        return self._payload


# ---------------------------------------------------------------------------
# Protocol structural check
# ---------------------------------------------------------------------------


def test_executable_request_protocol_accepts_concrete_impl() -> None:
    """_SuccessRequest satisfies the _ExecutableRequest Protocol structurally."""

    # This is a runtime isinstance check using runtime_checkable would need
    # @runtime_checkable.  Instead assert that execute_request accepts it
    # without raising a TypeError — the call itself exercises the protocol.
    req: _ExecutableRequest = _SuccessRequest({"spreadsheetId": "x"})
    result = execute_request(req, action="test.check")
    assert result == {"spreadsheetId": "x"}


# ---------------------------------------------------------------------------
# Response shape is GoogleApiResponseBody (dict[str, Any])
# ---------------------------------------------------------------------------


def test_execute_request_returns_dict_typed_as_google_api_response_body() -> None:
    """execute_request returns a GoogleApiResponseBody (dict[str, Any])."""

    payload: GoogleApiResponseBody = {"kind": "drive#file", "id": "abc123"}
    req = _SuccessRequest(payload)
    result = execute_request(req, action="drive.files.get")

    assert isinstance(result, dict)
    assert result["id"] == "abc123"
    assert result["kind"] == "drive#file"


def test_execute_request_passes_nested_dict_payload_intact() -> None:
    """Nested dicts in the response survive the execute_request boundary."""

    payload: GoogleApiResponseBody = {"developerMetadata": [{"metadataKey": "aeat_vault_app", "metadataValue": "aeat"}]}
    req = _SuccessRequest(payload)
    result = execute_request(req, action="sheets.spreadsheets.get")

    assert result["developerMetadata"][0]["metadataKey"] == "aeat_vault_app"


def test_execute_request_enables_google_client_retries() -> None:
    """Requests run through google-api-python-client retry handling."""

    req = _RetryRecordingRequest({"spreadsheetId": "retry-check"})
    result = execute_request(req, action="sheets.spreadsheets.get")

    assert result["spreadsheetId"] == "retry-check"
    assert req.seen_num_retries == 3


# ---------------------------------------------------------------------------
# HTTP error translation
# ---------------------------------------------------------------------------


def _make_http_error(status: int, content: bytes = b"error") -> Exception:
    """Build a minimal googleapiclient.errors.HttpError-shaped exception."""

    import httplib2
    from googleapiclient.errors import HttpError

    response = httplib2.Response({"status": str(status), "reason": "test"})
    return HttpError(resp=response, content=content)


def test_http_401_translates_to_permission_error() -> None:
    req = _RaisingRequest(_make_http_error(401))
    with pytest.raises(OutboundStoragePermissionError):
        execute_request(req, action="drive.files.get")


def test_http_403_translates_to_permission_error() -> None:
    req = _RaisingRequest(_make_http_error(403))
    with pytest.raises(OutboundStoragePermissionError):
        execute_request(req, action="drive.files.get")


def test_http_403_rate_limit_translates_to_quota_error() -> None:
    content = (
        b'{"error":{"code":403,"message":"quota","errors":[{"reason":"rateLimitExceeded"}],'
        b'"status":"RESOURCE_EXHAUSTED"}}'
    )
    req = _RaisingRequest(_make_http_error(403, content=content))
    with pytest.raises(OutboundStorageQuotaError):
        execute_request(req, action="sheets.spreadsheets.get")


def test_http_429_translates_to_quota_error() -> None:
    req = _RaisingRequest(_make_http_error(429))
    with pytest.raises(OutboundStorageQuotaError):
        execute_request(req, action="sheets.spreadsheets.get")


def test_http_404_translates_to_not_found_error() -> None:
    req = _RaisingRequest(_make_http_error(404))
    with pytest.raises(OutboundStorageNotFoundError):
        execute_request(req, action="drive.files.get")


def test_http_500_translates_to_network_error() -> None:
    req = _RaisingRequest(_make_http_error(500))
    with pytest.raises(OutboundStorageNetworkError):
        execute_request(req, action="drive.files.get")


def test_generic_exception_translates_to_network_error() -> None:
    req = _RaisingRequest(ConnectionError("timeout"))
    with pytest.raises(OutboundStorageNetworkError):
        execute_request(req, action="sheets.values.batchGet")


# ---------------------------------------------------------------------------
# Nested OutboundStorageError re-raise contract
# ---------------------------------------------------------------------------


def test_outbound_storage_error_is_not_re_wrapped() -> None:
    """OutboundStorageError raised inside execute() must propagate unchanged."""

    inner = OutboundStorageNetworkError(
        "already typed",
        translated_message="adapters.google.calc_sheets.errors.api_call_failed",
    )
    req = _RaisingRequest(inner)
    with pytest.raises(OutboundStorageNetworkError) as exc_info:
        execute_request(req, action="any.action")

    assert exc_info.value is inner
