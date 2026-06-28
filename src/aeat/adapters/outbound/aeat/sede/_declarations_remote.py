"""Remote-read guard helpers for the declarations register walker."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from pydantic import AnyUrl

from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from ._errors import SedeParseError

_CSV_SHAPE_RE = re.compile(r"^[A-Z0-9]{8,24}$")


def assert_read_http(
    method: str,
    url: str,
    *,
    policy: RemoteStateGuardPolicy,
) -> None:
    assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


def assert_read_browser_action(
    action: str,
    *,
    policy: RemoteStateGuardPolicy,
) -> None:
    assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="browser_action", action=action),
    )


def extract_csv_from_url(url: str) -> str:
    """Extract and shape-validate the ``CSV`` query parameter from a cotejo URL."""
    parsed = urlsplit(url)
    qs = parse_qs(parsed.query)
    csv_values = qs.get("CSV", [])
    if not csv_values:
        raise SedeParseError(f"cotejo URL missing CSV query: {url!r}")
    if len(csv_values) > 1:
        raise SedeParseError(
            f"cotejo URL has {len(csv_values)} CSV values; AEAT only emits one: {url!r}",
        )
    csv = csv_values[0]
    if not _CSV_SHAPE_RE.match(csv):
        raise SedeParseError(
            f"cotejo URL CSV {csv!r} does not match AEAT shape (expected 8-24 uppercase alphanumeric chars)",
        )
    return csv


__all__ = [
    "assert_read_browser_action",
    "assert_read_http",
    "extract_csv_from_url",
]
