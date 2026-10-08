"""A live custody transaction defers the background sweep without stopping IPC."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.persistence.storage.bucket.keystore_paths import keystore_root
from cadrumo.adapters.persistence.storage.custody.errors import (
    ProfileCustodyLockContendedError,
    ProfileCustodyRecordError,
)
from cadrumo.adapters.persistence.storage.custody.filesystem import profile_custody_root_lock
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import publish_sign_in_custody
from cadrumo.entrypoints.runtime.sign_in_sweep import sweep_saved_sign_ins

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_sweep_defers_real_lock_contention_but_preserves_other_refusals(tmp_path: Path) -> None:
    custody = publish_sign_in_custody(tmp_path, uuid4())
    installation = runtime_installation(
        storage_root=tmp_path, os_owner_id=custody.binding.os_owner_id, storage_identity="a" * 64
    )
    keystore_root(tmp_path).mkdir(parents=True, exist_ok=True)
    acquired, release = Event(), Event()

    def hold_root() -> None:
        with profile_custody_root_lock(tmp_path):
            acquired.set()
            assert release.wait(10)

    with ThreadPoolExecutor(max_workers=1) as executor:
        held = executor.submit(hold_root)
        try:
            assert acquired.wait(5)
            with (
                pytest.raises(ProfileCustodyLockContendedError),
                profile_custody_root_lock(tmp_path, timeout_seconds=0.05),
            ):
                pytest.fail("a second thread acquired the held custody root")
            started = monotonic()
            assert (
                sweep_saved_sign_ins(root=tmp_path, installation=installation, logins=(), inventory_complete=True) == ()
            )
            assert monotonic() - started < 2
        finally:
            release.set()
        held.result(timeout=5)

    assert sweep_saved_sign_ins(root=tmp_path, installation=installation, logins=(), inventory_complete=True) == ()
    lock = tmp_path / ".profile-custody-root.lock"
    lock.unlink()
    lock.mkdir()
    with pytest.raises(ProfileCustodyRecordError) as refused:
        sweep_saved_sign_ins(root=tmp_path, installation=installation, logins=(), inventory_complete=True)
    assert not isinstance(refused.value, ProfileCustodyLockContendedError)
