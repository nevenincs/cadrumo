"""A launch the operating system blocks is not charged to the bound that abandons a stalled KDF child."""

from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path

import pytest

from ......core.config import Settings
from .. import _kdf_process as process_boundary
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUDGET_SECONDS = 10.0
_BLOCKED_CREATE_SECONDS = _BUDGET_SECONDS + 1.0


def _kdf() -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=19,
        iterations=2,
        parallelism=1,
        salt_b64=base64.b64encode(b"l" * 16).decode("ascii"),
        output_bytes=32,
    )


def test_a_child_whose_creation_outlasts_the_deadline_still_attests_and_derives_within_the_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launch_process = process_boundary._launch_worker_process
    launch_returned: list[float] = []

    def blocked_create(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        # Stands in for a saturated host's CreateProcess call, which the
        # supervisor cannot interrupt; the child it then starts is real.
        time.sleep(_BLOCKED_CREATE_SECONDS)
        process = launch_process(command, launch_kwargs)
        launch_returned.append(time.monotonic())
        return process

    monkeypatch.setattr(process_boundary, "_launch_worker_process", blocked_create)
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + _BUDGET_SECONDS,
        settings=Settings(cadrumo_storage_root=tmp_path),
    )

    with worker:
        assert worker._deadline <= launch_returned[0] + _BUDGET_SECONDS
        assert worker.calibrate(_kdf()) > 0
