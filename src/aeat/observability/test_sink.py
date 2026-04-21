"""JSONL store round-trip and corruption-detection tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from . import (
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunTraceValidationError,
    load_events,
    save_events_append,
)
from ._sink import JsonlRunSink
from ._store import _EVENTS_FILENAME, runs_dir

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


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
            module="aeat.observability.test_sink",
        )

    def test_append_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        events = tuple(self._make_event(i) for i in range(3))
        for evt in events:
            save_events_append(evt.run_id, evt)
        loaded = load_events(events[0].run_id)
        assert loaded == events

    def test_load_rejects_corrupted_line(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        evt = self._make_event(1)
        save_events_append(evt.run_id, evt)
        target = runs_dir() / evt.run_id / _EVENTS_FILENAME
        with target.open("a", encoding="utf-8") as handle:
            handle.write('{"not_a": "valid_run_event"}\n')
        with pytest.raises(RunTraceValidationError):
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
            module="aeat.observability.test_sink",
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

        assert not target.exists() or target.read_text(encoding="utf-8") == ""

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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from . import load_events, load_trace
        from ._store import _validate_run_id

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
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
            with pytest.raises(RunTraceValidationError):
                _validate_run_id(bad)
            with pytest.raises(RunTraceValidationError):
                load_trace(bad)
            with pytest.raises(RunTraceValidationError):
                load_events(bad)

    def test_load_trace_rejects_run_id_shape_without_creating_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from . import load_trace

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        with pytest.raises(RunTraceValidationError):
            load_trace("not-a-valid-run")
        # The crafted run_id must never have resulted in a new directory.
        assert not any(tmp_path.iterdir()), "rejected run_id must not create dirs"

    def test_load_trace_missing_does_not_pollute_runs_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from . import load_trace

        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        # 16 hex chars — passes validation, but nothing on disk.
        with pytest.raises(RunTraceValidationError):
            load_trace("0" * 16)
        assert not any(tmp_path.iterdir()), "missing trace lookup must not create dirs"
