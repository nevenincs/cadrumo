"""Validation and visible elision for pre-redacted component prose."""

from __future__ import annotations

import re

from ....core.prose_elision import elide_to_cap
from ....core.redaction import redact_for_cli_output

_UNSAFE_RENDERED_TEXT = re.compile(
    r"""(?ix)
    (?:
        traceback\s*\(most\ recent\ call\ last\)
        | https?://
        | [a-z]:[\\/]
        | (?:^|[\s\"'])/(?:[^/\s]+/)+[^/\s]*
        | \b(?:password|passphrase|credential|secret|token|bearer|cookie)\s*[:=]
    )
    """
)


def bounded_pre_redacted_text(value: object, *, field: str, maximum_characters: int) -> str:
    """Return supplied safe prose within a visible presentation bound.

    Components do not classify failures or redact diagnostic material. Their
    input must therefore already be a single-line public projection. This
    check refuses raw locations, credentials, URLs, tracebacks, and any value
    the shared public-output redactor would still change.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a pre-redacted str, got {type(value).__name__}")
    if maximum_characters < 1:
        raise ValueError("maximum_characters must be positive")
    if not value or value != value.strip() or "\n" in value or "\r" in value or "\x1b" in value:
        raise ValueError(f"{field} must be non-empty, single-line plain text")
    if _UNSAFE_RENDERED_TEXT.search(value) is not None or redact_for_cli_output(value) != value:
        raise ValueError(f"{field} must already be safe for public TUI presentation")
    return elide_to_cap(value, cap=maximum_characters)
