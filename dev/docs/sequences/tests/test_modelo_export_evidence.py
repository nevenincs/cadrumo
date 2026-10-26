"""Real fichero receipts prove portability without hiding corrupt audit joins."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from cadrumo.core.config import load_settings, override_settings
from cadrumo.tests.env_scope import derived_storage_settings
from cadrumo.tests.golden_comparison import differing_paths

from ..checks import discover_sequences
from ..compare import compare_transcript_to_golden, evaluate_expectations
from ..export_evidence import modelo_export_evidence_problem, normalise_modelo_export_evidence
from ..golden_store import SANDBOX_WORKDIR_PLACEHOLDER, build_golden, normalise_document_paths
from ..runner import SequenceTranscript, executed_sequence_sandbox
from .modelo_export_evidence_support import changed_modelo_export_event

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture(scope="module", params=["quickstart-export", "verification-reports-export-check"])
def modelo_export_runs(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[SequenceTranscript, SequenceTranscript]:
    sequence_id = str(request.param)
    enrolled, problems = discover_sequences(sequence_id=sequence_id)
    assert not problems and len(enrolled) == 1
    authority_root = load_settings().cadrumo_authority_root
    runs = []
    with (
        derived_storage_settings(tmp_path_factory.mktemp("modelo-export-storage")),
        override_settings(cadrumo_authority_root=authority_root),
    ):
        for suffix in ("a", "b"):
            with executed_sequence_sandbox(
                enrolled[0].sequence,
                sandbox_root=tmp_path_factory.mktemp(sequence_id + "-" + suffix),
            ) as (_, transcript):
                assert not evaluate_expectations(enrolled[0].sequence, transcript, page=enrolled[0].page)
                result = _result(transcript)
                artifact = Path(cast(str, result["output_path"]))
                assert artifact.is_file()
                assert hashlib.sha256(artifact.read_bytes()).hexdigest() == result["file_sha256"]
                assert artifact.stat().st_size == result["byte_size"]
                runs.append(transcript)
    return runs[0], runs[1]


def _result(transcript: SequenceTranscript) -> dict[str, JsonValue]:
    frame = transcript.result_frame
    assert frame.envelope is not None and isinstance(frame.envelope["result"], dict)
    return frame.envelope["result"]


def _normalised(transcript: SequenceTranscript) -> dict[str, JsonValue]:
    frame = transcript.result_frame
    assert frame.envelope is not None
    return normalise_modelo_export_evidence(
        frame.envelope,
        argv=frame.argv,
        profile_id=transcript.profile_id,
        instant=transcript.frozen_instant,
        workdir=transcript.workdir,
        destination_token=SANDBOX_WORKDIR_PLACEHOLDER,
    )


def _mutated(
    transcript: SequenceTranscript,
    result: dict[str, JsonValue],
    *,
    argv: tuple[str, ...] | None = None,
) -> SequenceTranscript:
    frame = transcript.result_frame
    assert frame.envelope is not None
    changed = frame.model_copy(update={"envelope": {**frame.envelope, "result": result}, "argv": argv or frame.argv})
    return transcript.model_copy(update={"frames": (*transcript.frames[:-1], changed)})


def test_real_modelo_events_bind_the_destination_and_share_portable_comparison(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    first, second = modelo_export_runs
    assert _result(first)["output_path"] != _result(second)["output_path"]
    assert _result(first)["bucket_event_id"] != _result(second)["bucket_event_id"]
    a, b = [], []
    for transcript in (first, second):
        frame = transcript.result_frame
        assert frame.envelope is not None
        a.append(
            normalise_document_paths(frame.envelope, storage_root=transcript.storage_root, workdir=transcript.workdir)
        )
        b.append(_normalised(transcript))
    assert differing_paths(a[0], a[1]) == {"result.bucket_event_id"}
    assert (
        cast(dict[str, JsonValue], b[0]["result"])["bucket_event_id"]
        == cast(dict[str, JsonValue], b[1]["result"])["bucket_event_id"]
    )
    assert not compare_transcript_to_golden(second, build_golden(first), page="export-evidence")


@pytest.mark.parametrize(
    "field",
    ["bucket_event_id", "file_sha256", "calculation_revision_id", "work_unit_id", "byte_size", "modelo", "filing_year"],
)
def test_wrong_modelo_evidence_is_not_normalised(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
    field: str,
) -> None:
    first, second = modelo_export_runs
    result = deepcopy(_result(second))
    if field == "byte_size":
        result[field] = cast(int, result[field]) + 1
    elif field == "filing_year":
        result[field] = 2025
    elif field == "modelo":
        result[field] = "999"
    else:
        result[field] = "a" * 64
    changed = _mutated(second, result)
    assert _normalised(changed) == changed.result_frame.envelope
    assert compare_transcript_to_golden(changed, build_golden(first), page="export-evidence")


def test_malformed_modelo_event_is_not_normalised(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    _, second = modelo_export_runs
    result = deepcopy(_result(second))
    result["bucket_event_id"] = "not-a-valid-event"
    changed = _mutated(second, result)
    assert _normalised(changed) == changed.result_frame.envelope


def test_coherent_wrong_artifact_digest_is_rejected_before_release_mask(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    first, second = modelo_export_runs
    result = deepcopy(_result(second))
    result["file_sha256"] = "a" * 64
    changed = _mutated(second, result)
    result["bucket_event_id"] = changed_modelo_export_event(changed)
    changed = _mutated(second, result)
    assert _normalised(changed) != changed.result_frame.envelope
    problems = compare_transcript_to_golden(changed, build_golden(first), page="export-evidence")
    assert any("artifact digest differs" in problem for problem in problems)


def test_missing_artifact_is_rejected_before_release_mask(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    _, second = modelo_export_runs
    destination = str(Path(second.workdir) / "missing-artifact.boe")
    assert not Path(destination).exists()
    result = deepcopy(_result(second))
    result["output_path"] = destination
    result["bucket_event_id"] = changed_modelo_export_event(second, destination=destination)
    arguments = list(second.result_frame.argv)
    arguments[arguments.index("--output") + 1] = destination
    changed = _mutated(second, result, argv=tuple(arguments))
    assert _normalised(changed) != changed.result_frame.envelope
    frame = changed.result_frame
    assert frame.envelope is not None
    assert (
        modelo_export_evidence_problem(
            frame.envelope,
            argv=frame.argv,
            profile_id=changed.profile_id,
            instant=changed.frozen_instant,
            workdir=changed.workdir,
        )
        == "fichero export artifact cannot be verified"
    )


@pytest.mark.parametrize("case", ["outside", "wrong_actor", "unsupported_payload"])
def test_valid_events_with_other_semantics_are_not_normalised(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
    case: str,
) -> None:
    first, second = modelo_export_runs
    assert changed_modelo_export_event(second) == _result(second)["bucket_event_id"]
    result = deepcopy(_result(second))
    argv = second.result_frame.argv
    if case == "outside":
        destination = str(Path(second.workdir).parent / "outside.boe")
        result["output_path"] = destination
        result["bucket_event_id"] = changed_modelo_export_event(second, destination=destination)
        arguments = list(argv)
        arguments[arguments.index("--output") + 1] = destination
        argv = tuple(arguments)
    elif case == "wrong_actor":
        result["bucket_event_id"] = changed_modelo_export_event(second, actor="different-actor")
    else:
        result["bucket_event_id"] = changed_modelo_export_event(second, unsupported=True)
    changed = _mutated(second, result, argv=argv)
    assert _normalised(changed) == changed.result_frame.envelope
    assert compare_transcript_to_golden(changed, build_golden(first), page="export-evidence")


def test_wallet_provenance_cannot_be_removed_or_changed(
    modelo_export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    _, second = modelo_export_runs
    wallet = _result(second)["iva_wallet_decision_provenance"]
    if wallet is None:
        return
    assert isinstance(wallet, dict)
    for value in (None, {**wallet, "decision_ref": "sha256:" + "a" * 64}):
        result = deepcopy(_result(second))
        result["iva_wallet_decision_provenance"] = value
        changed = _mutated(second, result)
        assert _normalised(changed) == changed.result_frame.envelope
