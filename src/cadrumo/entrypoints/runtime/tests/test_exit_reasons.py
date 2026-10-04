"""The runtime process ends with the exit reason of the event that stopped it."""

from __future__ import annotations

import subprocess
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.process_support import fixture_environment, native_python
from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeRefusalCode
from cadrumo.application.runtime.login import RuntimeLoginInventory

from ..main import run
from ..profile_connections import RuntimeProfileConnections
from ..shutdown import RuntimeStop, request_runtime_stop
from .test_profile_connections import LoginObservation

pytestmark = [pytest.mark.hex_entrypoint]

_BLOCKED_DRAIN = """
from threading import Event
from cadrumo.entrypoints.runtime.shutdown import RuntimeShutdownWatchdog
stop = Event()
with RuntimeShutdownWatchdog(stop, timeout=0.2):
    stop.set()
    Event().wait(20)
"""


@pytest.mark.unit
def test_stop_latch_keeps_the_first_requested_reason() -> None:
    stop = RuntimeStop()
    assert stop.reason is None and not stop.is_set()
    stop.request(RuntimeExitReason.SIGNAL_STOP)
    stop.request(RuntimeExitReason.LOGIN_WITNESS_LOSS)
    assert stop.is_set() and stop.reason is RuntimeExitReason.SIGNAL_STOP


@pytest.mark.unit
def test_plain_set_names_no_reason_and_plain_events_still_stop() -> None:
    stop = RuntimeStop()
    stop.set()
    assert stop.is_set() and stop.reason is None
    stop.request(RuntimeExitReason.SUPERVISOR_STOP)
    assert stop.reason is RuntimeExitReason.SUPERVISOR_STOP
    plain = Event()
    request_runtime_stop(plain, RuntimeExitReason.LOGIN_WITNESS_LOSS)
    assert plain.is_set()


@pytest.mark.unit
@pytest.mark.parametrize("earlier", [None, RuntimeExitReason.SIGNAL_STOP])
def test_login_witness_loss_names_its_reason_unless_a_stop_came_first(
    tmp_path: Path, earlier: RuntimeExitReason | None
) -> None:
    stop = RuntimeStop()
    native = LoginObservation("synthetic-owner")
    current = RuntimeLoginInventory((native,), complete=True)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
        login_inventory=lambda: current,
    )
    profiles._login_contexts()
    assert not stop.is_set()
    if earlier is not None:
        stop.request(earlier)
    native.active = False
    current = RuntimeLoginInventory((), complete=True)
    profiles._login_contexts()
    assert stop.is_set()
    assert stop.reason is (earlier or RuntimeExitReason.LOGIN_WITNESS_LOSS)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("storage_root", "expected_version", "refusal", "reason"),
    [
        pytest.param(
            "absolute",
            "0.0.0-not-installed",
            RuntimeRefusalCode.VERSION_MISMATCH,
            RuntimeExitReason.VERSION_MISMATCH,
            id="version",
        ),
        pytest.param(
            "relative", None, RuntimeRefusalCode.ROOT_MISMATCH, RuntimeExitReason.ROOT_MISMATCH, id="relative-root"
        ),
    ],
)
def test_startup_refusal_exits_with_its_reason_and_writes_only_the_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    storage_root: str,
    expected_version: str | None,
    refusal: RuntimeRefusalCode,
    reason: RuntimeExitReason,
) -> None:
    root = tmp_path if storage_root == "absolute" else Path("relative-runtime-root")
    code = run(
        [
            "--storage-root",
            str(root),
            "--storage-identity",
            "0" * 64,
            "--expected-version",
            expected_version or version("cadrumo"),
        ]
    )
    assert code == reason.value
    assert capsys.readouterr().err == refusal.value + "\n"
    assert not tuple(tmp_path.iterdir())


@pytest.mark.integration
def test_drain_watchdog_exits_the_process_with_its_reason(tmp_path: Path) -> None:
    completed = subprocess.run(  # noqa: S603 -- exact interpreter and fixed in-repository source.
        (str(native_python()), "-c", _BLOCKED_DRAIN),
        cwd=tmp_path,
        env=fixture_environment(),
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == RuntimeExitReason.DRAIN_WATCHDOG.value, completed.stderr
