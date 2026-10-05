"""The UAC elevation type of this process's own Windows token.

A supervised runtime refuses to serve from a full UAC-elevated token. Only a
split token's elevated half is refused: an account with UAC disabled runs with
the default type and is accepted, whatever its group membership.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import IntEnum
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError


class WindowsTokenElevationType(IntEnum):
    """The native ``TOKEN_ELEVATION_TYPE`` values."""

    # No split token: UAC is disabled, or the account has no elevated half.
    DEFAULT = 1
    # The elevated half of a split token.
    FULL = 2
    # The filtered half of a split token.
    LIMITED = 3


def windows_token_elevation_type(value: object) -> WindowsTokenElevationType:
    """Decode a native ``TOKEN_ELEVATION_TYPE``, refusing any value outside the enumeration."""
    if type(value) is not int or value not in {member.value for member in WindowsTokenElevationType}:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return WindowsTokenElevationType(value)


def supervised_elevation_refused(elevation: WindowsTokenElevationType) -> bool:
    """Report whether a supervised runtime must refuse to serve from ``elevation``."""
    return elevation is WindowsTokenElevationType.FULL


def current_process_token_elevation_type() -> WindowsTokenElevationType:
    """Read this process's token elevation type through a query-only token handle."""
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import win32api
    import win32security

    open_token = cast(Callable[[int, int], int], win32security.OpenProcessToken)
    information = cast(Callable[[int, int], object], win32security.GetTokenInformation)
    token = open_token(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    try:
        value = information(token, win32security.TokenElevationType)
    finally:
        win32api.CloseHandle(token)
    return windows_token_elevation_type(value)


__all__ = [
    "WindowsTokenElevationType",
    "current_process_token_elevation_type",
    "supervised_elevation_refused",
    "windows_token_elevation_type",
]
