"""Optional native acquisition without coupling password custody to platform readiness."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)

from .automation_support import MemoryNativePort
from .test_automation_store import Subject
from .test_automation_store import subject as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def binding() -> ProfileAccessBinding:
    """Supply an exact synthetic identity for tests that never read profile custody."""
    return ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-native-acquisition-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )


@pytest.mark.parametrize("reason", [AutomationCustodyCode.UNSUPPORTED, AutomationCustodyCode.UNAVAILABLE])
def test_local_profile_lock_paths_do_not_acquire_native_custody_and_failure_is_retryable(
    subject: Subject, reason: AutomationCustodyCode
) -> None:
    calls = 0
    failure = AutomationCustodyError(reason)

    def acquire() -> AutomationSecretStore:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        return subject.native

    store = AutomationControlStore(
        root=subject.store.root, binding=subject.store.binding, secrets_store_factory=acquire
    )
    assert calls == 0
    initial = store.profile_lock_state()
    assert not initial.globally_locked
    assert store.unlock_profile(generation=initial.generation) == initial
    assert calls == 0

    with pytest.raises(AutomationCustodyError) as refused:
        store.read()
    assert refused.value is failure
    assert calls == 1
    assert store.profile_lock_state() == initial
    assert store.unlock_profile(generation=initial.generation) == initial
    assert calls == 1

    # The next real custody read reaches the native port and reports its missing anchor.
    with pytest.raises(AutomationCustodyError) as missing:
        store.read()
    assert missing.value.reason is AutomationCustodyCode.MISSING
    assert calls == 2
    assert store.secrets is subject.native
    with pytest.raises(AutomationCustodyError) as still_missing:
        store.read()
    assert still_missing.value.reason is AutomationCustodyCode.MISSING
    assert calls == 2


def test_concurrent_native_acquisition_publishes_one_successful_port(
    tmp_path: Path, binding: ProfileAccessBinding
) -> None:
    native = MemoryNativePort()
    callers = Barrier(5)
    entered = Event()
    release = Event()
    calls = 0

    def acquire() -> AutomationSecretStore:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=5), "native acquisition was not released"
        return native

    store = AutomationControlStore(root=tmp_path, binding=binding, secrets_store_factory=acquire)

    def obtain() -> AutomationSecretStore:
        callers.wait(timeout=5)
        return store.secrets

    with ThreadPoolExecutor(max_workers=4) as workers:
        acquisitions = [workers.submit(obtain) for _ in range(4)]
        try:
            callers.wait(timeout=5)
            assert entered.wait(timeout=5), "native acquisition did not start"
        finally:
            release.set()
        assert all(acquisition.result(timeout=5) is native for acquisition in acquisitions)
    assert calls == 1
    assert store.secrets is native


@pytest.mark.parametrize("both", [False, True])
def test_constructor_requires_exactly_one_native_source(
    tmp_path: Path, binding: ProfileAccessBinding, both: bool
) -> None:
    native = MemoryNativePort()
    with pytest.raises(AutomationCustodyError) as refused:
        AutomationControlStore(
            root=tmp_path,
            binding=binding,
            secrets_store=native if both else None,
            secrets_store_factory=(lambda: native) if both else None,
        )
    assert refused.value.reason is AutomationCustodyCode.UNSUPPORTED


def test_acquired_backend_must_be_native_and_invalid_acquisition_is_not_cached(
    tmp_path: Path, binding: ProfileAccessBinding
) -> None:
    native = MemoryNativePort()
    malformed = cast(AutomationSecretStore, SimpleNamespace(backend="windows_credential_manager"))
    calls = 0

    def acquire() -> AutomationSecretStore:
        nonlocal calls
        calls += 1
        return malformed if calls == 1 else native

    store = AutomationControlStore(root=tmp_path, binding=binding, secrets_store_factory=acquire)
    with pytest.raises(AutomationCustodyError) as refused:
        _ = store.secrets
    assert refused.value.reason is AutomationCustodyCode.UNSUPPORTED
    assert store.secrets is native
    assert calls == 2


def test_trusted_replacement_preserves_direct_injection_and_does_not_acquire_pending_factory(
    tmp_path: Path, binding: ProfileAccessBinding
) -> None:
    initial, replacement = MemoryNativePort(), MemoryNativePort()
    direct = AutomationControlStore(root=tmp_path, binding=binding, secrets_store=initial)
    assert direct.secrets is initial
    direct.secrets = replacement
    assert direct.secrets is replacement

    def forbidden_factory() -> AutomationSecretStore:
        pytest.fail("replacing a pending port must not acquire the superseded native dependency")

    pending = AutomationControlStore(root=tmp_path, binding=binding, secrets_store_factory=forbidden_factory)
    pending.secrets = replacement
    assert pending.secrets is replacement


def test_invalid_direct_or_replacement_backend_refuses_without_replacing_current_port(
    tmp_path: Path, binding: ProfileAccessBinding
) -> None:
    malformed = cast(AutomationSecretStore, SimpleNamespace(backend="windows_credential_manager"))
    with pytest.raises(AutomationCustodyError) as refused:
        AutomationControlStore(root=tmp_path, binding=binding, secrets_store=malformed)
    assert refused.value.reason is AutomationCustodyCode.UNSUPPORTED
    native = MemoryNativePort()
    store = AutomationControlStore(root=tmp_path, binding=binding, secrets_store=native)
    with pytest.raises(AutomationCustodyError) as replacement_refused:
        store.secrets = malformed
    assert replacement_refused.value.reason is AutomationCustodyCode.UNSUPPORTED
    assert store.secrets is native
