"""The supervised call runtime bounds and terminates a hung CLI call.

Proves the contract with REAL subprocesses (no
mocks): a fast command completes and reports its output; a command that exceeds
its tier ceiling is terminated - promptly, not waited out - and reports
``timed_out``; a process that spawns a child is killed as a tree, not left with a
stranded grandchild; and the timeout tier is derived from the command
annotations. The localized refusal envelope is asserted through the real ``tr``
catalogue.
"""

from __future__ import annotations

import sys
import time

import pytest

from .._call_runtime import (
    CallTier,
    SupervisedResult,
    run_supervised,
    tier_for,
    timeout_seconds,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_tier_is_derived_from_annotations() -> None:
    assert tier_for(read_only=True, open_world=False) is CallTier.READ
    assert tier_for(read_only=False, open_world=False) is CallTier.MUTATE
    # Open-world (AEAT sede) always gets the live tier, read or write.
    assert tier_for(read_only=True, open_world=True) is CallTier.LIVE
    assert tier_for(read_only=False, open_world=True) is CallTier.LIVE
    # The live ceiling is the most generous (a portal pull runs for minutes).
    assert timeout_seconds(CallTier.LIVE) > timeout_seconds(CallTier.MUTATE) > timeout_seconds(CallTier.READ)


def test_a_fast_command_completes_without_timing_out() -> None:
    result = run_supervised(
        [sys.executable, "-c", "print('ok')"],
        timeout_s=30.0,
        encoding="utf-8",
    )
    assert isinstance(result, SupervisedResult)
    assert result.executable == sys.executable
    assert result.timed_out is False
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_a_hung_command_is_terminated_promptly_not_waited_out() -> None:
    started = time.monotonic()
    result = run_supervised(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        timeout_s=1.0,
        encoding="utf-8",
    )
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    # The call returned in seconds, not the 60s the child would have slept: proof
    # the process was killed at the ceiling rather than run to completion.
    assert elapsed < 20.0


def test_a_child_spawning_process_is_killed_as_a_tree() -> None:
    # The parent spawns a long-sleeping grandchild then sleeps itself; on timeout
    # the whole tree must be signalled. We assert the call returns promptly (the
    # tree was terminated) rather than blocking on the grandchild.
    script = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "time.sleep(60)"
    )
    started = time.monotonic()
    result = run_supervised([sys.executable, "-c", script], timeout_s=1.0, encoding="utf-8")
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert elapsed < 20.0


def test_timeout_refusal_is_localized_and_names_the_tier() -> None:
    from .._server import _timeout_refusal_envelope

    envelope = _timeout_refusal_envelope(command_key="app.live.expedientes.pull", tier=CallTier.LIVE, timeout_s=420.0)
    assert envelope["status"] == "error"
    assert envelope["timed_out"] is True
    refusal = envelope["refusal"]
    assert isinstance(refusal, str)
    # The refusal names the command, the tier, and the ceiling.
    assert "app.live.expedientes.pull" in refusal
    assert "live" in refusal
    assert "420" in refusal
