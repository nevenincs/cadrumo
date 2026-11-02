"""Ask the real remote-state guard what it would answer, and keep only a closed verdict.

The guard scans the whole URL, so it is given the real one; a verdict taken from
the redacted path could differ. Its reason text can quote that URL, so the reason
is reduced to a refusal class here and never retained.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlsplit

from pydantic import AnyUrl

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    evaluate_remote_operation,
)

ALLOW: Final = "allow"
REFUSE_UNPARSABLE: Final = "refuse:unparsable-url"

_TOKEN_REASON: Final = re.compile(r"AEAT remote state token '([a-z]+)' is forbidden")
_FORBIDDEN_ACTION_REASON: Final = re.compile(r"AEAT forbidden action '([a-z0-9 _-]+)' is blocked")
_REASON_CLASSES: Final = (
    ("AEAT remote write method ", "refuse:method"),
    ("AEAT host ", "refuse:host"),
    ("AEAT path ", "refuse:path-not-listed"),
    ("AEAT remote authority ", "refuse:authority"),
    ("AEAT forbidden action ", "refuse:forbidden-action"),
)


def _token_location(token: str, url: str) -> str:
    parts = urlsplit(url)
    return "path" if token in f"{parts.hostname or ''}{parts.path}".lower() else "query"


def _refusal_class(reason: str, url: str) -> str:
    if (token := _TOKEN_REASON.fullmatch(reason)) is not None:
        return f"refuse:token:{token[1]}@{_token_location(token[1], url)}"
    if (action := _FORBIDDEN_ACTION_REASON.fullmatch(reason)) is not None:
        return f"refuse:forbidden-action:{action[1]}"
    for prefix, refusal in _REASON_CLASSES:
        if reason.startswith(prefix):
            return refusal
    return "refuse:other"


def guard_verdict(policy: RemoteStateGuardPolicy, method: str, url: str) -> str:
    """Return ``allow`` or a value-free refusal class for this request under ``policy``."""
    try:
        operation = RemoteOperation(kind="http", method=method, url=AnyUrl(url))
        result = evaluate_remote_operation(policy, operation)
    except (ValueError, RegistryValidationError):
        return REFUSE_UNPARSABLE
    return ALLOW if result.decision == "allowed" else _refusal_class(result.reason, url)
