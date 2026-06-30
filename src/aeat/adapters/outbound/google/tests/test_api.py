"""Real-behavior tests for the Google API request executor.

Exercises :func:`execute_request` end-to-end using real
``googleapiclient.http.HttpRequest`` objects pointed at a local HTTP endpoint.
The tests verify the typed response shape, HTTP error translation, Google
client retry handling, and the re-raise contract for nested
``OutboundStorage*`` errors.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httplib2
import pytest
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest
from googleapiclient.model import JsonModel

from .....adapters.outbound.storage._errors import (
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
)
from .._api import GoogleApiResponseBody, _ExecutableRequest, execute_request

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

PostProcessor = Callable[[httplib2.Response, bytes], GoogleApiResponseBody]


@contextmanager
def _local_google_request(
    *responses: tuple[int, bytes],
    postproc: PostProcessor | None = None,
) -> Iterator[tuple[HttpRequest, list[str]]]:
    requested_paths: list[str] = []
    response_sequence = responses or ((200, _json_body({})),)

    class LocalResponseHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requested_paths.append(self.path)
            index = min(len(requested_paths) - 1, len(response_sequence) - 1)
            status, body = response_sequence[index]
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), LocalResponseHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = HttpRequest(
                httplib2.Http(),
                postproc or JsonModel().response,
                f"http://127.0.0.1:{server.server_port}/google-api-test",
            )
            yield request, requested_paths
        finally:
            server.shutdown()
            thread.join(timeout=2)


def _json_body(payload: GoogleApiResponseBody) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _postproc_raises(exc: BaseException) -> PostProcessor:
    def postproc(_response: httplib2.Response, _content: bytes) -> GoogleApiResponseBody:
        raise exc

    return postproc


# ---------------------------------------------------------------------------
# Protocol structural check
# ---------------------------------------------------------------------------


def test_executable_request_protocol_accepts_concrete_impl() -> None:
    """HttpRequest satisfies the _ExecutableRequest Protocol structurally."""

    # This is a runtime isinstance check using runtime_checkable would need
    # @runtime_checkable.  Instead assert that execute_request accepts it
    # without raising a TypeError — the call itself exercises the protocol.
    with _local_google_request((200, _json_body({"spreadsheetId": "x"}))) as (request, _paths):
        req: _ExecutableRequest = request
        result = execute_request(req, action="test.check")
    assert result == {"spreadsheetId": "x"}


# ---------------------------------------------------------------------------
# Response shape is GoogleApiResponseBody (dict[str, Any])
# ---------------------------------------------------------------------------


def test_execute_request_returns_dict_typed_as_google_api_response_body() -> None:
    """execute_request returns a GoogleApiResponseBody (dict[str, Any])."""

    payload: GoogleApiResponseBody = {"kind": "drive#file", "id": "abc123"}
    with _local_google_request((200, _json_body(payload))) as (req, _paths):
        result = execute_request(req, action="drive.files.get")

    assert isinstance(result, dict)
    assert result["id"] == "abc123"
    assert result["kind"] == "drive#file"


def test_execute_request_passes_nested_dict_payload_intact() -> None:
    """Nested dicts in the response survive the execute_request boundary."""

    payload: GoogleApiResponseBody = {"developerMetadata": [{"metadataKey": "aeat_vault_app", "metadataValue": "aeat"}]}
    with _local_google_request((200, _json_body(payload))) as (req, _paths):
        result = execute_request(req, action="sheets.spreadsheets.get")

    assert result["developerMetadata"][0]["metadataKey"] == "aeat_vault_app"


def test_execute_request_enables_google_client_retries() -> None:
    """Requests run through google-api-python-client retry handling."""

    payload: GoogleApiResponseBody = {"spreadsheetId": "retry-check"}
    with _local_google_request((500, b"try again"), (200, _json_body(payload))) as (req, requested_paths):
        result = execute_request(req, action="sheets.spreadsheets.get")

    assert result["spreadsheetId"] == "retry-check"
    assert requested_paths == ["/google-api-test", "/google-api-test"]


# ---------------------------------------------------------------------------
# HTTP error translation
# ---------------------------------------------------------------------------


def _make_http_error(status: int, content: bytes = b"error") -> Exception:
    """Build a minimal googleapiclient.errors.HttpError-shaped exception."""

    response = httplib2.Response({"status": str(status), "reason": "test"})
    return HttpError(resp=response, content=content)


def _request_raising(exc: BaseException) -> Iterator[tuple[HttpRequest, list[str]]]:
    return _local_google_request((200, _json_body({"ok": True})), postproc=_postproc_raises(exc))


def test_http_401_translates_to_permission_error() -> None:
    with _request_raising(_make_http_error(401)) as (req, _paths), pytest.raises(OutboundStoragePermissionError):
        execute_request(req, action="drive.files.get")


def test_http_403_translates_to_permission_error() -> None:
    with _request_raising(_make_http_error(403)) as (req, _paths), pytest.raises(OutboundStoragePermissionError):
        execute_request(req, action="drive.files.get")


def test_http_403_rate_limit_translates_to_quota_error() -> None:
    content = (
        b'{"error":{"code":403,"message":"quota","errors":[{"reason":"rateLimitExceeded"}],'
        b'"status":"RESOURCE_EXHAUSTED"}}'
    )
    with _request_raising(_make_http_error(403, content=content)) as (req, _paths), pytest.raises(
        OutboundStorageQuotaError,
    ):
        execute_request(req, action="sheets.spreadsheets.get")


def test_http_429_translates_to_quota_error() -> None:
    with _request_raising(_make_http_error(429)) as (req, _paths), pytest.raises(OutboundStorageQuotaError):
        execute_request(req, action="sheets.spreadsheets.get")


def test_http_404_translates_to_not_found_error() -> None:
    with _request_raising(_make_http_error(404)) as (req, _paths), pytest.raises(OutboundStorageNotFoundError):
        execute_request(req, action="drive.files.get")


def test_http_500_translates_to_network_error() -> None:
    with _request_raising(_make_http_error(500)) as (req, _paths), pytest.raises(OutboundStorageNetworkError):
        execute_request(req, action="drive.files.get")


def test_generic_exception_translates_to_network_error() -> None:
    with _request_raising(ConnectionError("timeout")) as (req, _paths), pytest.raises(OutboundStorageNetworkError):
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
    with _request_raising(inner) as (req, _paths), pytest.raises(OutboundStorageNetworkError) as exc_info:
        execute_request(req, action="any.action")

    assert exc_info.value is inner
