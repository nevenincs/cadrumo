"""Cancellation settles real KDF capacity waits and secret-bearing children."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Event

import pytest

from ......application.user_profile.proof_cancellation import ProfileProofCancellation, ProfileProofCancelledError
from .. import _kdf_file_lease as file_lease
from .. import kdf_supervision
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from .test_kdf_file_lease import _old_lock
from .test_kdf_supervision import _DEK, _PASSPHRASE, _permit_is_free, _settings, _stall, _unlock_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_cancellation_wakes_the_process_local_permit_without_waiting_for_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope, sentinel = _unlock_inputs()
    settings = _settings(tmp_path)
    cancellation, waiting = ProfileProofCancellation(), Event()
    wait = kdf_supervision._KDF_THREAD_CAPACITY.wait

    def wait_for_capacity(timeout: float | None = None) -> bool:
        waiting.set()
        return wait(timeout)

    monkeypatch.setattr(kdf_supervision._KDF_THREAD_CAPACITY, "wait", wait_for_capacity)
    with ExitStack() as cleanup:
        pool = ThreadPoolExecutor(max_workers=1)
        cleanup.callback(pool.shutdown)
        cleanup.enter_context(kdf_supervision.profile_kdf_lease(settings=settings, deadline=time.monotonic() + 60))
        cleanup.callback(cancellation.cancel)
        result = pool.submit(
            kdf_supervision.unlock_profile_custody,
            envelope,
            _PASSPHRASE,
            sentinel=sentinel,
            settings=settings,
            timeout_deadline=time.monotonic() + 600,
            cancellation=cancellation,
        )
        assert waiting.wait(10), "the proof must actually be waiting for the occupied local permit"
        cancellation.cancel()
        with pytest.raises(ProfileProofCancelledError):
            result.result(timeout=5)
        assert not kdf_supervision._KDF_THREAD_LEASE.acquire(blocking=False), "the earlier permit remains owned"
    assert _permit_is_free(settings)


def test_cancellation_settles_a_real_legacy_file_lock_wait_before_that_lock_is_released(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope, sentinel = _unlock_inputs()
    settings = _settings(tmp_path)
    cancellation, waiting = ProfileProofCancellation(), Event()
    helpers: list[subprocess.Popen[bytes]] = []
    derivations: list[_SupervisedKdfWorker] = []
    unwrap = _SupervisedKdfWorker.unwrap

    def derive(
        worker: _SupervisedKdfWorker,
        *,
        password: bytes,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        associated_data: bytes,
        recovery: bool = False,
    ) -> bytes | None:
        derivations.append(worker)
        return unwrap(
            worker,
            password=password,
            kdf=kdf,
            wrapped_dek=wrapped_dek,
            associated_data=associated_data,
            recovery=recovery,
        )

    monkeypatch.setattr(_SupervisedKdfWorker, "unwrap", derive)
    if sys.platform == "win32":
        kernel = file_lease._kernel32()
        wait = kernel.WaitForMultipleObjects

        def wait_for_capacity(count: int, handles: object, all_objects: bool, milliseconds: int) -> int:
            waiting.set()
            return wait(count, handles, all_objects, milliseconds)

        kernel.WaitForMultipleObjects = wait_for_capacity
        monkeypatch.setattr(file_lease, "_kernel32", lambda: kernel)
    else:
        launch = file_lease.launch_lease_worker

        def launching(*, neutral_root: Path, lease_fd: int, owner_fd: int, result_fd: int) -> subprocess.Popen[bytes]:
            helper = launch(neutral_root=neutral_root, lease_fd=lease_fd, owner_fd=owner_fd, result_fd=result_fd)
            helpers.append(helper)
            waiting.set()
            return helper

        monkeypatch.setattr(file_lease, "launch_lease_worker", launching)

    with ExitStack() as cleanup:
        pool = ThreadPoolExecutor(max_workers=1)
        cleanup.callback(pool.shutdown)
        descriptor = os.open(
            tmp_path / "profile-kdf.v1.lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600
        )
        cleanup.callback(os.close, descriptor)
        os.write(descriptor, b"\0")
        _old_lock(descriptor, acquire=True)
        cleanup.callback(_old_lock, descriptor, acquire=False)
        cleanup.callback(cancellation.cancel)
        result = pool.submit(
            kdf_supervision.unlock_profile_custody,
            envelope,
            _PASSPHRASE,
            sentinel=sentinel,
            settings=settings,
            timeout_deadline=time.monotonic() + 600,
            cancellation=cancellation,
        )
        assert waiting.wait(10), "the exact legacy OS lock must remain held when cancellation arrives"
        cancellation.cancel()
        with pytest.raises(ProfileProofCancelledError):
            result.result(timeout=5)
        assert not derivations, "a cancelled capacity wait must never send the password to an Argon2 child"
        assert all(helper.poll() is not None for helper in helpers)
    assert not derivations, "releasing legacy capacity cannot revive the cancelled attempt"
    assert _permit_is_free(settings)
    unlocked = kdf_supervision.unlock_profile_custody(
        envelope, _PASSPHRASE, sentinel=sentinel, settings=settings, cancellation=ProfileProofCancellation()
    )
    assert unlocked.dek == _DEK, "the same worker-side custody path remains usable for a fresh proof"


def test_cancellation_contains_and_reaps_the_secret_bearing_child_before_releasing_its_permit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope, sentinel = _unlock_inputs()
    settings = _settings(tmp_path)
    cancellation, sent = ProfileProofCancellation(), Event()
    prewarm = kdf_supervision.ProfileKdfPrewarm(settings=settings)
    prewarm._launch()
    spare = prewarm._spare
    assert spare is not None and spare._process is not None
    child = spare._process
    monkeypatch.setattr(prewarm, "refill", lambda: None)
    write = _SupervisedKdfWorker._write_request

    def stop_child_then_write(worker: _SupervisedKdfWorker, payload: dict[str, object]) -> None:
        assert worker is spare
        _stall(child)
        write(worker, payload)
        sent.set()

    monkeypatch.setattr(_SupervisedKdfWorker, "_write_request", stop_child_then_write)

    def prove() -> None:
        with prewarm.bound():
            kdf_supervision.unlock_profile_custody(
                envelope,
                _PASSPHRASE,
                sentinel=sentinel,
                settings=settings,
                timeout_deadline=time.monotonic() + 600,
                cancellation=cancellation,
            )

    def contain_if_test_failed() -> None:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)

    try:
        with ExitStack() as cleanup:
            pool = ThreadPoolExecutor(max_workers=1)
            cleanup.callback(pool.shutdown)
            cleanup.callback(contain_if_test_failed)
            cleanup.callback(cancellation.cancel)
            result = pool.submit(prove)
            assert sent.wait(10), "the contained child must own the protected password request before cancellation"
            cancellation.cancel()
            with pytest.raises(ProfileProofCancelledError):
                result.result(timeout=5)
        assert child.poll() is not None
        assert spare._process is None and spare._job is None
        assert spare._request_fd is None and spare._result_fd is None and not spare._readers
        assert spare._neutral_directory is None
        assert _permit_is_free(settings)
    finally:
        cancellation.cancel()
        prewarm.close()
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
