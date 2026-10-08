"""The runtime process ends with the exit reason of the event that stopped it."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import override
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.process_support import fixture_environment, native_python
from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeRefusalCode
from cadrumo.application.runtime.login import RuntimeLoginInventory
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.core.diagnostic_log import DiagnosticFormatter, diagnostic_process
from cadrumo.core.logging import LOG_FILE_FORMAT

from .. import profile_connections
from ..arguments import parse_runtime_arguments
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


@dataclass(repr=False)
class _DiagnosticLoginWitness:
    context: OsLoginContext

    @property
    def login_id(self) -> str:
        return self.context.login_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        assert credential_facilities is Availability.UNAVAILABLE
        return self.context

    @override
    def __repr__(self) -> str:
        raise AssertionError("native witness objects must never be rendered in diagnostics")


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
@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("earlier", [None, RuntimeExitReason.SIGNAL_STOP])
def test_login_witness_loss_logs_only_counts_and_measured_spans_without_changing_stop(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    complete: bool,
    earlier: RuntimeExitReason | None,
) -> None:
    private_owner = "synthetic-private-owner-canary"
    native = LoginObservation(private_owner, login_id="synthetic-initial-login-canary")
    current = RuntimeLoginInventory((native,), complete=True)
    stop = RuntimeStop()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-private-storage-canary",
        runtime_boot_id=uuid4(),
        stop=stop,
        login_inventory=lambda: current,
    )
    profiles._login_contexts()
    assert not stop.is_set()
    if earlier is not None:
        stop.request(earlier)

    def witness(identifier: str, *, active: bool, eligibility: LoginEligibility) -> _DiagnosticLoginWitness:
        return _DiagnosticLoginWitness(
            OsLoginContext(
                login_id=identifier,
                os_owner_id=private_owner,
                active=active,
                lock_state=OsLockState.UNKNOWN,
                unattended=eligibility,
                credential_facilities=Availability.UNAVAILABLE,
            )
        )

    unknown = witness("synthetic-unknown-login-canary", active=True, eligibility=LoginEligibility.UNKNOWN)
    stale = witness("synthetic-stale-login-canary", active=False, eligibility=LoginEligibility.ELIGIBLE)
    peer = witness("synthetic-retained-login-canary", active=True, eligibility=LoginEligibility.INELIGIBLE)
    current = RuntimeLoginInventory((unknown, stale), complete=complete)
    profiles._logins[peer.login_id] = peer
    instants = iter((10.0, 10.25, 10.5, 10.875, 11.0))
    monkeypatch.setattr(profile_connections, "time", SimpleNamespace(monotonic=lambda: next(instants)))

    with diagnostic_process("runtime"), caplog.at_level(logging.WARNING, logger=profile_connections.__name__):
        remaining = profiles._login_contexts()

    assert len(remaining) == 3
    assert remaining[0] is unknown and remaining[1] is stale and remaining[2] is peer
    assert stop.is_set() and not profiles._private_work_available()
    assert stop.reason is (earlier or RuntimeExitReason.LOGIN_WITNESS_LOSS)
    records = [record for record in caplog.records if record.name == profile_connections.__name__]
    assert len(records) == 1
    record = records[0]
    assert record.getMessage() == "no eligible login witness remains; stopping the runtime"
    assert not record.args and record.exc_info is None
    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(record)
    context = json.loads(rendered.split(" | ", 1)[1])
    assert context == {
        "process_id": os.getpid(),
        "process_role": "runtime",
        "reason_code": "login_witness_loss",
        "inventory_complete": complete,
        "inventory_login_count": 2,
        "retained_peer_witness_count": 1,
        "observed_active_count": 2,
        "observed_eligible_count": 0,
        "observed_unknown_count": 1,
        "inventory_elapsed_ms": 250.0,
        "observation_elapsed_ms": 375.0,
    }
    assert "canary" not in rendered
    assert str(profiles.boot) not in rendered and str(tmp_path) not in rendered


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
    options = parse_runtime_arguments(
        [
            "--storage-root",
            str(root),
            "--storage-identity",
            "0" * 64,
            "--expected-version",
            expected_version or version("cadrumo"),
        ]
    )
    code = run(options)
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
        timeout=None,
        check=False,
    )
    assert completed.returncode == RuntimeExitReason.DRAIN_WATCHDOG.value, completed.stderr
