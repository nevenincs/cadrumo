"""Windows public secret-store methods refuse invalid targets before native access."""

from __future__ import annotations

from typing import NoReturn

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import automation_secret_store as windows_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import WindowsAutomationSecretStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_target import AUTOMATION_NAMESPACE_PREFIX
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}client-credentials"
_INVALID_TARGETS = [
    pytest.param("cadrumo.profile.client", "profile-1", id="outside-namespace"),
    pytest.param(_NAMESPACE, "profile\x00-1", id="nul-account"),
    pytest.param(_NAMESPACE, "a" * (1025 - len(_NAMESPACE)), id="over-limit"),
]


@pytest.mark.parametrize("operation", ["read", "replace", "delete"])
@pytest.mark.parametrize(("namespace", "account"), _INVALID_TARGETS)
def test_invalid_target_is_refused_before_native_factory(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    namespace: str,
    account: str,
) -> None:
    native_factory_calls: list[bool] = []

    def fail_if_native_factory_is_reached() -> NoReturn:
        native_factory_calls.append(True)
        pytest.fail("invalid target reached the Windows credential factory")

    monkeypatch.setattr(windows_secret_store, "_windows_credential_api", fail_if_native_factory_is_reached)
    store = WindowsAutomationSecretStore()

    with pytest.raises(AutomationCustodyError) as raised:
        if operation == "read":
            store.read(namespace, account)
        elif operation == "replace":
            store.replace(namespace, account, SecretBytes(b"synthetic-value"))
        else:
            store.delete(namespace, account)

    assert raised.value.reason is AutomationCustodyCode.INVALID
    assert native_factory_calls == []
