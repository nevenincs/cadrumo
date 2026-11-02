"""Reduce a request URL to a host and path that cannot carry taxpayer data.

The query string, fragment, user-info and port are never read out of the split
URL. What remains is judged segment by segment, and any segment that could hold
a tax identifier, a long number, a token or a session id is replaced whole.
A segment is kept only when its shape is that of a route name, so an unforeseen
shape is lost rather than written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Final
from urllib.parse import urlsplit

TAX_ID: Final = "tax-id"
DIGITS: Final = "digits"
RANDOM_ID: Final = "token"
SESSION: Final = "session"
ENCODED: Final = "encoded"
OPAQUE_TARGET: Final = "opaque-target"

_WEB_SCHEMES: Final = frozenset({"http", "https", "ws", "wss"})
_TAX_ID_SHAPE: Final = re.compile(r"[0-9]{8}[A-Za-z]|[A-Za-z][0-9]{7}[0-9A-Za-z]")
_DIGIT_RUN: Final = re.compile(r"[0-9]{5,}|[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ROUTE_NAME: Final = re.compile(r"[A-Za-z0-9._~-]+")
_MAX_ROUTE_NAME: Final = 64
_DIGIT_MIX_MIN_LENGTH: Final = 12
_RANDOM_CASE_MIN_LENGTH: Final = 16
# CamelCase servlet names flip case in under a third of their characters; random text in about half.
_RANDOM_CASE_FLIP_RATIO: Final = 0.4


@dataclass(frozen=True)
class RedactedTarget:
    """The only parts of a request URL that may leave the observing callback."""

    host: str
    path: str
    placeholders: tuple[str, ...]


def _placeholder(kind: str) -> str:
    return "{" + kind + "}"


def _case_flip_ratio(text: str) -> float:
    letters = [character for character in text if character.isalpha()]
    flips = sum(left.islower() != right.islower() for left, right in pairwise(letters))
    return flips / max(len(letters), 1)


def _sensitive_kind(segment: str) -> str | None:
    if _TAX_ID_SHAPE.search(segment):
        return TAX_ID
    if _DIGIT_RUN.search(segment):
        return DIGITS
    if not _ROUTE_NAME.fullmatch(segment):
        return ENCODED
    digit_count = sum(character.isdigit() for character in segment)
    if (
        len(segment) > _MAX_ROUTE_NAME
        or (len(segment) >= _DIGIT_MIX_MIN_LENGTH and digit_count >= 2)
        or (len(segment) >= _RANDOM_CASE_MIN_LENGTH and _case_flip_ratio(segment) >= _RANDOM_CASE_FLIP_RATIO)
    ):
        return RANDOM_ID
    return None


def _redact_host(host: str, placeholders: list[str]) -> str:
    labels = []
    for label in host.split("."):
        kind = _sensitive_kind(label)
        if kind is None:
            labels.append(label)
        else:
            placeholders.append(kind)
            labels.append(_placeholder(kind))
    return ".".join(labels)


def _redact_segment(segment: str, placeholders: list[str]) -> str:
    route, separator, _parameters = segment.partition(";")
    kind = _sensitive_kind(route) if route else None
    if kind is not None:
        placeholders.append(kind)
        route = _placeholder(kind)
    if not separator:
        return route
    # Kept visible because the guard reads a path parameter as part of the exact path.
    placeholders.append(SESSION)
    return f"{route};{_placeholder(SESSION)}"


def redact_target(url: str) -> RedactedTarget:
    """Return the host and path of ``url`` with every doubtful segment replaced and counted."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
    except ValueError:
        return RedactedTarget("", _placeholder(OPAQUE_TARGET), (OPAQUE_TARGET,))
    if parts.scheme.lower() not in _WEB_SCHEMES or not host:
        return RedactedTarget("", _placeholder(OPAQUE_TARGET), (OPAQUE_TARGET,))
    placeholders: list[str] = []
    redacted_host = _redact_host(host, placeholders)
    path = "/".join(_redact_segment(segment, placeholders) for segment in parts.path.split("/")) or "/"
    return RedactedTarget(redacted_host, path, tuple(placeholders))
