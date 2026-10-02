"""Opt-in native ordinary-host custody, without UI or borrowed user items.

Select CADRUMO_TEST_MACOS_KEYCHAIN_EXPECTATION=protected in an unlocked native
login context, or needs-user for the locked-context refusal detector. Protected
does not skip a missing native facility. Each binary round trip includes a fresh
Python process reopening the same item through the public store factory, with
expected bytes carried only by an anonymous stdin pipe. Random exact accounts
are cleaned in finally. Success in an unlocked context does not prove OS lock,
logout or guardian behavior; the separate needs-user case observes a real lock
without locking or unlocking the user's Keychain on behalf of the test.
"""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import macos_keychain_store as native
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_store import (
    CLIENT_NAMESPACE,
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.os_keychain,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS Security.framework"),
]

_REOPEN = """
import json
import secrets
import sys
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError, NativeSecretBackend

expected = bytearray(sys.stdin.buffer.read(2561))
result = {"result": "refused"}
try:
    if not 0 < len(expected) <= 2560:
        raise ValueError
    store = native_automation_secret_store(NativeSecretBackend.MACOS_KEYCHAIN)
    observed = store.read(sys.argv[1], sys.argv[2])
    if observed is not None and secrets.compare_digest(observed.get_secret_value(), expected):
        result = {"result": "reopened"}
except AutomationCustodyError as error:
    result = {"result": "refused", "code": error.reason.value}
except BaseException:
    result = {"result": "refused"}
finally:
    expected[:] = b"\\x00" * len(expected)
sys.stdout.write(json.dumps(result) + "\\n")
raise SystemExit(0 if result["result"] == "reopened" else 1)
"""


def _select(expectation: str) -> None:
    selected = os.environ.get("CADRUMO_TEST_MACOS_KEYCHAIN_EXPECTATION")
    if selected is None:
        pytest.skip("requires explicit native Keychain acceptance selection")
    if selected not in {"protected", "needs-user"}:
        pytest.fail("native Keychain expectation must be protected or needs-user", pytrace=False)
    if selected != expectation:
        pytest.skip("a different native Keychain expectation was explicitly selected")


def _ui(api: native._LoginKeychain) -> int:
    value = ctypes.c_ubyte()
    assert api.ui_get(ctypes.byref(value)) == native._SUCCESS
    assert value.value in (0, 1)
    return value.value


def _trace_queries(monkeypatch: pytest.MonkeyPatch) -> list[native._ItemIdentity]:
    original = native._LoginKeychain._query
    observed: list[native._ItemIdentity] = []

    @contextmanager
    def inspect_query(
        api: native._LoginKeychain, identity: native._ItemIdentity, *, adding: bool = False
    ) -> Generator[int]:
        with original(api, identity, adding=adding) as query:
            cf = api.cf
            constants = api.constants
            assert cf.text(cf.field(query, constants["kSecAttrService"])) == identity.namespace
            assert cf.text(cf.field(query, constants["kSecAttrAccount"])) == identity.account
            assert identity.keychain_path == native._login_path()
            assert _ui(api) == 0
            if adding:
                keychain = cf.field(query, constants["kSecUseKeychain"])
            else:
                search = cf.require_type(cf.field(query, constants["kSecMatchSearchList"]), cf.array_type)
                assert cf.array_count(search) == 1
                keychain = cf.array_get(search, 0)
            assert keychain is not None and api.keychain is not None
            assert cf.equal(keychain, api.keychain) == 1
            assert cf.equal(cf.field(query, constants["kSecClass"]), constants["kSecClassGenericPassword"]) == 1
            observed.append(identity)
            yield query

    monkeypatch.setattr(native._LoginKeychain, "_query", inspect_query)
    return observed


def _reopen(namespace: str, account: str, expected: SecretBytes) -> None:
    child = subprocess.run(  # noqa: S603 - fixed embedded development test module
        [sys.executable, "-c", _REOPEN, namespace, account],
        input=expected.get_secret_value(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    try:
        document: object = json.loads(child.stdout)
    except ValueError:
        pytest.fail("native child reopen did not return a closed receipt", pytrace=False)
    if child.returncode != 0 or document != {"result": "reopened"}:
        # Do not put stdout, stderr, native error text, expected data or observed
        # store contents in an assertion; only the closed process status.
        pytest.fail(f"native child reopen refused (exit={child.returncode})", pytrace=False)


@pytest.mark.parametrize("namespace", [CLIENT_NAMESPACE, CONTROL_NAMESPACE, WRAP_NAMESPACE])
def test_native_login_keychain_replaces_reopens_and_deletes_exact_binary_item_without_ui(
    namespace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _select("protected")
    queries = _trace_queries(monkeypatch)
    api = native._LoginKeychain()
    previous_ui = _ui(api)
    store = native_automation_secret_store(NativeSecretBackend.MACOS_KEYCHAIN)
    assert store.backend is NativeSecretBackend.MACOS_KEYCHAIN
    account, other_account = str(uuid4()), str(uuid4())
    first = SecretBytes(b"\x00" + secrets.token_bytes(31) + b"\xff")
    replacement = SecretBytes(b"\xff" + secrets.token_bytes(31) + b"\x00")
    assert store.read(namespace, account) is None
    assert store.read(namespace, other_account) is None
    try:
        store.replace(namespace, account, first)
        assert store.read(namespace, account) == first
        store.replace(namespace, account, replacement)
        assert store.read(namespace, account) == replacement
        _reopen(namespace, account, replacement)
        assert store.read(namespace, other_account) is None
        store.delete(namespace, account)
        assert store.read(namespace, account) is None
        store.delete(namespace, account)
        assert store.read(namespace, account) is None
    finally:
        store.delete(namespace, account)
        assert store.read(namespace, account) is None
        assert _ui(api) == previous_ui
    assert queries
    assert {query.namespace for query in queries} == {namespace}
    assert {query.account for query in queries} == {account, other_account}
    assert {query.keychain_path for query in queries} == {native._login_path()}


def test_native_locked_login_context_refuses_every_path_before_item_query(monkeypatch: pytest.MonkeyPatch) -> None:
    _select("needs-user")
    queries = _trace_queries(monkeypatch)
    api = native._LoginKeychain()
    previous_ui = _ui(api)
    store = native_automation_secret_store(NativeSecretBackend.MACOS_KEYCHAIN)
    assert store.backend is NativeSecretBackend.MACOS_KEYCHAIN
    account = str(uuid4())
    for action in ("read", "replace", "delete"):
        with pytest.raises(AutomationCustodyError) as refused:
            if action == "read":
                store.read(CLIENT_NAMESPACE, account)
            elif action == "replace":
                store.replace(CLIENT_NAMESPACE, account, SecretBytes(secrets.token_bytes(32)))
            else:
                store.delete(CLIENT_NAMESPACE, account)
        assert refused.value.reason is AutomationCustodyCode.NEEDS_USER
        assert _ui(api) == previous_ui
    assert not queries
