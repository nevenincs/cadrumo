"""Real-behaviour tests for the golden store and comparison tier.

Every golden in these tests is produced by executing a REAL sequence against the
real CLI in a fresh hermetic sandbox and fingerprinting its record through the
real store — never hand-shaped fixtures. Divergence cases mutate the RECORD a
golden was fingerprinted from (the exact drift a CLI behaviour change would
produce between the committed golden and a later run) and assert the comparison
names the frame and, when the earlier record is cached as a baseline, the
differing paths or unified diff. The mutation tests double as the fingerprint's
anti-tautology proof: an output change the digest failed to detect would void
every clean pass in the suite.
"""

from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from pydantic import JsonValue

from cadrumo.tests.golden_comparison import MASK_SENTINEL

from .. import compare, record_store
from ..compare import (
    assert_transcript_matches_golden,
    check_transcript,
    compare_transcript_to_golden,
    evaluate_expectations,
)
from ..errors import SequenceGoldenError, SequenceGoldenMismatchError
from ..golden_store import (
    REPO_ROOT_PLACEHOLDER,
    SANDBOX_STORAGE_ROOT_PLACEHOLDER,
    SANDBOX_WORKDIR_PLACEHOLDER,
    SequenceGolden,
    _repo_root,
    golden_path,
    normalise_document_paths,
    normalise_text_output,
    read_golden,
    write_golden,
)
from ..parser import parse_sequence
from ..record_store import SequenceRecord, build_record, golden_from_record
from ..runner import FrameExecution, SequenceTranscript, execute_sequence
from ..schema import FrameKind, ParsedSequence

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/compare-gate"

#: A light all-JSON sequence: two real ``config profile list`` reads, a capture
#: from the envelope spine, and semantic expectations on the result frame.
_JSON_BODY = "\n".join(
    [
        "aeat --format json config profile list",
        "@capture run_status status",
        "@result aeat --format json config profile list",
        '@expect status == "success"',
        "@expect exit_code == 0",
    ],
)

#: A sequence whose first frame is human-readable text output.
_TEXT_BODY = "\n".join(
    [
        "aeat config profile list",
        "@result aeat --format json config profile list",
        '@expect status == "success"',
    ],
)


def _json_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="compare-json-case",
        options={"verify": "Verify the profile listing succeeds."},
        body=_JSON_BODY,
    )


def _text_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="compare-text-case",
        options={"verify": "Verify the profile listing succeeds."},
        body=_TEXT_BODY,
    )


def _golden(transcript: SequenceTranscript) -> SequenceGolden:
    """Return the golden fingerprint refresh would commit for ``transcript``."""
    return golden_from_record(build_record(transcript))


def _drifted(
    transcript: SequenceTranscript,
    mutate: Callable[[dict[str, object]], None],
) -> tuple[SequenceGolden, SequenceRecord]:
    """Return the golden and record of an earlier run whose output ``mutate`` changed.

    The record is re-validated strictly in JSON mode, exactly as the store's
    reader does, and the golden is fingerprinted from it, so the pair is what a
    refresh of that earlier output would have left behind.
    """
    document = build_record(transcript).model_dump(mode="json")
    mutate(document)
    record = SequenceRecord.model_validate_json(json.dumps(document))
    return golden_from_record(record), record


def _write(transcript: SequenceTranscript, root: Path) -> Path:
    """Commit ``transcript``'s golden under ``root`` the way refresh does."""
    return write_golden(_golden(transcript), page=_PAGE, goldens_root=root)


