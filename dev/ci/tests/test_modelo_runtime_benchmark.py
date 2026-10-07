"""Benchmark observations preserve behavior and exclude payloads on every exit."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo.adapters.persistence.storage.envelope.contract import Envelope
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.domain.modelos.calculation_repository import CalculationRevisionCatalogue

from ..modelo_runtime_benchmark import (
    RuntimeBenchmarkRecorder,
    observe_runtime_boundaries,
    record_runtime_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RECORD = TypeAdapter(dict[str, object])


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


def test_exception_message_and_input_are_not_captured(tmp_path: Path) -> None:
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    sensitive_text = "synthetic-secret-invalid-json"
    measured = recorder.wrap(json.loads, "json.decode")

    with pytest.raises(json.JSONDecodeError):
        measured(sensitive_text)

    raw = recorder.path.read_bytes()
    assert sensitive_text.encode() not in raw
    assert _records(raw)[-1]["outcome"] == "JSONDecodeError"


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
    outer = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    inner = RuntimeBenchmarkRecorder(tmp_path, role="worker")
    invalid_wire = "synthetic-private-invalid-catalogue"

    with observe_runtime_boundaries(outer):
        outer_descriptor = vars(BaseModel)["model_validate_json"]
        with pytest.raises(ValidationError), observe_runtime_boundaries(inner):
            Envelope[CalculationRevisionCatalogue].model_validate_json(invalid_wire)
        assert vars(BaseModel)["model_validate_json"] is outer_descriptor

    assert vars(BaseModel)["model_validate_json"] is original
    for recorder in (outer, inner):
        raw = recorder.path.read_bytes()
        assert invalid_wire.encode() not in raw
        finishes = [row for row in _records(raw) if row["event"] == "finish"]
        assert len(finishes) == 1
        assert finishes[0]["outcome"] == "ValidationError"
