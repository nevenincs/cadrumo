"""Real-behavior tests for the replay envelope-assertion tier.

These close the research F1 gap: replay now proves "the same JSON came
out", not only "the same argv re-runs". They exercise the real
:func:`cadrumo.core.observability.replay_run` path with its corpus-drift
gate, the persisted golden ``envelope.json`` artifact, the capture sink,
and the shared golden compare primitive — plus the ``run_context``
envelope-capture that persists the artifact in the first place.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from ....tests.storage_scope import storage_overrides
from ... import StorageCategory
from ...config import Settings, override_settings
from ...json_contract import OutputSchema, emit_json_success
from .. import (
    CadrumoObservabilityError,
    GoldenReplayMismatchError,
    RunOutcome,
    RunTrace,
    RunTraceValidationError,
    capture_envelopes,
    compute_corpus_sha256,
    load_envelope_document,
    replay_run,
    run_context,
    save_envelope,
    save_trace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)
_PROFILE_ID = "bafde89c-041e-4756-882b-933aaf16cad8"  # was '11111111-1111-1111-1111-111111111111'
_COMMAND = "golden demo"


class _GoldenResult(OutputSchema):
    label: str
    profile_id: str
    generated_at: datetime
    snapshot_id: str
    run_id: str


def _result(*, label: str = "ok", snapshot_id: str = "snap-A") -> _GoldenResult:
    return _GoldenResult(
        label=label,
        profile_id=_PROFILE_ID,
        generated_at=_INSTANT,
        snapshot_id=snapshot_id,
        run_id="run-x",
    )


def _capture_document(*, label: str = "ok", snapshot_id: str = "snap-A") -> dict[str, object]:
    import io

    with capture_envelopes() as sink:
        emit_json_success(_COMMAND, _result(label=label, snapshot_id=snapshot_id), stream=io.StringIO())
    return sink[-1]


def _build_trace(run_id: str, *, corpus_sha256: str) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=_INSTANT,
        finished_at=_INSTANT,
        entrypoint="cadrumo golden demo",
        arguments=(),
        corpus_sha256=corpus_sha256,
        db_sha256="b" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


def _save_replay_fixture(
    run_id: str,
    *,
    label: str = "ok",
    snapshot_id: str = "snap-A",
    with_envelope: bool = True,
) -> RunTrace:
    trace = _build_trace(run_id, corpus_sha256=compute_corpus_sha256(Settings()))
    save_trace(trace)
    if with_envelope:
        save_envelope(trace.run_id, _capture_document(label=label, snapshot_id=snapshot_id))
    return trace


def _emit_into_replay(*, label: str = "ok", snapshot_id: str = "snap-A"):
    import io

    def _invoke(_argv: list[str]) -> None:
        emit_json_success(_COMMAND, _result(label=label, snapshot_id=snapshot_id), stream=io.StringIO())

    return _invoke


class TestReplayEnvelopeAssertion:
    def test_matches_identical_replay(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("0123456789abcdef", snapshot_id="snap-A")

            result = replay_run(
                trace.run_id,
                invoke=_emit_into_replay(snapshot_id="snap-A"),
                assert_envelope=True,
            )
            assert result.run_id == trace.run_id

    def test_masked_field_divergence_still_matches(self, tmp_path: Path) -> None:
        """A differing ``snapshot_id`` is masked, so replay still passes."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("1111222233334444", snapshot_id="snap-A")

            # Re-entry emits a DIFFERENT snapshot_id — the opaque surrogate
            # key the substrate is licensed to mask.
            replay_run(
                trace.run_id,
                invoke=_emit_into_replay(snapshot_id="snap-DIFFERENT"),
                assert_envelope=True,
            )

    def test_unmasked_divergence_raises(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("aaaabbbbccccdddd", label="ok")

            with pytest.raises(GoldenReplayMismatchError) as excinfo:
                replay_run(
                    trace.run_id,
                    invoke=_emit_into_replay(label="TAMPERED"),
                    assert_envelope=True,
                )
            assert any("label" in path for path in excinfo.value.differing_paths)

    def test_no_emitted_envelope_raises(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("deadbeefcafe0001")

            def _silent(_argv: list[str]) -> None:
                return None

            with pytest.raises(CadrumoObservabilityError, match="emitted no"):
                replay_run(trace.run_id, invoke=_silent, assert_envelope=True)

    def test_missing_golden_artifact_raises(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("0f0f0f0f0f0f0f0f", with_envelope=False)
            with pytest.raises(RunTraceValidationError, match=r"envelope\.json not found"):
                replay_run(
                    trace.run_id,
                    invoke=_emit_into_replay(),
                    assert_envelope=True,
                )

    def test_assert_envelope_off_is_backward_compatible(self, tmp_path: Path) -> None:
        """Default ``assert_envelope=False`` replays without needing a golden artifact."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            trace = _save_replay_fixture("ccccddddeeeeffff", with_envelope=False)
            result = replay_run(trace.run_id, invoke=_emit_into_replay())
            assert result.run_id == trace.run_id


class TestDbStatePostTier:
    """The optional post-state ``db_sha256`` tier (state-transition determinism)."""

    def test_matching_db_state_passes(self) -> None:
        from .._replay import _assert_db_state_unchanged

        # A true no-op: recorded == observed → no raise.
        _assert_db_state_unchanged("0123456789abcdef", "a" * 64, "a" * 64)

    def test_drifted_db_state_raises(self) -> None:
        from .._replay import _assert_db_state_unchanged

        with pytest.raises(CadrumoObservabilityError, match="db-state drift"):
            _assert_db_state_unchanged("0123456789abcdef", "a" * 64, "b" * 64)


class TestRunContextPersistsEnvelope:
    """``run_context`` captures and persists the emitted envelope as a golden artifact."""

    def test_emitted_envelope_is_persisted(self, tmp_path: Path) -> None:
        import io

        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(entrypoint="cadrumo golden demo", arguments=()) as info:
                run_id = info.run_id
                emit_json_success(_COMMAND, _result(snapshot_id="snap-run"), stream=io.StringIO())

            persisted = cast("dict[str, Any]", load_envelope_document(run_id))
            assert persisted["command"] == _COMMAND
            assert persisted["result"]["snapshot_id"] == "snap-run"

    def test_run_without_emit_persists_no_envelope(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            with run_context(entrypoint="cadrumo golden demo", arguments=()) as info:
                run_id = info.run_id
            # No JSON emitted → no golden artifact written.
            with pytest.raises(RunTraceValidationError, match="not found"):
                load_envelope_document(run_id)