@pytest.fixture(scope="module")
def json_run(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real execution of the JSON sequence, shared across this module."""
    return execute_sequence(_json_sequence(), sandbox_root=tmp_path_factory.mktemp("json-run-a"))


@pytest.fixture(scope="module")
def text_run(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real execution of the text sequence, shared across this module."""
    return execute_sequence(_text_sequence(), sandbox_root=tmp_path_factory.mktemp("text-run-a"))


class TestGoldenStoreRoundtrip:
    def test_write_read_roundtrip_is_strictly_equal(self, json_run: SequenceTranscript, tmp_path: Path) -> None:
        target = _write(json_run, tmp_path)
        assert target == golden_path(_PAGE, json_run.sequence_id, goldens_root=tmp_path)
        assert target.is_file()

        loaded = read_golden(_PAGE, json_run.sequence_id, goldens_root=tmp_path)
        assert loaded == _golden(json_run)
        # The committed artifact is canonical review-diffable JSON.
        raw = target.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        assert json.loads(raw)["sequence_id"] == json_run.sequence_id

    def test_the_committed_golden_stores_no_output(self, json_run: SequenceTranscript, tmp_path: Path) -> None:
        """Only the fingerprint is committed: no envelope or text body reaches the file."""
        document = json.loads(_write(json_run, tmp_path).read_text(encoding="utf-8"))
        for frame in document["frames"]:
            assert set(frame) == {
                "kind",
                "argv",
                "exit_code",
                "captures",
                "envelope_source",
                "output_sha256",
                "output_bytes",
            }
            assert len(frame["output_sha256"]) == 64

    def test_a_golden_that_stores_output_is_refused(self, json_run: SequenceTranscript, tmp_path: Path) -> None:
        """A schema-2 golden carrying its envelope is refused with the refresh remedy."""
        target = _write(json_run, tmp_path)
        document = json.loads(target.read_text(encoding="utf-8"))
        document["golden_schema_version"] = 2
        document["frames"][0]["envelope"] = json_run.frames[0].envelope
        target.write_text(json.dumps(document), encoding="utf-8")

        with pytest.raises(SequenceGoldenError, match="refresh --sequence compare-json-case"):
            read_golden(_PAGE, json_run.sequence_id, goldens_root=tmp_path)

    def test_missing_golden_names_the_refresh_invocation(self, tmp_path: Path) -> None:
        with pytest.raises(SequenceGoldenError, match="refresh --sequence compare-json-case"):
            read_golden(_PAGE, "compare-json-case", goldens_root=tmp_path)

    def test_hand_edited_golden_with_extra_key_is_refused(
        self,
        json_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """The strict schema is the structural guard against hand-edits — in
        particular a smuggled per-sequence mask extension key is refused."""
        target = _write(json_run, tmp_path)
        document = json.loads(target.read_text(encoding="utf-8"))
        document["mask_fields"] = ["created_at"]
        target.write_text(json.dumps(document), encoding="utf-8")

        with pytest.raises(SequenceGoldenError, match="never hand-edited"):
            read_golden(_PAGE, json_run.sequence_id, goldens_root=tmp_path)


class TestJsonFrameComparison:
    def test_fresh_rerun_matches_the_committed_golden_cleanly(
        self,
        json_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """The full check tier over two REAL runs: golden written from run A,
        run B executed in a fresh sandbox, zero problems end to end."""
        _write(json_run, tmp_path)
        golden = read_golden(_PAGE, json_run.sequence_id, goldens_root=tmp_path)

        rerun = execute_sequence(_json_sequence(), sandbox_root=tmp_path / "json-run-b")
        problems = check_transcript(_json_sequence(), rerun, golden, page=_PAGE)
        assert problems == ()

    @staticmethod
    def _status_drift(document: dict[str, object]) -> None:
        frames = cast("list[dict[str, object]]", document["frames"])
        envelope = cast("dict[str, object]", frames[0]["envelope"])
        envelope["status"] = "warning"

    def test_envelope_drift_names_frame_and_differing_paths(self, json_run: SequenceTranscript) -> None:
        golden, baseline = _drifted(json_run, self._status_drift)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE, baseline=baseline)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert "status" in problems[0]
        assert _PAGE in problems[0] and json_run.sequence_id in problems[0]

    def test_envelope_drift_is_detected_without_a_cached_baseline(self, json_run: SequenceTranscript) -> None:
        """The digest alone decides the verdict: with no earlier record to diff
        against, the changed frame is still named, with both digests."""
        golden, _ = _drifted(json_run, self._status_drift)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert "output changed" in problems[0] and str(golden.frames[0].output_sha256) in problems[0]

    def test_deleted_envelope_field_is_detected(self, json_run: SequenceTranscript) -> None:
        """Anti-tautology proof: an earlier output that lacked a field must not
        fingerprint like the live one — a pass here would void every clean pass
        in the suite."""

        def _drop(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            envelope = cast("dict[str, object]", frames[1]["envelope"])
            del envelope["active_profile"]

        golden, baseline = _drifted(json_run, _drop)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE, baseline=baseline)
        assert len(problems) == 1
        assert "frame 1" in problems[0]
        assert "active_profile" in problems[0]

    def test_a_masked_value_difference_fingerprints_identically(self, json_run: SequenceTranscript) -> None:
        """The digest covers the compared form, so a centrally masked leaf that
        differs between runs cannot move it, while the same change on any other
        key does (the deleted-field and status cases above)."""

        def _reidentify(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            envelope = cast("dict[str, object]", frames[0]["envelope"])
            envelope["run_id"] = "a-surrogate-id-only-this-run-minted"

        golden, _ = _drifted(json_run, _reidentify)
        live = _golden(json_run)
        live_envelope = json_run.frames[0].envelope
        assert live_envelope is not None and "run_id" not in live_envelope
        # Adding the masked key is still a structural change the digest sees...
        assert golden.frames[0].output_sha256 != live.frames[0].output_sha256

        def _both(value: str) -> Callable[[dict[str, object]], None]:
            def _set(document: dict[str, object]) -> None:
                frames = cast("list[dict[str, object]]", document["frames"])
                cast("dict[str, object]", frames[0]["envelope"])["run_id"] = value

            return _set

        # ...but two runs that differ ONLY in the masked value fingerprint the same.
        first, _ = _drifted(json_run, _both("minted-on-run-a"))
        second, _ = _drifted(json_run, _both("minted-on-run-b"))
        assert first == second

    def test_exit_code_drift_is_a_named_failure(self, json_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            frames[-1]["exit_code"] = 3

        golden, _ = _drifted(json_run, _drift)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE)
        assert any("exit code 0, golden expects 3" in problem for problem in problems)

    def test_frame_count_drift_is_a_named_failure(self, json_run: SequenceTranscript) -> None:
        def _drop_frame(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            del frames[0]

        golden, _ = _drifted(json_run, _drop_frame)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE)
        assert len(problems) == 1
        assert "frame count changed" in problems[0]

    def test_capture_drift_is_a_named_failure(self, json_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            captures = cast("list[dict[str, object]]", frames[0]["captures"])
            captures[0]["value"] = "warning"

        golden, _ = _drifted(json_run, _drift)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE)
        assert any("captured values diverged" in problem for problem in problems)

    def test_mismatch_assertion_carries_every_problem_and_the_remedy(
        self,
        json_run: SequenceTranscript,
    ) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            envelope = cast("dict[str, object]", frames[0]["envelope"])
            envelope["status"] = "warning"
            frames[-1]["exit_code"] = 3

        golden, _ = _drifted(json_run, _drift)
        with pytest.raises(SequenceGoldenMismatchError) as excinfo:
            assert_transcript_matches_golden(_json_sequence(), json_run, golden, page=_PAGE)

        message = str(excinfo.value)
        assert "refresh --sequence compare-json-case" in message
        assert len(excinfo.value.problems) == 2


class TestTextFrameComparison:
    def test_text_frames_roundtrip_and_compare_cleanly(self, text_run: SequenceTranscript, tmp_path: Path) -> None:
        _write(text_run, tmp_path)
        golden = read_golden(_PAGE, text_run.sequence_id, goldens_root=tmp_path)
        assert golden.frames[0].envelope_source is None

        first = build_record(text_run).frames[0]
        assert first.text is not None and first.envelope is None
        # The record is run-independent: no sandbox path survives.
        assert text_run.storage_root not in first.text
        assert text_run.workdir not in first.text

        problems = compare_transcript_to_golden(text_run, golden, page=_PAGE)
        assert problems == ()

    def test_text_drift_reports_a_unified_diff(self, text_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            frames[0]["text"] = str(frames[0]["text"]) + "a line the CLI no longer prints\n"

        golden, baseline = _drifted(text_run, _drift)
        problems = compare_transcript_to_golden(text_run, golden, page=_PAGE, baseline=baseline)
        assert len(problems) == 1
        assert "stdout text diverged" in problems[0]
        assert "--- golden" in problems[0] and "+++ live" in problems[0]
        assert "-a line the CLI no longer prints" in problems[0]

    def test_normalisation_replaces_sandbox_paths_and_masked_ids(self, text_run: SequenceTranscript) -> None:
        native_root = text_run.storage_root
        posix_root = native_root.replace("\\", "/")
        sample = f"stored under {native_root} (also {posix_root})\nworkdir {text_run.workdir}\nsnapshot abc-123-flap\n"
        normalised = normalise_text_output(
            sample,
            storage_root=text_run.storage_root,
            workdir=text_run.workdir,
            masked_values=("abc-123-flap",),
        )
        assert native_root not in normalised and posix_root not in normalised
        assert (
            f"stored under {SANDBOX_STORAGE_ROOT_PLACEHOLDER} (also {SANDBOX_STORAGE_ROOT_PLACEHOLDER})" in normalised
        )
        assert f"workdir {SANDBOX_WORKDIR_PLACEHOLDER}" in normalised
        assert f"snapshot {MASK_SENTINEL}" in normalised

    def test_token_rooted_suffix_uses_one_cross_platform_separator(self) -> None:
        """A Windows writer and POSIX checker persist the same token path."""

        normalised = normalise_text_output(
            "path\tC:\\Temp\\sequence\\store\\logs\\cadrumo.log\n",
            storage_root=r"C:\Temp\sequence\store",
            workdir=r"C:\Temp\sequence\workdir",
        )
        assert normalised == f"path\t{SANDBOX_STORAGE_ROOT_PLACEHOLDER}/logs/cadrumo.log\n"

    def test_unrelated_windows_path_keeps_its_native_separators(self) -> None:
        """Separator canonicalisation cannot rewrite an unknown operator path."""

        unrelated = r"open C:\Users\someone\Documents\report.pdf"
        assert (
            normalise_text_output(
                unrelated,
                storage_root=r"C:\Temp\sequence\store",
                workdir=r"C:\Temp\sequence\workdir",
            )
            == unrelated
        )

    def test_a_storage_root_without_a_parent_directory_contributes_no_sandbox_root_needle(self) -> None:
        """A root with no parent of its own must not tokenise every full stop or separator."""

        text = "open C:\\Users\\someone\\Documents\\report.pdf and /var/log/cadrumo.log\n"
        for storage_root in ("cadrumo-storage", "/cadrumo-storage", "C:\\cadrumo-storage"):
            assert normalise_text_output(text, storage_root=storage_root, workdir="workdir") == text


class TestEnvelopePathNormalisation:
    """Value-anchored sandbox/checkout-path tokenisation inside JSON envelopes.

    ``config check``'s ``preflight[...].detail`` strings carry the per-run
    storage root and the machine's absolute corpus paths; the field-level
    ``mask_document`` never looks inside a string value, so without this
    normalisation the golden diverges every run and on every other checkout.
    These are synthetic unit inputs (a directly-built transcript, like the
    bracket-quoted-key expectation test) exercising the REAL build and compare
    path, since no simple hermetic command is guaranteed to leak both roots.
    """

    _REPO_ROOT: str = str(_repo_root())

    def _run(self, *, storage_root: str, workdir: str, status: str = "success") -> SequenceTranscript:
        detail = (
            f"secure-storage root {storage_root} is reachable; "
            f"corpus at {self._REPO_ROOT}/src/cadrumo/_data/corpus/x.html"
        )
        envelope: dict[str, JsonValue] = {
            "schema_version": "2",
            "status": status,
            "result": {"preflight": [{"detail": detail}, {"detail": f"workdir {workdir}"}]},
        }
        execution = FrameExecution(
            kind=FrameKind.RESULT,
            command_line="aeat --format json config check",
            argv=("aeat", "--format", "json", "config", "check"),
            exit_code=0,
            output=json.dumps(envelope),
            envelope=envelope,
            envelope_source="stdout",
        )
        return SequenceTranscript(
            sequence_id="path-norm-case",
            profile_id="docs-sequence-sandbox",
            frozen_instant=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            storage_root=storage_root,
            workdir=workdir,
            frames=(execution,),
        )

    @staticmethod
    def _first_detail(record: SequenceRecord) -> str:
        envelope = record.frames[0].envelope
        assert envelope is not None
        result = cast("dict[str, JsonValue]", envelope["result"])
        preflight = cast("list[JsonValue]", result["preflight"])
        first_preflight = cast("dict[str, JsonValue]", preflight[0])
        return cast("str", first_preflight["detail"])

    def test_build_bakes_stable_tokens_for_sandbox_and_checkout_paths(self) -> None:
        storage = r"C:\Temp\cli-sequence-AAA\cadrumo-storage"
        workdir = r"C:\Temp\cli-sequence-AAA\workdir"
        record = build_record(self._run(storage_root=storage, workdir=workdir))
        detail = self._first_detail(record)
        assert storage not in detail
        assert self._REPO_ROOT not in detail and self._REPO_ROOT.replace("\\", "/") not in detail
        assert SANDBOX_STORAGE_ROOT_PLACEHOLDER in detail and REPO_ROOT_PLACEHOLDER in detail

    def test_two_runs_with_different_sandbox_paths_compare_clean(self) -> None:
        golden = _golden(
            self._run(
                storage_root=r"C:\Temp\cli-sequence-AAA\cadrumo-storage",
                workdir=r"C:\Temp\cli-sequence-AAA\workdir",
            ),
        )
        live = self._run(
            storage_root=r"C:\Temp\cli-sequence-BBB\cadrumo-storage",
            workdir=r"C:\Temp\cli-sequence-BBB\workdir",
        )
        assert compare_transcript_to_golden(live, golden, page=_PAGE) == ()

    def test_windows_writer_and_posix_reader_compare_token_suffixes_cleanly(self) -> None:
        """Known-root suffix separators are canonical across operating systems."""

        golden = _golden(
            self._run(
                storage_root=r"C:\Temp\cli-sequence-AAA\cadrumo-storage",
                workdir=r"C:\Temp\cli-sequence-AAA\workdir",
            ),
        )
        live = self._run(
            storage_root="/home/runner/cli-sequence-BBB/cadrumo-storage",
            workdir="/home/runner/cli-sequence-BBB/workdir",
        )
        assert compare_transcript_to_golden(live, golden, page=_PAGE) == ()

    def test_real_divergence_survives_path_normalisation(self) -> None:
        """Anti-tautology proof: the only legitimate difference between the two
        runs is the tokenised sandbox path, yet a real ``status`` flap is still
        caught — path normalisation cannot void the compare (over-mask)."""
        golden = _golden(
            self._run(
                storage_root=r"C:\Temp\cli-sequence-AAA\cadrumo-storage",
                workdir=r"C:\Temp\cli-sequence-AAA\workdir",
                status="success",
            ),
        )
        live = self._run(
            storage_root=r"C:\Temp\cli-sequence-BBB\cadrumo-storage",
            workdir=r"C:\Temp\cli-sequence-BBB\workdir",
            status="warning",
        )
        baseline = build_record(
            self._run(
                storage_root=r"C:\Temp\cli-sequence-AAA\cadrumo-storage",
                workdir=r"C:\Temp\cli-sequence-AAA\workdir",
                status="success",
            ),
        )
        problems = compare_transcript_to_golden(live, golden, page=_PAGE, baseline=baseline)
        assert len(problems) == 1
        assert "status" in problems[0]

    def test_unrelated_absolute_path_is_not_over_masked(self) -> None:
        """Value-anchored: only the known roots are replaced. An unrelated
        absolute path the CLI might echo survives verbatim, so the normalisation
        cannot mask a path it was never told about."""
        unrelated = r"see C:\Users\someone\Documents\report.pdf"
        document: dict[str, JsonValue] = {"result": {"detail": unrelated}}
        normalised = normalise_document_paths(
            document,
            storage_root=r"C:\Temp\cli-sequence-AAA\cadrumo-storage",
            workdir=r"C:\Temp\cli-sequence-AAA\workdir",
        )
        result = cast("dict[str, JsonValue]", normalised["result"])
        assert result["detail"] == unrelated


@pytest.fixture(scope="module")
def error_run(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real run whose first frame refuses via the stderr error document."""
    missing_id = "deadbeef" * 8
    sequence = parse_sequence(
        sequence_id="compare-stderr-case",
        options={"verify": "Verify the profile listing succeeds."},
        body=(
            f"aeat --format json app modelo work calculate {missing_id}\n"
            "@expect exit_code == 2\n"
            "@result aeat --format json config profile list\n"
            '@expect status == "success"\n'
        ),
    )
    return execute_sequence(sequence, sandbox_root=tmp_path_factory.mktemp("stderr-run"))


class TestStderrErrorDocumentGoldens:
    def test_error_document_golden_roundtrips_and_self_compares_clean(
        self,
        error_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        _write(error_run, tmp_path)
        golden = read_golden(_PAGE, error_run.sequence_id, goldens_root=tmp_path)
        assert golden.frames[0].envelope_source == "stderr"
        assert golden.frames[0].exit_code == 2

        refusal = build_record(error_run).frames[0]
        assert refusal.envelope is not None
        assert refusal.stderr_text is None  # stderr IS the envelope, never duplicated

        assert compare_transcript_to_golden(error_run, golden, page=_PAGE) == ()

    def test_envelope_moving_streams_is_a_named_failure(self, error_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            frames[0]["envelope_source"] = "stdout"
            frames[0]["stderr_text"] = None

        golden, _ = _drifted(error_run, _drift)
        problems = compare_transcript_to_golden(error_run, golden, page=_PAGE)
        assert any("envelope stream changed from stdout to stderr" in problem for problem in problems)

    def test_stderr_text_drift_is_a_named_failure(self, json_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            frames = cast("list[dict[str, object]]", document["frames"])
            frames[0]["stderr_text"] = "a warning the CLI no longer prints\n"

        golden, baseline = _drifted(json_run, _drift)
        problems = compare_transcript_to_golden(json_run, golden, page=_PAGE, baseline=baseline)
        assert len(problems) == 1
        assert "stderr text diverged" in problems[0]


class TestExpectEvaluation:
    def test_expectations_pass_against_the_live_run(self, json_run: SequenceTranscript) -> None:
        assert evaluate_expectations(_json_sequence(), json_run, page=_PAGE) == ()

    def test_expectation_can_compare_with_an_earlier_capture(self, json_run: SequenceTranscript) -> None:
        sequence = parse_sequence(
            sequence_id="compare-json-case",
            options={"verify": "Verify both profile listings report the same status."},
            body=_JSON_BODY.replace('@expect status == "success"', '@expect status == "{run_status}"'),
        )

        assert evaluate_expectations(sequence, json_run, page=_PAGE) == ()

    def test_failed_semantic_expectation_is_named(self, json_run: SequenceTranscript) -> None:
        """A sequence cannot 'verify' by reproducing the wrong meaning: the
        expectation evaluates against the LIVE output and fails loudly."""
        failing = parse_sequence(
            sequence_id="compare-json-case",
            options={"verify": "Verify the profile listing succeeds."},
            body=_JSON_BODY.replace('@expect status == "success"', '@expect status == "warning"'),
        )
        problems = evaluate_expectations(failing, json_run, page=_PAGE)
        assert len(problems) == 1
        assert '@expect status == "warning" failed' in problems[0]
        assert '"success"' in problems[0]  # the live value is named

    def test_missing_expectation_path_is_named(self, json_run: SequenceTranscript) -> None:
        variant = parse_sequence(
            sequence_id="compare-json-case",
            options={"verify": "Verify the profile listing succeeds."},
            body=_JSON_BODY.replace(
                '@expect status == "success"',
                '@expect result.no_such_field == "x"',
            ),
        )
        problems = evaluate_expectations(variant, json_run, page=_PAGE)
        assert len(problems) == 1
        assert "result.no_such_field" in problems[0]

    def test_bracket_quoted_path_expectation_evaluates_against_the_envelope(self) -> None:
        """An @expect with a bracket-quoted object key evaluates end to end.

        No simple real command emits a casilla dict keyed with a literal dot, so
        this constructs the transcript directly (a unit input to the pure
        ``evaluate_expectations``, not a committed golden) to exercise the
        bracket-quoted path against a genuine envelope shape — M349's declarante
        casillas keyed ``decl.importe-operaciones`` / ``decl.numero-operadores``.
        """
        envelope: dict[str, JsonValue] = {
            "schema_version": "2",
            "status": "success",
            "result": {
                "casilla_values": {
                    "decl.importe-operaciones": "12345.00",
                    "decl.numero-operadores": "3",
                },
            },
        }
        execution = FrameExecution(
            kind=FrameKind.RESULT,
            command_line="aeat --format json app modelo verify wu",
            argv=("aeat", "--format", "json", "app", "modelo", "verify", "wu"),
            exit_code=0,
            output=json.dumps(envelope),
            envelope=envelope,
            envelope_source="stdout",
        )
        transcript = SequenceTranscript(
            sequence_id="compare-quoted-key",
            profile_id="docs-sequence-sandbox",
            frozen_instant=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            storage_root="/sandbox",
            workdir="/sandbox/workdir",
            frames=(execution,),
        )

        passing = parse_sequence(
            sequence_id="compare-quoted-key",
            options={"verify": "Confirm the declarante figures."},
            body=(
                "@result aeat --format json app modelo verify wu\n"
                '@expect result.casilla_values["decl.importe-operaciones"] == "12345.00"\n'
                '@expect result.casilla_values["decl.numero-operadores"] == "3"\n'
            ),
        )
        assert evaluate_expectations(passing, transcript, page=_PAGE) == ()

        failing = parse_sequence(
            sequence_id="compare-quoted-key",
            options={"verify": "Confirm the declarante figures."},
            body=(
                "@result aeat --format json app modelo verify wu\n"
                '@expect result.casilla_values["decl.numero-operadores"] == "9"\n'
            ),
        )
        problems = evaluate_expectations(failing, transcript, page=_PAGE)
        assert len(problems) == 1
        assert "decl.numero-operadores" in problems[0]
        assert '"3"' in problems[0]  # the live value is named


class TestMaskAuthorityIsCentral:
    """The executor never declares its own mask set; mask authority stays central.

    Three enforcement tiers, none sufficient alone: the public surface exposes
    no mask-shaped parameter (this class), the compare module's own source
    never overrides ``mask_document``'s central default (the AST gate below —
    the substrate primitive DOES take a ``fields=`` kwarg, so an internal
    override would otherwise widen the mask without touching any signature),
    and the executor-level double-run proof in
    ``dev/docs/tests/test_sequence_goldens.py`` pins the residual behaviour.
    """

    def test_comparison_surface_exposes_no_mask_parameter(self) -> None:
        for function in (
            compare_transcript_to_golden,
            evaluate_expectations,
            check_transcript,
            assert_transcript_matches_golden,
        ):
            parameters = {name.lower() for name in inspect.signature(function).parameters}
            offending = {name for name in parameters if "mask" in name or "field" in name}
            assert not offending, f"{function.__name__} exposes mask-shaped parameter(s): {sorted(offending)}"

    @pytest.mark.parametrize("module", [compare, record_store], ids=["compare", "record_store"])
    def test_comparison_modules_never_override_the_central_mask_default(self, module: ModuleType) -> None:
        """AST gate: every ``mask_document`` call inside the compare module and
        the record store (whose compared form the digest covers) is
        argument-free beyond the document — no ``fields=`` keyword, no extra
        positional — so the central ``GOLDEN_MASK_FIELDS`` default is the only
        mask that can ever apply."""
        module_ast = ast.parse(inspect.getsource(module))
        calls = [
            node
            for node in ast.walk(module_ast)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "mask_document")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "mask_document")
            )
        ]
        assert calls, "JSON comparison must route through mask_document"
        for call in calls:
            assert len(call.args) == 1 and not call.keywords, (
                f"mask_document call at line {call.lineno} overrides the central mask default"
            )


class TestStepDescriptionGoldenImmunity:
    def test_adding_step_lines_never_invalidates_a_committed_golden(
        self,
        json_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """@step is narration metadata, never executed truth: a golden written
        from the description-free body compares clean against a REAL fresh run
        of the same body with @step lines added — authoring or editing
        narration can never force a golden refresh."""
        _write(json_run, tmp_path)
        golden = read_golden(_PAGE, json_run.sequence_id, goldens_root=tmp_path)

        annotated = parse_sequence(
            sequence_id="compare-json-case",
            options={"verify": "Verify the profile listing succeeds."},
            body=(
                "@step List the registered profiles.\n"
                + _JSON_BODY.replace(
                    "@result aeat",
                    "@step Verify the listing reads success.\n@result aeat",
                )
            ),
        )
        assert all(frame.step_description is not None for frame in annotated.frames)

        rerun = execute_sequence(annotated, sandbox_root=tmp_path / "annotated-run")
        assert check_transcript(annotated, rerun, golden, page=_PAGE) == ()
