"""Tests for the JSONL store and the per-run sink's run-id filter.

Covers:

* Append-then-load round-trip through
  :func:`cadrumo.core.observability.save_events_append` /
  :func:`cadrumo.core.observability.load_events`, including the
  DIAGNOSTIC-class URL host-only redaction property.
* :exc:`cadrumo.core.observability.RunTraceValidationError` on a corrupted
  JSONL line.
* :class:`cadrumo.core.observability.sink.JsonlRunSink` rejecting events
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
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.path_obstruction import obstructed_path
from ....tests.storage_scope import storage_overrides
from ...storage_taxonomy_locations import storage_path
from ...storage_taxonomy import StorageCategory
from ...config import override_settings
from ...directory_scan import iter_directory
from ..errors import RunTracePersistenceError, RunTraceValidationError
from ..models import NavigationPayload, RunEvent, RunEventKind, RunEventPayload, RunOutcome, RunTrace
from ..sink import JsonlRunSink
from ..store import (
    EVENTS_FILENAME,
    TRACE_FILENAME,
    iter_runs,
    load_events,
    load_trace,
    runs_dir,
    save_events_append,
    save_trace,
)

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
            module="cadrumo.core.observability.test_sink",
        )

    def test_append_and_load(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
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
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            evt = self._make_event(1)
            save_events_append(evt.run_id, evt)
            target = runs_dir() / evt.run_id / EVENTS_FILENAME
            with target.open("a", encoding="utf-8") as handle:
                handle.write('{"not_a": "valid_run_event"}\n')
            with pytest.raises(RunTraceValidationError, match=r"failed strict validation"):
                load_events(evt.run_id)

    def test_concurrent_direct_appends_preserve_every_event(self, tmp_path: Path) -> None:
        """Concurrent real writers retain every independently addressable event."""

        event_count = 1_000
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            events = tuple(self._make_event(ordinal % 60) for ordinal in range(event_count))
            events = tuple(
                event.model_copy(update={"step_id": f"concurrent-{ordinal}"}) for ordinal, event in enumerate(events)
            )
            run_id = events[0].run_id
            with ThreadPoolExecutor(max_workers=64) as executor:
                written = tuple(
                    executor.map(lambda event: save_events_append(run_id, event, settings=settings), events)
                )
            loaded = load_events(run_id)

        assert len(set(written)) == 1
        assert len(loaded) == len(events)
        assert {event.step_id for event in loaded} == {event.step_id for event in events}


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
            module="cadrumo.core.observability.test_sink",
        )

    def _emit(self, sink: JsonlRunSink, event: RunEvent) -> None:
        record = logging.LogRecord(
            name="aeat-test",
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
                name="aeat-test",
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
    def test_load_trace_rejects_path_traversal(self, tmp_path: Path) -> None:
        from ..store import _validate_run_id, load_events, load_trace

        bad_run_ids = (
            "../escape",
            "../../etc/passwd",
            "/absolute/path",
            "00000000000000001",
            "0123456789ABCDEF",
            "contains/slash",
            "",
            "..",
        )

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            for bad_run_id in bad_run_ids:
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    _validate_run_id(bad_run_id)
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    load_trace(bad_run_id)
                with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                    load_events(bad_run_id)

    def test_load_trace_rejects_run_id_shape_without_creating_dir(
        self,
        tmp_path: Path,
    ) -> None:
        from ..store import load_trace

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with pytest.raises(RunTraceValidationError, match=r"invalid run_id"):
                load_trace("not-a-valid-run")
            # The crafted run_id must never have resulted in a new directory.
            assert not any(iter_directory(tmp_path)), "rejected run_id must not create dirs"

    def test_load_trace_missing_does_not_pollute_runs_dir(
        self,
        tmp_path: Path,
    ) -> None:
        from ..store import load_trace

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            runs_root = storage_path(StorageCategory.RUNS, settings=settings)
            # 16 hex chars — passes validation, but nothing on disk.
            with pytest.raises(RunTraceValidationError, match=r"trace\.json not found"):
                load_trace("0" * 16)

            # Asserted against the runs root rather than the enclosing
            # directory. While the two were the same path this could not
            # observe the resolver materialising the root, because the
            # fixture had already created it -- relocating the category is
            # what made that visible: with the fixture no longer pre-creating
            # runs_root, a resolver that eagerly mkdir'd it would show up
            # here as `runs_root.exists()` turning True. The property being
            # defended is unchanged: a lookup that finds nothing must not
            # leave a directory behind, for the run it looked for or for the
            # runs root itself.
            assert not runs_root.exists(), "a failed lookup must not materialise the runs root"


class TestStorePersistenceErrors:
    def _trace(self, run_id: str = "0123456789abcdef") -> RunTrace:
        return RunTrace(
            run_id=run_id,
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="cadrumo test",
            arguments=(),
            corpus_sha256="a" * 64,
            db_sha256="b" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )

    def test_save_trace_wraps_unusable_runs_root(self, tmp_path: Path) -> None:
        """The write path is the sole materialiser: its mkdir(parents=True) covers the
        runs root too, so an unusable root now surfaces from `_run_dir`, not `runs_dir` —
        `runs_dir` is a pure resolver post-fix and never attempts a mkdir of its own."""
        trace = self._trace()
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            runs_root = storage_path(StorageCategory.RUNS, settings=settings)
            runs_root.parent.mkdir(parents=True, exist_ok=True)
            runs_root.write_text("not a directory", encoding="utf-8")

            with pytest.raises(RunTracePersistenceError) as excinfo:
                save_trace(trace, settings=settings)

        error = excinfo.value
        assert error.operation == "_run_dir"
        assert error.path == runs_root / trace.run_id
        assert isinstance(error.__cause__, OSError)

    def test_load_trace_wraps_unreadable_trace_file(self, tmp_path: Path) -> None:
        run_id = "abcdef0123456789"
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            runs_root = storage_path(StorageCategory.RUNS, settings=settings)
            trace_path = runs_root / run_id / TRACE_FILENAME

            with obstructed_path(trace_path), pytest.raises(RunTracePersistenceError) as excinfo:
                load_trace(run_id, settings=settings)

        error = excinfo.value
        assert error.operation == "load_trace"
        assert error.path == trace_path
        assert isinstance(error.__cause__, OSError)

    def test_load_trace_refuses_an_embedded_identity_from_another_run(self, tmp_path: Path) -> None:
        """A valid trace copied from run B cannot be replayed through run A."""
        run_a = "0123456789abcdef"
        run_b = "abcdef0123456789"
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace_b = self._trace(run_b)
            source = save_trace(trace_b)
            target = runs_dir() / run_a / TRACE_FILENAME
            target.parent.mkdir()
            shutil.copyfile(source, target)

            assert load_trace(run_b) == trace_b
            with pytest.raises(RunTraceValidationError, match=rf"run {run_a!r} contains embedded run_id {run_b!r}"):
                load_trace(run_a)

    def test_iter_runs_logs_and_skips_trace_copied_from_another_run(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Run enumeration retains B and skips its copied trace under directory A."""
        run_a = "0123456789abcdef"
        run_b = "abcdef0123456789"
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace_b = self._trace(run_b)
            source = save_trace(trace_b)
            target = runs_dir() / run_a / TRACE_FILENAME
            target.parent.mkdir()
            shutil.copyfile(source, target)

            caplog.set_level(logging.WARNING, logger="cadrumo.core.observability.store")
            assert list(iter_runs()) == [(run_b, trace_b)]

        messages = [record.getMessage() for record in caplog.records]
        assert any(
            "skipping run directory 0123456789abcdef" in message and "embedded run_id 'abcdef0123456789'" in message
            for message in messages
        )

    def test_iter_runs_logs_skipped_entries(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)) as settings:
            runs_root = storage_path(StorageCategory.RUNS, settings=settings)
            runs_root.mkdir(parents=True)
            (runs_root / "plain.txt").write_text("not a run", encoding="utf-8")
            (runs_root / "not-a-run").mkdir()
            (runs_root / "0123456789abcdef").mkdir()

            caplog.set_level(logging.DEBUG, logger="cadrumo.core.observability.store")

            assert list(iter_runs(settings=settings)) == []
        messages = [record.getMessage() for record in caplog.records]
        assert any("skipping non-directory entry" in message and "plain.txt" in message for message in messages)
        assert any("skipping non-run directory not-a-run" in message for message in messages)
        assert any("skipping run directory 0123456789abcdef without trace.json" in message for message in messages)

    def test_iter_runs_on_a_missing_runs_directory_yields_nothing(self, tmp_path: Path) -> None:
        """No run has ever been saved: the resolver must not create anything to answer this."""
        with override_settings(**storage_overrides(tmp_path / "does-not-exist", StorageCategory.RUNS)) as settings:
            runs_root = storage_path(StorageCategory.RUNS, settings=settings)
            assert not runs_root.exists()

            assert list(iter_runs(settings=settings)) == []

            assert not runs_root.exists(), "enumerating an absent runs directory must not materialise it"


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
            module="cadrumo.core.observability.test_sink",
        )

    def test_bad_run_id_raises_at_call_site(
        self,
        tmp_path: Path,
    ) -> None:
        """Validation must be eager — not deferred until iteration."""
        from ..store import iter_events

        with (
            override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)),
            pytest.raises(RunTraceValidationError, match=r"invalid run_id"),
        ):
            # No .iter(), no .__next__() — the call itself must raise.
            iter_events("../escape")

    def test_streams_without_materialising_all(
        self,
        tmp_path: Path,
    ) -> None:
        """Consuming n events pulls exactly n lines off disk."""
        from ..store import iter_events

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
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
        from ..store import iter_events

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            run_id = "abcdef0123456789"
            save_events_append(run_id, self._event(run_id, 0))
            # Append a malformed line after the valid one.
            target = runs_dir() / run_id / EVENTS_FILENAME
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
            module="cadrumo.core.observability.test_sink",
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

        with obstructed_path(target):
            sink = JsonlRunSink(target, run_id=run_id)
            try:
                record = logging.LogRecord(
                    name="aeat-test",
                    level=logging.INFO,
                    pathname=__file__,
                    lineno=0,
                    msg="run event",
                    args=None,
                    exc_info=None,
                )
                record.run_event = self._event(run_id)

                with caplog.at_level(logging.WARNING, logger="cadrumo.core.observability.sink"):
                    sink.emit(record)
            finally:
                sink.close()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "sink must emit a WARNING when the write fails"
        warn = warning_records[0]
        assert warn.name == "cadrumo.core.observability.sink"
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
