"""A supervised runtime refuses only the elevated half of a split UAC token."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from typing import cast

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..windows_token_elevation import (
    WindowsTokenElevationType,
    current_process_token_elevation_type,
    supervised_elevation_refused,
    windows_token_elevation_type,
)

pytestmark = [pytest.mark.hex_outbound_adapter]

_WINDOWS_DLL_LOADER = "WinDLL"
_TOKEN_QUERY = 0x0008
_TOKEN_ELEVATION_TYPE_CLASS = 18
_TOKEN_ELEVATION_CLASS = 20


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "refused"),
    [(1, False), (2, True), (3, False)],
    ids=["default-uac-disabled", "full-elevated", "limited-filtered"],
)
def test_only_the_full_elevation_type_is_refused(value: int, refused: bool) -> None:
    assert supervised_elevation_refused(windows_token_elevation_type(value)) is refused


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, 4, -1, 2**32 + 2, True, 2.0, "2", None])
def test_a_value_outside_the_native_enumeration_is_refused_as_unavailable(value: object) -> None:
    with pytest.raises(RuntimeRefusalError) as refused:
        windows_token_elevation_type(value)
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE


def _token_dword(information_class: int) -> int:
    """Read one DWORD token class through raw advapi32, independently of pywin32."""
    from ctypes import wintypes

    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    kernel, advapi = loader("kernel32", use_last_error=True), loader("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    token = wintypes.HANDLE()
    assert advapi.OpenProcessToken(kernel.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token))
    try:
        value, returned = wintypes.DWORD(), wintypes.DWORD()
        assert advapi.GetTokenInformation(
            token, information_class, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(returned)
        )
        return int(value.value)
    finally:
        kernel.CloseHandle(token)


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows token")
def test_the_current_token_reads_as_the_native_type_and_passes_unless_fully_elevated() -> None:
    elevation = current_process_token_elevation_type()
    assert elevation.value == _token_dword(_TOKEN_ELEVATION_TYPE_CLASS)
    is_elevated = bool(_token_dword(_TOKEN_ELEVATION_CLASS))
    # A full token is always elevated; a default token may be elevated when UAC is disabled.
    if elevation is WindowsTokenElevationType.FULL:
        assert is_elevated
    assert supervised_elevation_refused(elevation) is (elevation is WindowsTokenElevationType.FULL)


@pytest.mark.unit
@pytest.mark.skipif(sys.platform == "win32", reason="the token read refuses only off Windows")
def test_the_token_read_refuses_off_windows() -> None:
    with pytest.raises(RuntimeRefusalError) as refused:
        current_process_token_elevation_type()
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
