"""The Google HTTP failure reader returns the status and quota marker a failure carries."""

from __future__ import annotations

import json

import httplib2
import pytest
from googleapiclient.errors import HttpError

from ..google_http_error import google_http_status, google_quota_marker

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _http_error(status: int, payload: object) -> HttpError:
    return HttpError(httplib2.Response({"status": str(status)}), json.dumps(payload).encode("utf-8"))


@pytest.mark.parametrize("status", [401, 403, 404, 409, 429, 503])
def test_status_is_read_from_the_response(status: int) -> None:
    assert google_http_status(_http_error(status, {})) == status


@pytest.mark.parametrize("error", [OSError("connection reset"), TimeoutError(), ValueError("local")])
def test_a_failure_with_no_http_response_has_no_status(error: BaseException) -> None:
    assert google_http_status(error) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"status": "RESOURCE_EXHAUSTED"}},
        {"error": {"errors": [{"reason": "rateLimitExceeded"}]}},
        {"error": {"errors": [{"reason": "notFound"}, {"reason": "userRateLimitExceeded"}]}},
        {"error": {"details": [{"reason": "RATE_LIMIT_EXCEEDED"}]}},
    ],
)
def test_a_quota_marker_is_found_wherever_google_places_it(payload: dict[str, object]) -> None:
    marker = google_quota_marker(_http_error(403, payload))

    assert marker in {"RESOURCE_EXHAUSTED", "rateLimitExceeded", "userRateLimitExceeded", "RATE_LIMIT_EXCEEDED"}


def test_the_first_recognised_marker_is_returned() -> None:
    payload = {"error": {"status": "PERMISSION_DENIED", "errors": [{"reason": "userRateLimitExceeded"}]}}

    assert google_quota_marker(_http_error(403, payload)) == "userRateLimitExceeded"


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"status": "PERMISSION_DENIED", "errors": [{"reason": "forbidden"}]}},
        {"error": {"errors": "rateLimitExceeded"}},
        {"error": "rateLimitExceeded"},
        ["rateLimitExceeded"],
        {},
    ],
)
def test_a_payload_without_a_recognised_marker_names_no_quota(payload: object) -> None:
    assert google_quota_marker(_http_error(403, payload)) is None


def test_a_body_that_is_not_json_names_no_quota() -> None:
    error = HttpError(httplib2.Response({"status": "403"}), b"<html>forbidden</html>")

    assert google_quota_marker(error) is None
