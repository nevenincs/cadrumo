"""Pure classification of a Google API client HTTP failure.

Both Google adapters read the same two facts from a raised
``googleapiclient.errors.HttpError``: the response status and, for a 403, whether
the structured error payload names a quota refusal. Reading them is separate
from deciding what they mean, which differs per adapter (retry budget,
conflict, quota and permission mapping), so only the reading lives here.
"""

from __future__ import annotations

import json
from typing import Final

from .type_guards import is_object_dict, is_object_list

_RATE_LIMIT_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "rateLimitExceeded",
        "userRateLimitExceeded",
        "RATE_LIMIT_EXCEEDED",
        "RESOURCE_EXHAUSTED",
    }
)


def google_http_status(error: BaseException) -> int | None:
    """Return the HTTP status a Google API client error carries, or ``None``.

    ``None`` means the failure never produced an HTTP response (a transport or
    local error), so a caller must not read it as a mapped status.
    """
    status = getattr(error, "status_code", None) or getattr(getattr(error, "resp", None), "status", None)
    return status if isinstance(status, int) else None


def google_quota_marker(error: BaseException) -> str | None:
    """Return a recognised quota marker from a Google ``HttpError`` payload.

    Google may signal quota exhaustion through an HTTP 429 status, a 403 with
    ``error.status=RESOURCE_EXHAUSTED``, or nested ``reason`` fields such as
    ``rateLimitExceeded``. This reads only the structured payload; the status
    check belongs to the caller.
    """
    content = getattr(error, "content", b"")
    body = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    return next((marker for marker in _quota_markers_from_payload(payload) if marker in _RATE_LIMIT_MARKERS), None)


def _quota_markers_from_entries(entries: object) -> tuple[str, ...]:
    """Collect string ``reason`` markers from one Google error-entry list."""
    markers: list[str] = []
    if not is_object_list(entries):
        return ()
    for entry in entries:
        if not is_object_dict(entry):
            continue
        reason = entry.get("reason")
        if isinstance(reason, str):
            markers.append(reason)
    return tuple(markers)


def _quota_markers_from_payload(payload: object) -> tuple[str, ...]:
    """Collect quota markers from the structured Google error payload."""
    if not is_object_dict(payload):
        return ()
    raw_error = payload.get("error")
    if not is_object_dict(raw_error):
        return ()
    markers: list[str] = []
    status = raw_error.get("status")
    if isinstance(status, str):
        markers.append(status)
    markers.extend(_quota_markers_from_entries(raw_error.get("errors")))
    markers.extend(_quota_markers_from_entries(raw_error.get("details")))
    return tuple(markers)


__all__ = ["google_http_status", "google_quota_marker"]
