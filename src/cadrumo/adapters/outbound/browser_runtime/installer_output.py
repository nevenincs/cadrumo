"""Tolerant reading of the Playwright installer's console output for the cause of a failure.

The installer has no machine-readable channel, so a failure's cause is read
from its text, and a line that matches nothing changes nothing. Byte progress
is not read here: Cadrumo downloads the archives itself and counts their bytes.
With ``DEBUG=pw:install`` the installer prints the underlying error, which is
what makes a closed failure category possible at all.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

__all__ = ["classify_installer_output"]

_SERVER_CODE: Final = re.compile(r"server returned code (\d{3})")

_NO_SPACE: Final = ("enospc", "no space left")
_NO_PERMISSION: Final = ("eacces", "eperm", "permission denied", "operation not permitted")
_SECURE_CONNECTION: Final = (
    "certificate",
    "unable_to_verify",
    "self_signed",
    "self-signed",
    "err_tls",
    "ssl routines",
    "tlsv1 alert",
)
_TRANSIENT_NETWORK: Final = (
    "eai_again",
    "enotfound",
    "econnreset",
    "econnrefused",
    "etimedout",
    "esockettimedout",
    "socket hang up",
    "network timeout",
    "timed out",
)


def classify_installer_output(lines: Iterable[str]) -> tuple[DependencyFailureCategory | None, bool]:
    """Return the failure category the output names and whether a later attempt may succeed.

    ``(None, False)`` means the output names no recognised cause.
    """
    text = "\n".join(lines).lower()
    if any(token in text for token in _NO_SPACE):
        return DependencyFailureCategory.DISK_FULL, False
    if any(token in text for token in _NO_PERMISSION):
        return DependencyFailureCategory.NO_PERMISSION, False
    code = _SERVER_CODE.search(text)
    if code is not None:
        status = int(code.group(1))
        if status == 429 or status >= 500:
            return DependencyFailureCategory.HOST_UNREACHABLE, True
        if status in {403, 407}:
            return DependencyFailureCategory.BLOCKED_BY_NETWORK, False
        return DependencyFailureCategory.UNEXPECTED, False
    if any(token in text for token in _SECURE_CONNECTION):
        return DependencyFailureCategory.SECURE_CONNECTION_FAILED, False
    if any(token in text for token in _TRANSIENT_NETWORK):
        return DependencyFailureCategory.HOST_UNREACHABLE, True
    return None, False
