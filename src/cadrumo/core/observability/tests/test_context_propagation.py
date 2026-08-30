"""Verify run_id propagates across nested subpackage call sites.

Uses real, tiny classes that satisfy a structural Protocol — no mocks,
no patches. Each test stage is a small class that in turn calls into the
next, recording an event at every layer. The assertion is that every
recorded event carries the same ``run_id`` set by the outer
:func:`run_context`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from ....tests.storage_scope import storage_overrides
from ... import StorageCategory, storage_path
from ...config import override_settings
from ...directory_scan import scan_directory
from ..context import current_run_context, run_context
from ..errors import RunTracePersistenceError
from ..models import GenericPayload, RunEventKind, RunEventPayload, RunOutcome
from ..recorder import record_event
from ..store import EVENTS_FILENAME, TRACE_FILENAME, load_events, load_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Step(Protocol):
    """A trivial Protocol any chainable step satisfies structurally."""

    def __call__(self, label: str) -> None: ...


class _StatusStep:
    """Concrete status test stage."""

    def __call__(self, label: str) -> None:
        record_event(
            RunEventKind.ASSERTION,
            payload=RunEventPayload(generic=GenericPayload(fields=(("status", label),))),
        )


class _InboxStep:
    """Concrete inbox test stage, which calls into status next."""

    def __init__(self, downstream: _Step) -> None:
        self._downstream = downstream

    def __call__(self, label: str) -> None:
        record_event(
            RunEventKind.NAVIGATION,
            payload=RunEventPayload(generic=GenericPayload(fields=(("inbox", label),))),
        )
        self._downstream(label)


class _SubmissionStep:
    """Concrete submission test stage at the top of the chain."""

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
    ) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(entrypoint="cadrumo test ok", arguments=()) as info:
                run_id = info.run_id
            trace = load_trace(run_id)
            assert trace.outcome is RunOutcome.OK

    def test_outcome_failed_when_body_raises(self, tmp_path: Path) -> None:
        cases = (
            (RuntimeError("boom"), "cadrumo test fail"),
            (KeyboardInterrupt(), "cadrumo test int"),
        )

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            for exception, entrypoint in cases:
                captured: dict[str, str] = {}
                expected_error = (
                    pytest.raises(type(exception), match=str(exception))
                    if str(exception)
                    else pytest.raises(type(exception))
                )
                with (
                    expected_error,
                    run_context(entrypoint=entrypoint, arguments=()) as info,
                ):
                    captured["run_id"] = info.run_id
                    raise exception
                trace = load_trace(captured["run_id"])
                # Pessimistic default: yield raised, so outcome must be FAILED
                # even though the persisted trace was written from a finally.
                assert trace.outcome is RunOutcome.FAILED

    def test_trace_persistence_failure_surfaces_on_clean_exit(
        self,
        tmp_path: Path,
    ) -> None:
        run_id = "1111111111111111"
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            trace_path = storage_path(StorageCategory.RUNS, settings=settings) / run_id / TRACE_FILENAME
            with (
                pytest.raises(RunTracePersistenceError) as excinfo,
                run_context(entrypoint="cadrumo test persist fail", arguments=(), run_id=run_id),
            ):
                trace_path.mkdir(parents=True)

            assert excinfo.value.operation == "save_trace"
            assert excinfo.value.path == trace_path
            assert current_run_context() is None

    def test_trace_persistence_failure_does_not_mask_body_error(
        self,
        tmp_path: Path,
    ) -> None:
        run_id = "2222222222222222"
        with (
            override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)),
            pytest.raises(RuntimeError, match="primary failure"),
            run_context(entrypoint="cadrumo test body fail", arguments=(), run_id=run_id),
        ):
            (storage_path(StorageCategory.RUNS) / run_id / TRACE_FILENAME).mkdir(parents=True)
            raise RuntimeError("primary failure")

        assert current_run_context() is None


class TestRunContextRunIdValidation:
    def test_caller_supplied_bad_run_id_rejected_before_fs(self, tmp_path: Path) -> None:
        """A malicious run_id must never touch the filesystem.

        Before the fix, ``run_context(run_id="../etc")`` would create
        ``<runs_dir>/../etc/`` and an events.jsonl inside it before the
        save-time validator caught it. The validation now runs in
        ``_build_initial_context`` so no directory is ever created for
        a rejected run_id.
        """
        from ..errors import RunTraceValidationError

        bad_run_ids = ("../escape", "not-hex", "0" * 17, "ABCDEF0123456789")

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            for bad_run_id in bad_run_ids:
                before = scan_directory(tmp_path)
                with (
                    pytest.raises(RunTraceValidationError, match=r"invalid run_id"),
                    run_context(entrypoint="cadrumo test", arguments=(), run_id=bad_run_id),
                ):
                    pass
                # No directory must have been created by the rejected enter.
                assert scan_directory(tmp_path) == before, (
                    f"rejected run_id {bad_run_id!r} left debris under {tmp_path}"
                )

    def test_caller_supplied_valid_run_id_accepted(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(
                entrypoint="cadrumo test",
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
    ) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            chain: Callable[[str], None] = _SubmissionStep(_InboxStep(_StatusStep()))
            with run_context(entrypoint="cadrumo test chain", arguments=()) as info:
                chain("alpha")
                chain("beta")
                run_id = info.run_id

            events = load_events(run_id)
            assert events, "expected at least one event after running the chain"
            run_ids = {evt.run_id for evt in events}
            assert run_ids == {run_id}


class TestRunSinkScrubbing:
    """Real-behavior tests: JSONL sink records are scrubbed before persistence.

    The :func:`attach_run_sink` helper (contract) installs a
    :class:`cadrumo.core.logging.SecretScrubbingFilter` on the sink before
    attaching it to the root logger.  The JSONL serialiser also applies
    the DIAGNOSTIC-class redaction rule set, which SHA256-prefixes any
    NIF-shaped value.  Both layers must fire before bytes hit disk.

    No mocks: real :func:`run_context`, real JSONL file, real redaction.
    """

    # A valid Spanish NIF pattern: 8 digits + check letter.
    _PLAIN_NIF = "12345678Z"

    def test_nif_shaped_field_is_sha256_prefixed_in_jsonl(
        self,
        tmp_path: Path,
    ) -> None:
        """A NIF-shaped value in a GenericPayload field must not appear in plain text."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(entrypoint="cadrumo test scrub nif", arguments=()) as info:
                record_event(
                    RunEventKind.ASSERTION,
                    payload=RunEventPayload(generic=GenericPayload(fields=(("taxpayer_nif", self._PLAIN_NIF),))),
                )
                run_id = info.run_id

            jsonl_path = storage_path(StorageCategory.RUNS) / run_id / EVENTS_FILENAME
            assert jsonl_path.exists(), f"JSONL sink file not found: {jsonl_path}"

            raw_text = jsonl_path.read_text(encoding="utf-8")
            assert self._PLAIN_NIF not in raw_text, (
                f"plain NIF {self._PLAIN_NIF!r} found in JSONL output — scrubbing did not fire"
            )
            # The DIAGNOSTIC rule SHA256-prefixes NIF spans.
            assert "sha256:" in raw_text, (
                "expected sha256: prefix in JSONL output to confirm NIF was redacted, not absent"
            )

    def test_scrubbing_filter_present_on_sink_after_attach(
        self,
        tmp_path: Path,
    ) -> None:
        """The sink handler must carry a SecretScrubbingFilter after attach_run_sink."""
        from ...logging import SecretScrubbingFilter, attach_run_sink
        from ..sink import JsonlRunSink

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            sink = JsonlRunSink(tmp_path / "test_events.jsonl", run_id="a" * 16)
            attach_run_sink(sink)
            try:
                has_filter = any(isinstance(f, SecretScrubbingFilter) for f in sink.filters)
                assert has_filter, "SecretScrubbingFilter not installed on sink by attach_run_sink"
            finally:
                import logging

                logging.getLogger().removeHandler(sink)
                sink.close()

    def test_jsonl_lines_are_valid_json(
        self,
        tmp_path: Path,
    ) -> None:
        """Every JSONL line must deserialise cleanly after scrubbing is applied."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(entrypoint="cadrumo test scrub json", arguments=()) as info:
                record_event(
                    RunEventKind.NAVIGATION,
                    payload=RunEventPayload(generic=GenericPayload(fields=(("taxpayer_nif", self._PLAIN_NIF),))),
                )
                run_id = info.run_id

            jsonl_path = storage_path(StorageCategory.RUNS) / run_id / EVENTS_FILENAME
            lines = [ln for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            assert lines, "no JSONL lines written"
            for line in lines:
                parsed = json.loads(line)
                assert isinstance(parsed, dict), f"expected JSON object per line, got {type(parsed)}"
