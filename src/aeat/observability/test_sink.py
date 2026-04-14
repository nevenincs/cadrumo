"""JSONL store round-trip and corruption-detection tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.observability import (
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunTraceValidationError,
    load_events,
    save_events_append,
)
from aeat.observability._store import _EVENTS_FILENAME, runs_dir


@pytest.mark.unit
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
