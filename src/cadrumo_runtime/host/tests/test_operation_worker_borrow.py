"""Operation observation can borrow custody while an effect holds the profile fence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import override

import pytest

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError

from ...adapters.profile_worker import ProfileWorkerProcess
from .test_worker_construction_cleanup import _owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _AdmittedWorker(ProfileWorkerProcess):
    def __init__(self) -> None:
        """Stand for already admitted custody; no process is launched in this lock test."""

    @override
    def require_alive(self) -> None:
        """The admitted worker remains available throughout the held effect."""


def test_observation_can_borrow_worker_while_another_thread_holds_commit_fence(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    worker = _AdmittedWorker()
    owner._worker = worker
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, owner.admission_guard():
            borrowed = pool.submit(owner.operation_worker)
            assert borrowed.result(timeout=1) is worker
    finally:
        owner._worker = None


def test_draining_owner_refuses_new_worker_borrow(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    owner._worker = _AdmittedWorker()
    owner._stopping.set()
    with pytest.raises(AutomationCustodyError):
        owner.operation_worker()
    owner._worker = None
