"""Verify run_id propagates across nested subpackage call sites.

Uses real, tiny classes that satisfy a structural Protocol — no mocks,
no patches. Each "subpackage" is a small class that in turn calls into
the next, recording an event at every layer. The assertion is that
every recorded event carries the same ``run_id`` set by the outer
:func:`run_context`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from . import (
    GenericPayload,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    load_events,
    load_trace,
    record_event,
    run_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class _Step(Protocol):
    """A trivial Protocol any chainable step satisfies structurally."""

    def __call__(self, label: str) -> None: ...


class _StatusStep:
    """Stand-in for ``aeat.status``."""

    def __call__(self, label: str) -> None:
        record_event(
            RunEventKind.ASSERTION,
            payload=RunEventPayload(generic=GenericPayload(fields=(("status", label),))),
        )


class _InboxStep:
    """Stand-in for ``aeat.inbox`` — calls into ``status`` next."""

    def __init__(self, downstream: _Step) -> None:
        self._downstream = downstream

    def __call__(self, label: str) -> None:
        record_event(
            RunEventKind.NAVIGATION,
            payload=RunEventPayload(generic=GenericPayload(fields=(("inbox", label),))),
        )
        self._downstream(label)


class _SubmissionStep:
    """Stand-in for ``aeat.submission`` — top of the chain."""

    def __init__(self, downstream: _Step) -> None:
        self._downstream = downstream

    def __call__(self, label: str) -> None:
        record_event(
            RunEventKind.STEP_START,
            payload=RunEventPayload(generic=GenericPayload(fields=(("submission", label),))),
        )
        self._downstream(label)


class TestRunContextOutcome:
    def test_outcome_ok_on_clean_exit(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        with run_context(entrypoint="aeat test ok", arguments=()) as info:
            run_id = info.run_id
        trace = load_trace(run_id)
        assert trace.outcome is RunOutcome.OK

    def test_outcome_failed_when_yield_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        captured: dict[str, str] = {}
        with (
            pytest.raises(RuntimeError, match="boom"),
            run_context(entrypoint="aeat test fail", arguments=()) as info,
        ):
            captured["run_id"] = info.run_id
            raise RuntimeError("boom")
        trace = load_trace(captured["run_id"])
        # Pessimistic default: yield raised, so outcome must be FAILED
        # even though the persisted trace was written from a finally.
        assert trace.outcome is RunOutcome.FAILED

    def test_keyboard_interrupt_recorded_as_failed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        captured: dict[str, str] = {}
        with (
            pytest.raises(KeyboardInterrupt),
            run_context(entrypoint="aeat test int", arguments=()) as info,
        ):
            captured["run_id"] = info.run_id
            raise KeyboardInterrupt
        trace = load_trace(captured["run_id"])
        # BaseException path: Ctrl-C must still leave a FAILED trace.
        assert trace.outcome is RunOutcome.FAILED


class TestRunContextRunIdValidation:
    def test_caller_supplied_bad_run_id_rejected_before_fs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A malicious run_id must never touch the filesystem.

        Before the fix, ``run_context(run_id="../etc")`` would create
        ``<runs_dir>/../etc/`` and an events.jsonl inside it before the
        save-time validator caught it. The validation now runs in
        ``_build_initial_context`` so no directory is ever created for
        a rejected run_id.
        """
        from . import RunTraceValidationError

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        for bad in ("../escape", "not-hex", "0" * 17, "ABCDEF0123456789"):
            with (
                pytest.raises(RunTraceValidationError),
                run_context(entrypoint="aeat test", arguments=(), run_id=bad),
            ):
                pass
            # No directory must have been created by the rejected enter.
            assert not any(tmp_path.iterdir()), f"rejected run_id {bad!r} left debris under {tmp_path}"

    def test_caller_supplied_valid_run_id_accepted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        with run_context(
            entrypoint="aeat test",
            arguments=(),
            run_id="cafebabecafebabe",
        ) as info:
            assert info.run_id == "cafebabecafebabe"
        trace = load_trace("cafebabecafebabe")
        assert trace.run_id == "cafebabecafebabe"


class TestRunIdPropagation:
    def test_run_id_is_identical_across_chain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        chain: Callable[[str], None] = _SubmissionStep(_InboxStep(_StatusStep()))
        with run_context(entrypoint="aeat test chain", arguments=()) as info:
            chain("alpha")
            chain("beta")
            run_id = info.run_id

        events = load_events(run_id)
        assert events, "expected at least one event after running the chain"
        run_ids = {evt.run_id for evt in events}
        assert run_ids == {run_id}
