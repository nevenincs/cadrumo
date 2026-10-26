"""A 403 means the same thing in both Google adapters: quota only on a quota marker."""

from __future__ import annotations

from typing import Any

import httplib2
import pytest
from googleapiclient.errors import HttpError

from ...google.api import RequestRetryPolicy, execute_request
from .._google_drive import _translate_http_error
from ..errors import OutboundStorageError, OutboundStoragePermissionError, OutboundStorageQuotaError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_QUOTA_REASON_BODY = b'{"error":{"code":403,"errors":[{"reason":"userRateLimitExceeded"}]}}'
_QUOTA_STATUS_BODY = b'{"error":{"code":403,"status":"RESOURCE_EXHAUSTED"}}'
_FORBIDDEN_BODY = b'{"error":{"code":403,"errors":[{"reason":"insufficientFilePermissions"}]}}'


def _http_error(status: int, content: bytes) -> HttpError:
    return HttpError(httplib2.Response({"status": str(status), "reason": "test"}), content)


class _RaisingRequest:
    def __init__(self, error: HttpError) -> None:
        self._error = error

    def execute(self, http: object = None, num_retries: int = 0) -> dict[str, Any]:
        raise self._error


def _sheets_stack_error(error: HttpError) -> OutboundStorageError:
    with pytest.raises(OutboundStorageError) as raised:
        execute_request(_RaisingRequest(error), action="drive.files.get", retry=RequestRetryPolicy.SINGLE_ATTEMPT)
    return raised.value


@pytest.mark.parametrize(
    ("body", "expected"),
    (
        (_QUOTA_REASON_BODY, OutboundStorageQuotaError),
        (_QUOTA_STATUS_BODY, OutboundStorageQuotaError),
        (_FORBIDDEN_BODY, OutboundStoragePermissionError),
        (b"not json", OutboundStoragePermissionError),
    ),
    ids=("quota-reason", "quota-status", "plain-forbidden", "unparseable-body"),
)
def test_both_adapters_classify_a_403_alike(body: bytes, expected: type[OutboundStorageError]) -> None:
    error = _http_error(403, body)

    drive_error = _translate_http_error(error, action="files.get")
    api_error = _sheets_stack_error(error)

    assert type(drive_error) is expected
    assert type(api_error) is expected


def test_a_401_stays_a_permission_failure_in_both_adapters() -> None:
    error = _http_error(401, _QUOTA_REASON_BODY)

    assert type(_translate_http_error(error, action="files.get")) is OutboundStoragePermissionError
    assert type(_sheets_stack_error(error)) is OutboundStoragePermissionError
