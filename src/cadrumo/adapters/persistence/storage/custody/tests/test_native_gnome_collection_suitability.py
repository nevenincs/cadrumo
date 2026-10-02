"""Acceptance of the installed Linux Secret Service against an owned GNOME fixture.

These cases run only when an explicit protected/unsuitable disposable facility
is selected. Ordinary test runs skip them instead of treating an ambient user
keyring as acceptance evidence.
"""

from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import linux_secret_service_store as native
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_store import CLIENT_NAMESPACE
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="requires the installed Linux Secret Service"),
]

_FIXTURE_SELECTOR = "CADRUMO_TEST_GNOME_COLLECTION_EXPECTATION"
_NATIVE_METHODS = frozenset(
    {
        "Hello",
        "GetNameOwner",
        "GetConnectionUnixUser",
        "GetConnectionUnixProcessID",
        "GetControlDirectory",
        "ReadAlias",
        "Get",
        "SearchItems",
        "OpenSession",
        "Close",
        "GetSecret",
        "CreateItem",
        "Delete",
        "Unlock",
        "Prompt",
        "CreateCollection",
    }
)
_ITEM_OR_PROMPT_METHODS = frozenset(
    {"SearchItems", "OpenSession", "GetSecret", "CreateItem", "Delete", "Unlock", "Prompt", "CreateCollection"}
)


@dataclass(slots=True)
class _NativeCallTrace:
    method_names: list[str] = field(default_factory=list)
    control_directory_checks: int = 0


def _selected_control_directory(expectation: str) -> Path:
    if sys.platform != "linux":
        pytest.skip("Linux GNOME Secret Service is unavailable")

    selected = os.environ.get(_FIXTURE_SELECTOR)
    if selected is None:
        pytest.skip("native GNOME acceptance requires an explicit disposable-fixture selector")
    if selected not in {"protected", "unsuitable"}:
        pytest.fail("native GNOME fixture selector must be protected or unsuitable", pytrace=False)
    if selected != expectation:
        pytest.skip(f"native GNOME fixture selects {selected}, not {expectation}")

    raw_control_directory = os.environ.get("GNOME_KEYRING_CONTROL")
    if raw_control_directory is None:
        pytest.fail("selected native GNOME fixture has no control directory", pytrace=False)
    control_directory = Path(raw_control_directory)
    runtime_directory = Path("/run/user") / str(os.getuid())
    try:
        relative = control_directory.relative_to(runtime_directory)
    except ValueError:
        pytest.fail("selected GNOME control directory is outside the current user's runtime fixture", pytrace=False)
    if (
        len(relative.parts) != 2
        or not relative.parts[0].startswith("cadrumo-native-ss-")
        or relative.parts[0] == "cadrumo-native-ss-"
        or relative.parts[1] != "control"
        or not control_directory.is_dir()
    ):
        pytest.fail("selected GNOME control directory is not the disposable native fixture", pytrace=False)
    return control_directory


def _trace_native_calls(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_control_directory: Path,
) -> _NativeCallTrace:
    trace = _NativeCallTrace()
    actual_call = native._DeadlineBus.call

    def traced_call(
        bus: native._DeadlineBus,
        path: str,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple[Any, ...] = (),
        *,
        destination: str | None = None,
    ) -> tuple[Any, ...]:
        if method not in _NATIVE_METHODS:
            pytest.fail("native Secret Service client issued an unreviewed D-Bus method", pytrace=False)
        trace.method_names.append(method)
        reply = actual_call(
            bus,
            path,
            interface,
            method,
            signature,
            body,
            destination=destination,
        )
        if method == "GetControlDirectory":
            trace.control_directory_checks += 1
            assert reply == (str(expected_control_directory),)
        return reply

    monkeypatch.setattr(native._DeadlineBus, "call", traced_call)
    return trace


def test_native_protected_gnome_collection_round_trips_binary_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control_directory = _selected_control_directory("protected")
    trace = _trace_native_calls(monkeypatch, expected_control_directory=control_directory)
    store = native_automation_secret_store(NativeSecretBackend.LINUX_DBUS)
    assert store.backend is NativeSecretBackend.LINUX_DBUS

    account = str(uuid4())
    first = SecretBytes(b"\x00" + secrets.token_bytes(31) + b"\xff")
    replacement = SecretBytes(b"\xff" + secrets.token_bytes(31) + b"\x00")
    assert first != replacement
    assert store.read(CLIENT_NAMESPACE, account) is None
    try:
        store.replace(CLIENT_NAMESPACE, account, first)
        assert store.read(CLIENT_NAMESPACE, account) == first
        store.replace(CLIENT_NAMESPACE, account, replacement)
        assert store.read(CLIENT_NAMESPACE, account) == replacement
        store.delete(CLIENT_NAMESPACE, account)
        assert store.read(CLIENT_NAMESPACE, account) is None
    finally:
        store.delete(CLIENT_NAMESPACE, account)
        assert store.read(CLIENT_NAMESPACE, account) is None

    observed_methods = set(trace.method_names)
    assert {
        "ReadAlias",
        "GetNameOwner",
        "GetConnectionUnixUser",
        "GetConnectionUnixProcessID",
        "GetControlDirectory",
        "SearchItems",
        "OpenSession",
        "GetSecret",
        "CreateItem",
        "Delete",
    } <= observed_methods
    assert trace.control_directory_checks > 0
    assert not {"Unlock", "Prompt", "CreateCollection"} & observed_methods


def test_native_unsuitable_gnome_collection_refuses_before_secret_item_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control_directory = _selected_control_directory("unsuitable")
    trace = _trace_native_calls(monkeypatch, expected_control_directory=control_directory)
    store = native_automation_secret_store(NativeSecretBackend.LINUX_DBUS)
    assert store.backend is NativeSecretBackend.LINUX_DBUS

    account = str(uuid4())
    replacement = SecretBytes(b"\x00" + secrets.token_bytes(31) + b"\xff")
    for operation in ("read", "replace", "delete"):
        call_start = len(trace.method_names)
        with pytest.raises(AutomationCustodyError) as refused:
            if operation == "replace":
                store.replace(CLIENT_NAMESPACE, account, replacement)
            elif operation == "read":
                store.read(CLIENT_NAMESPACE, account)
            else:
                store.delete(CLIENT_NAMESPACE, account)
        assert refused.value.reason is AutomationCustodyCode.NEEDS_USER
        operation_methods = trace.method_names[call_start:]
        assert {
            "GetNameOwner",
            "GetConnectionUnixUser",
            "GetConnectionUnixProcessID",
            "GetControlDirectory",
        } <= set(operation_methods)
        assert not _ITEM_OR_PROMPT_METHODS & set(operation_methods)

    assert trace.control_directory_checks == 3
