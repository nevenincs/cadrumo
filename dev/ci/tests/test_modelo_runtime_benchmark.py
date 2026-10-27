"""Benchmark observations preserve behavior and exclude payloads on every exit."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo.adapters.persistence.storage.envelope.contract import Envelope
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue
from cadrumo.entrypoints.cli.tests import cli_runner
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.adapters.profile_worker import ProfileWorkerProcess
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections
from cadrumo_runtime.host.profile_host import RuntimeProfileHost
from cadrumo_runtime.host.profile_login import ProfileWorkerHumanLogin

from ..modelo_runtime_benchmark import (
    RuntimeBenchmarkRecorder,
    _observe_logging,
    observe_runtime_boundaries,
    observe_worker_composition,
    record_runtime_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RECORD = TypeAdapter(dict[str, object])


def test_diagnostic_timings_are_buffered_payload_free_and_restore_logger(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    logger = logging.Logger("isolated-benchmark")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    original = logging.Logger._log
    with pytest.MonkeyPatch.context() as patch:
        _observe_logging(patch, recorder)
        logger.warning("synthetic-private-log-message %s", "synthetic-private-argument")
        logger.warning("another-private-message")
        assert not recorder.path.exists()
        assert recorder.totals["diagnostics.logger_log"].calls == 2
        assert len(recorder.diagnostic_timeline) == 2
    assert logging.Logger._log is original
    recorder.flush()
    raw = recorder.path.read_bytes()
    assert b"private" not in raw
    rows = _records(raw)
    assert rows[-1]["event"] == "aggregate"
    assert rows[-2]["event"] == "diagnostic_timeline"
    assert [sample["call"] for sample in recorder.diagnostic_timeline] == [1, 2]
    assert all(sample["outcome"] == "ok" for sample in recorder.diagnostic_timeline)


def _records(raw: bytes) -> list[dict[str, object]]:
    return [_RECORD.validate_json(line) for line in raw.splitlines() if line.strip()]


def test_real_callable_receives_inputs_and_only_safe_metrics_are_retained(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    sensitive_text = "synthetic-secret-never-record-this"
    measured = recorder.wrap(str.upper, "text.upper")

    assert measured(sensitive_text) == sensitive_text.upper()

    raw = recorder.path.read_bytes()
    records = _records(raw)
    assert sensitive_text.encode() not in raw
    assert sensitive_text.upper().encode() not in raw
    assert records[0]["event"] == "start"
    assert records[-1]["outcome"] == "ok"
    assert isinstance(records[-1]["wall_seconds"], float)
    assert isinstance(records[-1]["thread_cpu_seconds"], float)
    assert isinstance(records[-1]["finished_monotonic_seconds"], float)


def test_exception_message_and_input_are_not_captured(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    sensitive_text = "synthetic-secret-invalid-json"
    measured = recorder.wrap(json.loads, "json.decode")

    with pytest.raises(json.JSONDecodeError):
        measured(sensitive_text)

    raw = recorder.path.read_bytes()
    assert sensitive_text.encode() not in raw
    assert _records(raw)[-1]["outcome"] == "JSONDecodeError"


@pytest.mark.parametrize("enabled", (False, True))
@pytest.mark.parametrize("fails_first", (False, True))
def test_first_admission_profile_is_optional_bounded_and_preserves_execution(
    tmp_path: Path,
    enabled: bool,
    fails_first: bool,
) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent", profile_first_admission=enabled)
    measured = recorder.wrap(json.loads, "admission.runtime_human")
    sensitive_text = "synthetic-private-admission-input"
    if fails_first:
        with pytest.raises(json.JSONDecodeError):
            measured(sensitive_text)
    else:
        assert measured(json.dumps(sensitive_text)) == sensitive_text
    assert measured("42") == 42
    raw = recorder.path.read_bytes()
    assert sensitive_text.encode() not in raw
    records = _records(raw)
    profiles = [row for row in records if row["event"] == "admission_profile"]
    assert len(profiles) == int(enabled)
    if enabled:
        profile = profiles[0]
        assert profile["timer"] == "perf_counter"
        assert profile["boundary"] == "admission.runtime_human"
        assert records.index(profile) > next(index for index, row in enumerate(records) if row["event"] == "finish")
        for ranking in ("by_self", "by_cumulative"):
            rows = TypeAdapter(list[dict[str, str | int | float]]).validate_python(profile[ranking])
            assert 0 < len(rows) <= 30
            assert all("self_wall_seconds" in row and "self_cpu_seconds" not in row for row in rows)
    finishes = [row for row in records if row["event"] == "finish"]
    assert [row["outcome"] for row in finishes] == ["JSONDecodeError" if fails_first else "ok", "ok"]


@pytest.mark.parametrize("enabled", (False, True))
def test_worker_setup_profile_finishes_before_body_and_preserves_composition(tmp_path: Path, enabled: bool) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="worker")
    lifecycle = []

    @contextmanager
    def composition() -> Generator[None]:
        lifecycle.append("entered")
        try:
            yield
        finally:
            lifecycle.append("released")

    original = ProfileWorkerHumanLogin.authenticate
    with observe_worker_composition(recorder, composition, profile_setup=enabled):
        assert lifecycle == ["entered"]
        assert ProfileWorkerHumanLogin.authenticate is not original
        records = _records(recorder.path.read_bytes())
        profiles = [row for row in records if row["event"] == "bootstrap_profile"]
        assert len(profiles) == int(enabled)
        finishes = [row["boundary"] for row in records if row["event"] == "finish"]
        assert finishes == [
            "startup.worker_fixture_entry",
            "startup.worker_observer_entry",
            "startup.worker_fixture_and_observer_setup",
        ]
        if enabled:
            assert profiles[0]["timer"] == "perf_counter"
            assert records[-1]["event"] == "bootstrap_profile"
    assert lifecycle == ["entered", "released"]
    assert ProfileWorkerHumanLogin.authenticate is original


def test_high_frequency_work_is_counted_without_per_call_file_writes(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    measured = recorder.wrap(math.sqrt, "operations.strict_schema")

    assert measured(9) == 3
    assert measured(16) == 4
    assert not recorder.path.exists()
    recorder.flush()

    records = _records(recorder.path.read_bytes())
    assert len(records) == 1
    assert records[0]["event"] == "aggregate"
    assert recorder.totals["operations.strict_schema"].calls == 2


def test_real_process_tree_owner_finalizes_and_retains_failure_measurement(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    original = RuntimeError("synthetic-private-exception-message")

    with pytest.raises(RuntimeError) as captured, record_runtime_tree(recorder), recorder.measure("sequence.total"):
        sum(range(10_000))
        raise original

    assert captured.value is original
    raw = recorder.path.read_bytes()
    assert str(original).encode() not in raw
    records = _records(raw)
    assert records[-1]["event"] == "process_tree"
    assert isinstance(records[-1]["wall_seconds"], float)
    assert isinstance(records[-1]["cpu_seconds"], float)


@pytest.mark.parametrize("profile", (False, True), ids=("timing-only", "first-decode-profile"))
def test_actual_catalogue_envelope_decode_is_unchanged_and_hooks_restore(tmp_path: Path, profile: bool) -> None:
    catalogue = CalculationRevisionCatalogue()
    original = Envelope[CalculationRevisionCatalogue](
        schema_version=1,
        written_at=datetime(2026, 4, 1, tzinfo=UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=catalogue,
    )
    wire = original.model_dump_json()
    expected = Envelope[CalculationRevisionCatalogue].model_validate_json(wire)
    descriptor = vars(BaseModel)["model_validate_json"]
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="worker", profile_first_decode=profile)

    with observe_runtime_boundaries(recorder):
        loaded = Envelope[CalculationRevisionCatalogue].model_validate_json(wire)
        again = Envelope[CalculationRevisionCatalogue].model_validate_json(wire)

    assert loaded == again == expected
    assert vars(BaseModel)["model_validate_json"] is descriptor
    raw = recorder.path.read_bytes()
    assert wire.encode() not in raw
    records = _records(raw)
    profiles = [row for row in records if row["event"] == "decode_profile"]
    assert len(profiles) == int(profile)
    if profile:
        assert profiles[0]["timer"] == "thread_time"
    decode_starts = [row for row in records if row["event"] == "start"]
    assert len(decode_starts) == 2
    assert all(row["payload_bytes"] == len(wire.encode()) for row in decode_starts)


def test_nested_runtime_observers_restore_after_actual_decode_failure(tmp_path: Path) -> None:
    original = vars(BaseModel)["model_validate_json"]
    original_worker_constructor = ProfileWorkerProcess.__init__
    original_frontend_login = FrontendClient.login_password
    original_worker_login = ProfileWorkerHumanLogin.authenticate
    admission_owners = (
        (RuntimeProfileConnections, "_login"),
        (RuntimeProfileConnections, "_prepare"),
        (RuntimeProfileConnections, "_host"),
        (RuntimeProfileConnections, "prepare_registry"),
        (RuntimeProfileConnections, "_admit_human_login"),
        (RuntimeProfileConnections, "_finish_login"),
        (RuntimeProfileConnections, "_status"),
        (RuntimeProfileConnections, "_sign_out_other_profiles"),
        (RuntimeProfileHost, "__init__"),
        (ProfileWorkerProcess, "_accept_startup_channel"),
        (ProfileWorkerProcess, "_open_worker_channels"),
        (ProfileWorkerHumanLogin, "bind"),
    )
    originals = [getattr(owner, name) for owner, name in admission_owners]
    outer = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    inner = RuntimeBenchmarkRecorder(tmp_path, role="worker")
    invalid_wire = "synthetic-private-invalid-catalogue"

    with observe_runtime_boundaries(outer):
        outer_descriptor = vars(BaseModel)["model_validate_json"]
        outer_constructor = ProfileWorkerProcess.__init__
        outer_frontend_login = FrontendClient.login_password
        outer_worker_login = ProfileWorkerHumanLogin.authenticate
        outer_admission = [getattr(owner, name) for owner, name in admission_owners]
        with pytest.raises(ValidationError), observe_runtime_boundaries(inner):
            Envelope[CalculationRevisionCatalogue].model_validate_json(invalid_wire)
        assert vars(BaseModel)["model_validate_json"] is outer_descriptor
        assert ProfileWorkerProcess.__init__ is outer_constructor
        assert FrontendClient.login_password is outer_frontend_login
        assert ProfileWorkerHumanLogin.authenticate is outer_worker_login
        assert all(
            getattr(owner, name) is observed
            for (owner, name), observed in zip(admission_owners, outer_admission, strict=True)
        )

    assert vars(BaseModel)["model_validate_json"] is original
    assert ProfileWorkerProcess.__init__ is original_worker_constructor
    assert FrontendClient.login_password is original_frontend_login
    assert ProfileWorkerHumanLogin.authenticate is original_worker_login
    assert all(
        getattr(owner, name) is original for (owner, name), original in zip(admission_owners, originals, strict=True)
    )
    for recorder in (outer, inner):
        raw = recorder.path.read_bytes()
        assert invalid_wire.encode() not in raw
        finishes = [row for row in _records(raw) if row["event"] == "finish"]
        assert len(finishes) == 1
        assert finishes[0]["outcome"] == "ValidationError"


def test_observed_real_cli_materialization_keeps_its_cache_and_restores_after_failure(tmp_path: Path) -> None:
    original = cli_runner.cadrumo_click_command
    expected = original()
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")

    with pytest.raises(RuntimeError), observe_runtime_boundaries(recorder):
        first = cli_runner.cadrumo_click_command()
        second = cli_runner.cadrumo_click_command()
        assert first is second is expected
        raise RuntimeError("leave the observed CLI scope")

    assert cli_runner.cadrumo_click_command is original
    assert original() is expected
    finished = [
        row
        for row in _records(recorder.path.read_bytes())
        if row["event"] == "finish" and row["boundary"] == "cli.cached_command"
    ]
    assert [row["call"] for row in finished] == [1, 2]
    assert all(row["outcome"] == "ok" for row in finished)
