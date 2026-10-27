"""Profile timing observations preserve execution and cumulative snapshot meaning."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from ..profile_wizard_benchmark import ProfileBenchmarkRecorder, _observe, _observe_profile_boundaries, summarize

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_observer_preserves_result_exception_and_excludes_payload(tmp_path: Path) -> None:
    recorder = ProfileBenchmarkRecorder(tmp_path, role="parent")
    owner = SimpleNamespace(decode=json.loads)
    original = owner.decode
    with pytest.MonkeyPatch.context() as patch:
        _observe(patch, recorder, owner, "decode", "safe.decode")
        assert owner.decode('{"synthetic-private": 42}') == {"synthetic-private": 42}
        with pytest.raises(json.JSONDecodeError):
            owner.decode("synthetic-private-invalid")
    assert owner.decode is original
    recorder.flush()
    raw = recorder.path.read_text(encoding="utf-8")
    assert "synthetic-private" not in raw
    assert recorder.totals["safe.decode"].calls == 2
    assert len(recorder.samples["safe.decode"]) == 2


def test_summary_uses_last_distribution_and_omits_small_sample_percentiles(tmp_path: Path) -> None:
    recorder = ProfileBenchmarkRecorder(tmp_path, role="parent")
    with recorder.measure("one", aggregate=True):
        pass
    recorder.flush()
    with recorder.measure("one", aggregate=True):
        pass
    for _ in range(20):
        with recorder.measure("many", aggregate=True):
            pass
    recorder.flush()
    summarize(tmp_path, 0)
    result = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    process = result["processes"][0]
    assert process["totals"]["one"]["calls"] == 2
    assert process["distributions"]["one"]["calls"] == 2
    assert process["distributions"]["one"]["wall_seconds"]["total"] == process["totals"]["one"]["wall_seconds"]
    assert "p95" not in process["distributions"]["one"]["wall_seconds"]
    many = process["distributions"]["many"]["wall_seconds"]
    assert many["min"] <= many["p50"] <= many["p95"] <= many["max"]


def test_sql_commit_attribution_preserves_transaction_and_restores_hooks(tmp_path: Path) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    recorder = ProfileBenchmarkRecorder(tmp_path, role="parent")
    original = Session.commit
    engine = create_engine("sqlite://")
    with pytest.MonkeyPatch.context() as patch:
        _observe_profile_boundaries(patch, recorder)
        with Session(engine) as session:
            session.execute(text("CREATE TABLE benchmark (value INTEGER)"))
            session.commit()
            with recorder.measure("profile.record_write_transaction", aggregate=True):
                session.execute(text("INSERT INTO benchmark VALUES (42)"))
                session.commit()
        with Session(engine) as reopened:
            assert reopened.scalar(text("SELECT value FROM benchmark")) == 42
    assert Session.commit is original
    assert recorder.totals["storage.sql_commit.profile"].calls == 1
    assert recorder.totals["storage.sql_commit.other"].calls == 1
    recorder.flush()
    summarize(tmp_path, 0)
    process = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["processes"][0]
    commits = [entry for entry in process["timeline"] if entry["boundary"] == "storage.sql_commit.profile"]
    assert len(commits) == 1
    assert commits[0]["call"] == 1
    assert commits[0]["finished_monotonic_seconds"] > commits[0]["wall_seconds"]
    engine.dispose()


def test_kdf_lease_observer_releases_on_body_failure_and_restores_owner(tmp_path: Path) -> None:
    from cadrumo.adapters.persistence.storage.custody import kdf_supervision

    recorder = ProfileBenchmarkRecorder(tmp_path, role="parent")
    lifecycle: list[str] = []

    @contextmanager
    def lease(*, deadline: float) -> Generator[None]:
        assert deadline == 42
        lifecycle.append("acquired")
        try:
            yield
        finally:
            lifecycle.append("released")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(kdf_supervision, "profile_kdf_lease", lease)
        with pytest.MonkeyPatch.context() as observer:
            _observe_profile_boundaries(observer, recorder)
            with pytest.raises(ValueError, match="synthetic failure"), kdf_supervision.profile_kdf_lease(deadline=42):
                assert lifecycle == ["acquired"]
                raise ValueError("synthetic failure")
        assert kdf_supervision.profile_kdf_lease is lease
    assert lifecycle == ["acquired", "released"]
    assert recorder.totals["kdf.lease_acquire"].calls == 1
