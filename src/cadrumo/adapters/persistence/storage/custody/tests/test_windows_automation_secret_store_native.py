"""Opt-in real Windows Credential Manager replacement for exact synthetic items.

Select ``CADRUMO_TEST_WINDOWS_CREDENTIAL_MANAGER_EXPECTATION=protected`` only
from a normal, non-elevated interactive desktop logon. When selected, an
unavailable native facility is a failure; this test never enumerates or reads
any item except the random accounts it creates.
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import secrets
import sys
from collections.abc import Callable
from typing import cast
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_native_identity import (
    CLIENT_NAMESPACE,
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import TrackedWindowsItemCleanup
from cadrumo.application.user_profile.automation_custody_port import NativeSecretBackend
from cadrumo.core.async_cleanup import close_async_resources

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.os_keychain,
    pytest.mark.serial,
]

_EXPECTATION = "CADRUMO_TEST_WINDOWS_CREDENTIAL_MANAGER_EXPECTATION"
_WINDOWS_DLL_LOADER = "WinDLL"


def _windows_library(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    return loader(name, use_last_error=True)


def _is_elevated() -> bool | None:
    from ctypes import wintypes

    class _TokenElevation(ctypes.Structure):
        _fields_ = [("TokenIsElevated", wintypes.DWORD)]

    kernel = _windows_library("kernel32")
    advapi = _windows_library("advapi32")
    current_process = kernel.GetCurrentProcess
    current_process.argtypes = ()
    current_process.restype = wintypes.HANDLE
    open_token = advapi.OpenProcessToken
    open_token.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    open_token.restype = wintypes.BOOL
    get_information = advapi.GetTokenInformation
    get_information.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    get_information.restype = wintypes.BOOL
    close_handle = kernel.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not open_token(current_process(), 0x0008, ctypes.byref(token)):
        return None
    try:
        elevation = _TokenElevation()
        returned = wintypes.DWORD()
        if not get_information(token, 20, ctypes.byref(elevation), ctypes.sizeof(elevation), ctypes.byref(returned)):
            return None
        return bool(elevation.TokenIsElevated)
    finally:
        close_handle(token)


def _has_interactive_desktop() -> bool:
    from ctypes import wintypes

    kernel = _windows_library("kernel32")
    user = _windows_library("user32")
    process_id_to_session = kernel.ProcessIdToSessionId
    process_id_to_session.argtypes = (wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    process_id_to_session.restype = wintypes.BOOL
    session_id = wintypes.DWORD()
    if not process_id_to_session(os.getpid(), ctypes.byref(session_id)) or session_id.value == 0:
        return False

    open_input_desktop = user.OpenInputDesktop
    open_input_desktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_input_desktop.restype = wintypes.HANDLE
    desktop = open_input_desktop(0, False, 0x0001)
    if not desktop:
        return False
    close_desktop = user.CloseDesktop
    close_desktop.argtypes = (wintypes.HANDLE,)
    close_desktop.restype = wintypes.BOOL
    close_desktop(desktop)
    return True


def require_selected_normal_desktop() -> None:
    selected = os.environ.get(_EXPECTATION)
    if selected is None:
        pytest.skip("requires explicit Windows Credential Manager acceptance selection")
    if selected != "protected":
        pytest.fail("Windows Credential Manager expectation must be protected", pytrace=False)
    if sys.platform != "win32":
        pytest.fail("protected Windows Credential Manager expectation requires Windows", pytrace=False)
    if _is_elevated() is not False:
        pytest.fail("protected Windows Credential Manager expectation requires a verifiably non-elevated token")
    if not _has_interactive_desktop():
        pytest.fail("protected Windows Credential Manager expectation requires an interactive desktop logon")


@pytest.mark.parametrize(
    "namespace",
    [
        pytest.param(CLIENT_NAMESPACE, id="client"),
        pytest.param(CONTROL_NAMESPACE, id="control"),
        pytest.param(WRAP_NAMESPACE, id="wrap"),
    ],
)
def test_windows_credential_manager_replaces_and_deletes_exact_binary_item(
    namespace: str,
) -> None:
    require_selected_normal_desktop()
    store = native_automation_secret_store(NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER)
    assert store.backend is NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER

    account = f"native-test/{uuid4().hex}"
    assert store.read(namespace, account) is None

    first = SecretBytes(b"\x00" + secrets.token_bytes(63) + b"\xff\x80")
    replacement = SecretBytes(b"\x80" + secrets.token_bytes(47) + b"\x00\xfe")
    assert not secrets.compare_digest(first.get_secret_value(), replacement.get_secret_value())

    owner = TrackedWindowsItemCleanup(store, namespace, account)
    primary: BaseException | None = None
    try:
        store.replace(namespace, account, first)
        first_readback = store.read(namespace, account)
        assert first_readback is not None
        assert secrets.compare_digest(first_readback.get_secret_value(), first.get_secret_value())

        store.replace(namespace, account, replacement)
        replacement_readback = store.read(namespace, account)
        assert replacement_readback is not None
        assert secrets.compare_digest(replacement_readback.get_secret_value(), replacement.get_secret_value())

        store.delete(namespace, account)
        assert store.read(namespace, account) is None
        store.delete(namespace, account)
        assert store.read(namespace, account) is None
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(
            close_async_resources(owner, task_name="synthetic-windows-credential-cleanup", primary_error=primary)
        )
    assert store.read(namespace, account) is None
