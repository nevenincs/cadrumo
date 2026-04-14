"""Tests for deterministic dry-run replay and its refusal modes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.config import PROJECT_ROOT, Settings
from aeat.observability import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    RunOutcome,
    RunTrace,
    compute_corpus_sha256,
    replay_run,
    save_trace,
)


def _build_trace(run_id: str, *, corpus_sha256: str) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=datetime(2026, 4, 14, tzinfo=UTC),
        finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
        entrypoint="aeat hello",
        arguments=(),
        corpus_sha256=corpus_sha256,
        db_sha256="b" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


@pytest.mark.unit
class TestReplayRun:
    def test_clean_dry_run_round_trip(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        current_corpus = compute_corpus_sha256(PROJECT_ROOT / ".vault", Settings())
        trace = _build_trace("0123456789abcdef", corpus_sha256=current_corpus)
        save_trace(trace)
        result = replay_run(trace.run_id, dry_run=True)
        assert result.run_id == trace.run_id
        assert result.entrypoint == "aeat hello"

    def test_refuses_on_corpus_drift(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        trace = _build_trace("fedcba9876543210", corpus_sha256="0" * 64)
        save_trace(trace)
        with pytest.raises(AeatCorpusDriftError) as excinfo:
            replay_run(trace.run_id, dry_run=True)
        assert excinfo.value.run_id == trace.run_id
        assert excinfo.value.recorded == "0" * 64
        assert excinfo.value.observed != "0" * 64

    def test_refuses_no_dry_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        trace = _build_trace("abcdef0123456789", corpus_sha256="1" * 64)
        save_trace(trace)
        with pytest.raises(AeatObservabilityError):
            replay_run(trace.run_id, dry_run=False)
