"""Remote-read guard and CSV-extraction helpers for the declarations fetch adapter.

The read guards (``assert_read_http``, ``assert_read_browser_action``) are
consumed only by ``_declarations_fetch.py``, which delegates to them for its
own ``_assert_read_http`` / ``_assert_read_browser_action`` wrappers.
``_walker.py`` — a separate declarations-register surface — declares its own
non-delegating read guards and never imports from this module.
``extract_csv_from_url`` is shared more widely, by ``_declarations.py`` and
``_parse.py`` as well.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from pydantic import AnyUrl

from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from ._adapter_utils import is_aeat_csv
from ._errors import SedeParseError


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
    if not is_aeat_csv(csv):
        raise SedeParseError(
            f"cotejo URL CSV {csv!r} does not match AEAT shape (expected 8-32 uppercase alphanumeric chars)",
        )
    return csv


__all__ = [
    "assert_read_browser_action",
    "assert_read_http",
    "extract_csv_from_url",
]
