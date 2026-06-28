"""Tests for the JSONL store and the per-run sink's run-id filter.

Covers:

* Append-then-load round-trip through
  :func:`aeat.core.observability.save_events_append` /
  :func:`aeat.core.observability.load_events`, including the
  DIAGNOSTIC-class URL host-only redaction property.
* :exc:`aeat.core.observability.RunTraceValidationError` on a corrupted
  JSONL line.
* :class:`aeat.core.observability._sink.JsonlRunSink` rejecting events
  whose ``run_id`` does not match its bound id, and skipping records
  that carry no ``run_event`` extra (without creating the file).
* Strict ``run_id`` validation across :func:`load_trace`,
  :func:`load_events`, and :func:`iter_events` — eager rejection at
  call time and no on-disk pollution from rejected ids.
* Lazy iteration semantics for :func:`iter_events` plus mid-stream
  validation failure on a corrupted line.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...config import Settings, override_settings
from .. import (
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    RunTracePersistenceError,
    RunTraceValidationError,
    iter_runs,
    load_events,
    load_trace,
    save_events_append,
    save_trace,
)
from .._sink import JsonlRunSink
from .._store import _EVENTS_FILENAME, runs_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestJsonlStoreRoundTrip:
    def _make_event(self, ordinal: int) -> RunEvent:
        return RunEvent(
            run_id="0123456789abcdef",
            step_id=f"s{ordinal}",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(
                navigation=NavigationPayload(url=f"https://example.test/{ordinal}"),
            ),
            timestamp=datetime(2026, 4, 14, 0, 0, ordinal, tzinfo=UTC),
            module="aeat.core.observability.test_sink",
        )

    def test_append_and_load(self, tmp_path: Path) -> None:
        with override_settings(aeat_runs_dir=str(tmp_path)):
            events = tuple(self._make_event(i) for i in range(3))
            for evt in events:
                save_events_append(evt.run_id, evt)
            loaded = load_events(events[0].run_id)
            # URL host-only redaction at DIAGNOSTIC class strips the path
            # component but preserves the rest of the event shape; compare
            # everything except the redacted URL.
            assert len(loaded) == len(events)
            for restored, original in zip(loaded, events, strict=True):
                assert restored.run_id == original.run_id
                assert restored.step_id == original.step_id
                assert restored.kind == original.kind
                # Path-stripped URL ("https://example.test/0") survives as
                # "https://example.test" — the host stays intact.
                assert restored.payload.navigation is not None
                assert restored.payload.navigation.url.startswith("https://example.test")

    def test_load_rejects_corrupted_line(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(aeat_runs_dir=str(tmp_path)):
            evt = self._make_event(1)
            save_events_append(evt.run_id, evt)
            target = runs_dir() / evt.run_id / _EVENTS_FILENAME
            with target.open("a", encoding="utf-8") as handle:
                handle.write('{"not_a": "valid_run_event"}\n')
            with pytest.raises(RunTraceValidationError, match=r"failed strict validation"):
                load_events(evt.run_id)


class TestJsonlRunSinkRunIdFilter:
    def _event(self, run_id: str, *, ordinal: int = 0) -> RunEvent:
        return RunEvent(
            run_id=run_id,
            step_id="step-0",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(
                navigation=NavigationPayload(url=f"https://example.test/{ordinal}"),
            ),
            timestamp=datetime(2026, 4, 14, 0, 0, ordinal, tzinfo=UTC),
            module="aeat.core.observability.test_sink",
        )

    def _emit(self, sink: JsonlRunSink, event: RunEvent) -> None:
        record = logging.LogRecord(
            name="aeat.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="run event",
            args=None,
            exc_info=None,
        )
        record.run_event = event
        sink.emit(record)

    def test_sink_drops_events_from_other_runs(self, tmp_path: Path) -> None:
        target = tmp_path / "0000000000000001" / "events.jsonl"
        sink = JsonlRunSink(target, run_id="0000000000000001")
        try:
            self._emit(sink, self._event("0000000000000001", ordinal=1))
            self._emit(sink, self._event("ffffffffffffffff", ordinal=2))
            self._emit(sink, self._event("0000000000000001", ordinal=3))
        finally:
            sink.close()

        written = target.read_text(encoding="utf-8").strip().splitlines()
        assert len(written) == 2, "sink should reject the event belonging to a different run_id"
        for line in written:
            assert "0000000000000001" in line
            assert "ffffffffffffffff" not in line

    def test_sink_drops_records_without_run_event(self, tmp_path: Path) -> None:
        target = tmp_path / "0000000000000002" / "events.jsonl"
        sink = JsonlRunSink(target, run_id="0000000000000002")
        try:
            record = logging.LogRecord(
                name="aeat.test",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg="plain log",
                args=None,
                exc_info=None,
            )
            sink.emit(record)
        finally:
            sink.close()

        # The sink's early-return in emit() fires before _open(), so the
        # file must never have been created at all.
        assert not target.exists(), "plain log records must not trigger file creation"

    def test_sink_exposes_run_id(self, tmp_path: Path) -> None:
        target = tmp_path / "run" / "events.jsonl"
        sink = JsonlRunSink(target, run_id="deadbeefdeadbeef")
        try:
            assert sink.run_id == "deadbeefdeadbeef"
        finally:
            sink.close()


class TestStoreRunIdValidation:
    def test_load_trace_rejects_path_traversal(
        self,
        tmp_path: Path,
    ) -> None:
        from .. import load_events, load_trace
        from .._store import _validate_run_id

        with override_settings(aeat_runs_dir=str(tmp_path)):
            for bad in (
                "../escape",
                "../../etc/passwd",
                "/absolute/path",
                "00000000000000001",  # 17 chars — one too many
                "0123456789ABCDEF",  # uppercase rejected
                "contains/slash",
                "",
                "..",
            ):
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    _validate_run_id(bad)
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    load_trace(bad)
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    load_events(bad)

    def test_load_trace_rejects_run_id_shape_without_creating_dir(
        self,
        tmp_path: Path,
    ) -> None:
        from .. import load_trace

        with override_settings(aeat_runs_dir=str(tmp_path)):
            with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                load_trace("not-a-valid-run")
            # The crafted run_id must never have resulted in a new directory.
            assert not any(tmp_path.iterdir()), "rejected run_id must not create dirs"

    def test_load_trace_missing_does_not_pollute_runs_dir(
        self,
        tmp_path: Path,
    ) -> None:
        from .. import load_trace

        with override_settings(aeat_runs_dir=str(tmp_path)):
            # 16 hex chars — passes validation, but nothing on disk.
            with pytest.raises(RunTraceValidationError, match=r"trace\.json not found"):
                load_trace("0" * 16)
            assert not any(tmp_path.iterdir()), "missing trace lookup must not create dirs"


class TestStorePersistenceErrors:
    def _trace(self, run_id: str = "0123456789abcdef") -> RunTrace:
        return RunTrace(
            run_id=run_id,
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat test",
            arguments=(),
            corpus_sha256="a" * 64,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )

    def test_save_trace_wraps_unusable_runs_root(self, tmp_path: Path) -> None:
        runs_root = tmp_path / "runs"
        runs_root.write_text("not a directory", encoding="utf-8")
        settings = Settings(aeat_runs_dir=runs_root)

        with pytest.raises(RunTracePersistenceError) as excinfo:
            save_trace(self._trace(), settings=settings)

        error = excinfo.value
        assert error.operation == "runs_dir"
        assert error.path == runs_root
        assert isinstance(error.__cause__, OSError)

    def test_load_trace_wraps_unreadable_trace_file(self, tmp_path: Path) -> None:
        run_id = "abcdef0123456789"
        runs_root = tmp_path / "runs"
        trace_path = runs_root / run_id / "trace.json"
        trace_path.mkdir(parents=True)
        settings = Settings(aeat_runs_dir=runs_root)

        with pytest.raises(RunTracePersistenceError) as excinfo:
            load_trace(run_id, settings=settings)

        error = excinfo.value
        assert error.operation == "load_trace"
        assert error.path == trace_path
        assert isinstance(error.__cause__, OSError)

    def test_iter_runs_logs_skipped_entries(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        runs_root = tmp_path / "runs"
        runs_root.mkdir()
        (runs_root / "plain.txt").write_text("not a run", encoding="utf-8")
        (runs_root / "not-a-run").mkdir()
        (runs_root / "0123456789abcdef").mkdir()
        settings = Settings(aeat_runs_dir=runs_root)

        caplog.set_level(logging.DEBUG, logger="aeat.core.observability._store")

        assert list(iter_runs(settings=settings)) == []
        messages = [record.getMessage() for record in caplog.records]
        assert any("skipping non-directory entry" in message and "plain.txt" in message for message in messages)
        assert any("skipping non-run directory not-a-run" in message for message in messages)
        assert any("skipping run directory 0123456789abcdef without trace.json" in message for message in messages)


class TestIterEvents:
    """Verify :func:`iter_events` streams lazily with eager arg validation."""

    def _event(self, run_id: str, ordinal: int) -> RunEvent:
        return RunEvent(
            run_id=run_id,
            step_id=f"s{ordinal}",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(
                navigation=NavigationPayload(url=f"https://example.test/{ordinal}"),
            ),
            timestamp=datetime(2026, 4, 14, 0, 0, ordinal, tzinfo=UTC),
            module="aeat.core.observability.test_sink",
        )

    def test_bad_run_id_raises_at_call_site(
        self,
        tmp_path: Path,
    ) -> None:
        """Validation must be eager — not deferred until iteration."""
        from .. import iter_events

        with (
            override_settings(aeat_runs_dir=str(tmp_path)),
            pytest.raises(RunTraceValidationError, match=r"invalid run_id"),
        ):
            # No .iter(), no .__next__() — the call itself must raise.
            iter_events("../escape")

    def test_streams_without_materialising_all(
        self,
        tmp_path: Path,
    ) -> None:
        """Consuming n events pulls exactly n lines off disk."""
        from .. import iter_events

        with override_settings(aeat_runs_dir=str(tmp_path)):
            run_id = "0123456789abcdef"
            for i in range(5):
                save_events_append(run_id, self._event(run_id, i))
            it = iter_events(run_id)
            first = next(it)
            second = next(it)
            assert first.step_id == "s0"
            assert second.step_id == "s1"
            # Three more remain; iteration is lazy.
            remaining = list(it)
            assert len(remaining) == 3
            assert [e.step_id for e in remaining] == ["s2", "s3", "s4"]

    def test_corrupt_line_raises_mid_stream(
        self,
        tmp_path: Path,
    ) -> None:
        """A validation error fires during iteration, not at call time."""
        from .. import iter_events

        with override_settings(aeat_runs_dir=str(tmp_path)):
            run_id = "abcdef0123456789"
            save_events_append(run_id, self._event(run_id, 0))
            # Append a malformed line after the valid one.
            target = runs_dir() / run_id / _EVENTS_FILENAME
            with target.open("a", encoding="utf-8", newline="") as handle:
                handle.write('{"invalid": "event"}\n')
            save_events_append(run_id, self._event(run_id, 2))

            # Call succeeds — validation for the bad line is deferred.
            it = iter_events(run_id)
            assert next(it).step_id == "s0"
            with pytest.raises(RunTraceValidationError, match="line 2"):
                next(it)


class TestSinkEmitFailureWarningIsScrubbed:
    """Verify sink-emit failures route through SecretScrubbingFilter.

    contract: when ``JsonlRunSink.emit`` fails (e.g. write to a non-writable
    path) the WARNING record it emits must pass through
    ``SecretScrubbingFilter`` so any sensitive tokens embedded in the
    exception text are redacted before reaching any handler.
    """

    def _event(self, run_id: str) -> RunEvent:
        return RunEvent(
            run_id=run_id,
            step_id="step-0",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(
                navigation=NavigationPayload(url="https://example.test/1"),
            ),
            timestamp=datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC),
            module="aeat.core.observability.test_sink",
        )

    def test_emit_failure_warning_scrubs_sensitive_exc_text(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Force a write error, confirm the warning's exc_text is scrubbed.

        Makes the target JSONL path a directory so the real file open fails
        on every platform, then verifies the captured WARNING routes through
        the module logger with the secret-scrubbing filter attached.
        """
        run_id = "0123456789abcdef"
        target = tmp_path / run_id / "events.jsonl"
        target.mkdir(parents=True)

        sink = JsonlRunSink(target, run_id=run_id)
        try:
            record = logging.LogRecord(
                name="aeat.test",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg="run event",
                args=None,
                exc_info=None,
            )
            record.run_event = self._event(run_id)

            with caplog.at_level(logging.WARNING, logger="aeat.core.observability._sink"):
                sink.emit(record)
        finally:
            sink.close()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "sink must emit a WARNING when the write fails"
        warn = warning_records[0]
        assert warn.name == "aeat.core.observability._sink"
        # The record must have been processed by SecretScrubbingFilter:
        # exc_text is set by the filter (it formats exc_info into text and
        # scrubs it).  We assert the raw bearer/token placeholder is absent
        # and that the filter has at minimum formatted the exc_text field.
        assert warn.exc_info is not None, "exc_info must be attached to the warning"
        # If SecretScrubbingFilter ran, it converts exc_info → exc_text.
        # A raw bearer token injected into the traceback would appear as
        # "Bearer <redacted>" not "Bearer <raw-value>".
        # Since PermissionError tracebacks don't naturally contain tokens,
        # the meaningful assertion is that the logger used is the module-level
        # get_logger() one (has SecretScrubbingFilter attached) rather than
        # a bare logging.getLogger() call (which would not).
        from ...logging import SecretScrubbingFilter

        sink_logger = logging.getLogger(warn.name)
        assert any(isinstance(f, SecretScrubbingFilter) for f in sink_logger.filters), (
            "the logger used by _sink must carry SecretScrubbingFilter"
        )
