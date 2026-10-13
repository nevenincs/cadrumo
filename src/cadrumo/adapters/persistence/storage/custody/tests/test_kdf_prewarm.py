"""A prewarmed KDF child takes the launch off the operation without sharing a child between operations."""

from __future__ import annotations

import base64
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from ......core.config import Settings, override_settings
from .. import _kdf_process as process_boundary
from .. import kdf_supervision
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..kdf_supervision import ProfileKdfPrewarm
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"p" * 16).decode("ascii"),
        output_bytes=32,
    )


@pytest.fixture
def settings(tmp_path: Path) -> Generator[Settings]:
    with override_settings(cadrumo_local_storage_root=tmp_path) as settings:
        yield settings


@pytest.fixture
def launches(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[bytes]]:
    """Record every real child the supervisor launches, unchanged."""
    launched: list[subprocess.Popen[bytes]] = []
    lock = threading.Lock()
    launch_process = process_boundary._launch_worker_process

    def observe(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        process = launch_process(command, launch_kwargs)
        with lock:
            launched.append(process)
        return process

    monkeypatch.setattr(process_boundary, "_launch_worker_process", observe)
    return launched


def _ready_spare(prewarm: ProfileKdfPrewarm, *, timeout: float = 60.0) -> _SupervisedKdfWorker:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        spare = prewarm._spare
        if spare is not None:
            return spare
        time.sleep(0.05)
    pytest.fail("the prewarmed KDF child never attested")


def test_a_bound_operation_runs_in_the_attested_spare_and_the_next_spare_is_a_new_child(
    settings: Settings, launches: list[subprocess.Popen[bytes]]
) -> None:
    prewarm = ProfileKdfPrewarm(settings=settings)
    try:
        prewarm.refill()
        spare = _ready_spare(prewarm)
        assert len(launches) == 1

        with prewarm.bound():
            with kdf_supervision._supervised_kdf_worker(deadline=time.monotonic() + 30, settings=settings) as worker:
                assert worker is spare
                derivation_seconds = worker.calibrate(_kdf())
            # The operation itself launched nothing: its child was already attested.
            assert len(launches) == 1
        assert derivation_seconds > 0
        assert launches[0].returncode == 0, "the spare performs exactly one derivation and exits"

        successor = _ready_spare(prewarm)
        assert successor is not spare
        assert len(launches) == 2 and launches[1].pid != launches[0].pid
    finally:
        prewarm.close()
    assert all(process.poll() is not None for process in launches), "close contains the idle spare"


def test_a_spare_that_died_while_idle_is_replaced_by_a_fresh_child(
    settings: Settings, launches: list[subprocess.Popen[bytes]]
) -> None:
    prewarm = ProfileKdfPrewarm(settings=settings)
    try:
        prewarm.refill()
        spare = _ready_spare(prewarm)
        launches[0].kill()
        launches[0].wait(timeout=10)

        with (
            prewarm.bound(),
            kdf_supervision._supervised_kdf_worker(deadline=time.monotonic() + 30, settings=settings) as worker,
        ):
            assert worker is not spare
            assert worker.calibrate(_kdf()) > 0
        assert len(launches) >= 2
    finally:
        prewarm.close()


def test_an_unbound_operation_never_adopts_a_spare(settings: Settings, launches: list[subprocess.Popen[bytes]]) -> None:
    prewarm = ProfileKdfPrewarm(settings=settings)
    try:
        prewarm.refill()
        spare = _ready_spare(prewarm)
        with kdf_supervision._supervised_kdf_worker(deadline=time.monotonic() + 30, settings=settings) as worker:
            assert worker is not spare
            assert worker.calibrate(_kdf()) > 0
        assert prewarm._spare is spare
        assert spare._process is not None and spare._process.poll() is None
    finally:
        prewarm.close()
