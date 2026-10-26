"""Two real exports prove the residual and keep corrupt audit evidence visible."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType, derive_bucket_event_id
from cadrumo.tests.env_scope import derived_storage_settings
from cadrumo.tests.golden_comparison import differing_paths, mask_document

from ..checks import discover_sequences
from ..compare import compare_transcript_to_golden, evaluate_expectations
from ..golden_store import (
    build_golden,
    mask_host_conditional_details,
    normalise_document_paths,
    normalise_frame_envelope,
)
from ..runner import SequenceTranscript, executed_sequence_sandbox

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture(scope="module")
def export_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[SequenceTranscript, SequenceTranscript]:
    enrolled, problems = discover_sequences(sequence_id="import-export-rows")
    assert not problems and len(enrolled) == 1
    runs = []
    authority_root = load_settings().cadrumo_authority_root
    with (
        derived_storage_settings(tmp_path_factory.mktemp("export-evidence-storage")),
        override_settings(cadrumo_authority_root=authority_root),
    ):
        for suffix in ("a", "b"):
            with executed_sequence_sandbox(
                enrolled[0].sequence, sandbox_root=tmp_path_factory.mktemp("export-evidence-" + suffix)
            ) as (_, transcript):
                assert not evaluate_expectations(enrolled[0].sequence, transcript, page=enrolled[0].page)
                result = _result(transcript)
                artifact = Path(transcript.workdir) / cast(str, result["output_path"])
                assert artifact.is_file()
                assert hashlib.sha256(artifact.read_bytes()).hexdigest() == result["sha256"]
                runs.append(transcript)
    return runs[0], runs[1]


def _result(transcript: SequenceTranscript) -> dict[str, JsonValue]:
    envelope = transcript.frames[1].envelope
    assert envelope is not None and isinstance(envelope["result"], dict)
    return envelope["result"]


def _mutated(
    transcript: SequenceTranscript, result: dict[str, JsonValue], *, argv: tuple[str, ...] | None = None
) -> SequenceTranscript:
    frame = transcript.frames[1]
    assert frame.envelope is not None
    changed = frame.model_copy(update={"envelope": {**frame.envelope, "result": result}, "argv": argv or frame.argv})
    return transcript.model_copy(update={"frames": (transcript.frames[0], changed)})


def _canonical_event(transcript: SequenceTranscript, destination: Path, *, actor: str | None = None) -> str:
    """Derive a real domain event for a changed destination or actor."""
    result = _result(transcript)
    rows = result["rows"]
    assert isinstance(rows, list)
    identities = []
    for row in rows:
        assert isinstance(row, dict) and isinstance(row["transaction_id"], str)
        identities.append(row["transaction_id"])
    ids = tuple(identities)
    return derive_bucket_event_id(
        bucket_id=transcript.profile_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_EXPORTED,
        occurred_at=transcript.frozen_instant,
        actor=actor or transcript.profile_id,
        object_type=BucketEventObjectType.LEDGER_EXPORT,
        object_id=cast(str, result["export_id"]),
        payload={
            "source_command": "aeat app ledger export",
            "export_format": cast(str, result["export_format"]),
            "include_inactive": "false",
            "row_count": str(result["row_count"]),
            "byte_size": str(result["byte_size"]),
            "sha256": cast(str, result["sha256"]),
            "output_path": str(destination),
            "transaction_ids_sha256": content_hash_hex(ids),
            "first_transaction_id": ids[0],
            "last_transaction_id": ids[-1],
        },
    )


def test_two_real_exports_differ_only_in_destination_bound_event_id(
    export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    documents: list[dict[str, object]] = []
    for transcript in export_runs:
        frame = transcript.frames[1]
        assert frame.envelope is not None
        normalised = mask_host_conditional_details(
            mask_document(
                normalise_document_paths(
                    frame.envelope, storage_root=transcript.storage_root, workdir=transcript.workdir
                )
            )
        )
        assert isinstance(normalised, dict)
        documents.append(normalised)
    assert differing_paths(documents[0], documents[1]) == {"result.bucket_event_ids[0]"}


def test_write_and_compare_share_verified_destination_normalization(
    export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    first, second = export_runs
    original = deepcopy(first.frames[1].envelope)
    golden = build_golden(first)
    assert golden.frames[1].envelope != first.frames[1].envelope
    assert not compare_transcript_to_golden(second, golden, page="how-to/import-bank-statements")
    assert first.frames[1].envelope == original


@pytest.mark.parametrize("mutation", ["wrong_hash", "malformed_id", "extra_id", "byte_size", "sha256", "export_id"])
def test_corrupt_export_evidence_stays_exact_and_fails_comparison(
    export_runs: tuple[SequenceTranscript, SequenceTranscript], mutation: str
) -> None:
    first, second = export_runs
    result = deepcopy(_result(second))
    if mutation == "wrong_hash":
        result["bucket_event_ids"] = ["a" * 64]
    elif mutation == "malformed_id":
        result["bucket_event_ids"] = ["invalid-event-id"]
    elif mutation == "extra_id":
        event_ids = result["bucket_event_ids"]
        assert isinstance(event_ids, list)
        result["bucket_event_ids"] = [*event_ids, "a" * 64]
    elif mutation == "byte_size":
        result["byte_size"] = cast(int, result["byte_size"]) + 1
    else:
        result[mutation] = "a" * 64
    changed = _mutated(second, result)
    frame = changed.frames[1]
    assert frame.envelope is not None
    normalised = normalise_frame_envelope(frame.envelope, frame=frame, transcript=changed)
    assert cast(dict[str, JsonValue], normalised["result"])["bucket_event_ids"] == result["bucket_event_ids"]
    assert compare_transcript_to_golden(changed, build_golden(first), page="how-to/import-bank-statements")


def test_real_event_for_wrong_actor_is_not_normalised(
    export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    first, second = export_runs
    result = deepcopy(_result(second))
    destination = Path(second.workdir) / cast(str, result["output_path"])
    result["bucket_event_ids"] = [_canonical_event(second, destination, actor="different-actor")]
    changed = _mutated(second, result)
    assert compare_transcript_to_golden(changed, build_golden(first), page="how-to/import-bank-statements")


def test_valid_event_for_outside_destination_is_not_normalised(
    export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    first, second = export_runs
    outside = Path(second.workdir).parent / "outside.csv"
    result = deepcopy(_result(second))
    result["output_path"] = str(outside)
    result["bucket_event_ids"] = [_canonical_event(second, outside)]
    argv = tuple(str(outside) if argument == "./ledger-2026-q1.csv" else argument for argument in second.frames[1].argv)
    changed = _mutated(second, result, argv=argv)
    frame = changed.frames[1]
    assert frame.envelope is not None
    normalised = normalise_frame_envelope(frame.envelope, frame=frame, transcript=changed)
    assert cast(dict[str, JsonValue], normalised["result"])["bucket_event_ids"] == result["bucket_event_ids"]
    assert compare_transcript_to_golden(changed, build_golden(first), page="how-to/import-bank-statements")


def test_other_commands_event_ids_are_not_normalised(
    export_runs: tuple[SequenceTranscript, SequenceTranscript],
) -> None:
    _, second = export_runs
    frame = second.frames[1]
    assert frame.envelope is not None
    changed = frame.model_copy(update={"envelope": {**frame.envelope, "command": "ledger.evidence.add"}})
    assert changed.envelope is not None
    normalised = normalise_frame_envelope(changed.envelope, frame=changed, transcript=second)
    assert cast(dict[str, JsonValue], normalised["result"])["bucket_event_ids"] == _result(second)["bucket_event_ids"]
