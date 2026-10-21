"""Tolerant reading of the Playwright installer's console output.

The installer has no machine-readable channel, so byte progress and failure
causes are read from its text. Every pattern here is optional: a line that
matches nothing changes nothing, and progress then falls back to the setup
step alone. With ``DEBUG=pw:install`` the installer also prints each archive's
exact size and the underlying network error, which is what makes a closed
failure category possible at all.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

__all__ = ["InstallerProgressParser", "classify_installer_output"]

_MIB: Final = 1024 * 1024

_ARCHIVE_STARTED: Final = re.compile(r"Downloading .+\(playwright [a-z0-9-]+ v\d+\)")
_EXACT_TOTAL: Final = re.compile(r"-- total bytes: (\d{1,15})\b")
_PERCENT: Final = re.compile(r"\|\s*(\d{1,3})% of (\d{1,9}(?:\.\d{1,3})?) MiB")
_ARCHIVE_FINISHED: Final = re.compile(r"\) downloaded to ")
_SERVER_CODE: Final = re.compile(r"server returned code (\d{3})")


class InstallerProgressParser:
    """Turns installer lines into one running byte count across every archive of a run.

    A repeated download line for the same archive (the installer's own retry)
    restarts that archive's count without adding the abandoned bytes.
    """

    def __init__(self) -> None:
        """Start a run with nothing downloaded."""
        self._finished = 0
        self._current_total = 0
        self._current_done = 0

    def feed(self, line: str) -> int | None:
        """Read one line; return the new running total when the line moved it."""
        if _ARCHIVE_STARTED.search(line):
            self._current_total = 0
            self._current_done = 0
            return None
        exact = _EXACT_TOTAL.search(line)
        if exact is not None:
            self._current_total = int(exact.group(1))
            return None
        percent = _PERCENT.search(line)
        if percent is not None:
            share = min(int(percent.group(1)), 100)
            if not self._current_total:
                self._current_total = round(float(percent.group(2)) * _MIB)
            done = self._current_total * share // 100
            if done <= self._current_done:
                return None
            self._current_done = done
            return self._finished + done
        if _ARCHIVE_FINISHED.search(line):
            self._finished += max(self._current_total, self._current_done)
            self._current_total = 0
            self._current_done = 0
            return self._finished
        return None


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
