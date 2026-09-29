"""Setup frames: executed and checked, but their output is never stored.

A setup frame is build scaffolding. The rendered page never shows it and later
frames consume only its captures, so its golden and its record keep the argv,
exit code and captures alone. These tests execute a REAL sequence whose first frame is a JSON
setup frame with a capture and prove the contract from both sides: the golden
carries no setup output and still compares clean against a fresh run, while a
setup frame's exit code, captures and ``@expect`` assertions keep biting.
Divergence is injected into an isolated copy of the golden or transcript, never
into a committed artifact.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from cadrumo.tests.golden_comparison import MASK_SENTINEL

from ..compare import check_transcript, compare_transcript_to_golden, evaluate_expectations
from ..errors import SequenceGoldenError
from ..golden_store import SequenceGolden, golden_path, read_golden, write_golden
from ..parser import parse_sequence
from ..record_store import build_record, golden_from_record
from ..runner import FrameExecution, SequenceTranscript, execute_sequence
from ..schema import FrameKind, ParsedSequence

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/setup-frame-case"
_SEQUENCE_ID = "setup-frame-case"

#: A JSON setup frame that binds a capture, then a reader-facing result frame.
_BODY = "\n".join(
    [
        "@setup aeat --format json config profile list",
        "@capture setup_status status",
        "@result aeat --format json config profile list",
        '@expect status == "success"',
        "@expect exit_code == 0",
    ],
)

_REFRESH_HINT = f"python -m dev.docs.sequences refresh --sequence {_SEQUENCE_ID}"


def _sequence(body: str = _BODY) -> ParsedSequence:
    return parse_sequence(
        sequence_id=_SEQUENCE_ID,
        options={"verify": "Verify the profile listing succeeds."},
        body=body,
    )


def _golden(transcript: SequenceTranscript) -> SequenceGolden:
    return golden_from_record(build_record(transcript))


def _write(transcript: SequenceTranscript, root: Path) -> Path:
    return write_golden(_golden(transcript), page=_PAGE, goldens_root=root)


def _mutated(golden: SequenceGolden, mutate: Callable[[dict[str, object]], None]) -> SequenceGolden:
    """Return a strictly re-validated copy of ``golden`` after ``mutate(document)``."""
    document = golden.model_dump(mode="json")
    mutate(document)
    return SequenceGolden.model_validate_json(json.dumps(document))


def _setup_frame(document: dict[str, object]) -> dict[str, object]:
    return cast("list[dict[str, object]]", document["frames"])[0]


@pytest.fixture(scope="module")
def setup_run(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real execution of the setup sequence, shared across this module."""
    return execute_sequence(_sequence(), sandbox_root=tmp_path_factory.mktemp("setup-run-a"))


class TestSetupGoldenStorage:
    def test_the_live_setup_frame_really_produced_output(self, setup_run: SequenceTranscript) -> None:
        """Anti-vacuity: the storage tests below mean something only if the
        setup frame emitted an envelope that the golden then declined to keep."""
        setup = setup_run.frames[0]
        assert setup.kind is FrameKind.SETUP
        assert setup.envelope is not None
        assert setup.output
        assert [capture.name for capture in setup.captured] == ["setup_status"]

    def test_setup_frame_golden_stores_only_argv_exit_code_and_captures(
        self,
        setup_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        target = _write(setup_run, tmp_path)
        stored = json.loads(target.read_text(encoding="utf-8"))
        assert stored["golden_schema_version"] == 3

        setup, result = stored["frames"]
        assert setup["kind"] == "setup"
        assert setup["argv"] == ["aeat", "--format", "json", "config", "profile", "list"]
        assert setup["exit_code"] == 0
        assert [capture["name"] for capture in setup["captures"]] == ["setup_status"]
        for field in ("envelope_source", "output_sha256", "output_bytes"):
            assert setup[field] is None, field

        # The reader-facing frame keeps its output fingerprint.
        assert result["kind"] == "result"
        assert result["envelope_source"] == "stdout" and result["output_sha256"] and result["output_bytes"]

    def test_setup_frame_record_stores_no_output(self, setup_run: SequenceTranscript) -> None:
        setup, result = build_record(setup_run).frames
        assert (setup.envelope, setup.envelope_source, setup.text, setup.stderr_text) == (None, None, None, None)
        assert result.envelope is not None

    def test_output_free_setup_golden_roundtrips_and_a_fresh_run_checks_clean(
        self,
        setup_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        _write(setup_run, tmp_path)
        golden = read_golden(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)
        assert golden == _golden(setup_run)

        rerun = execute_sequence(_sequence(), sandbox_root=tmp_path / "setup-run-b")
        assert check_transcript(_sequence(), rerun, golden, page=_PAGE) == ()


class TestOutdatedGoldensAreRefused:
    def test_a_golden_fingerprinting_setup_output_is_refused_with_the_refresh_hint(
        self,
        setup_run: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """A setup frame is not reader-facing, so a digest on it is refused."""
        target = _write(setup_run, tmp_path)
        document = json.loads(target.read_text(encoding="utf-8"))
        setup = document["frames"][0]
        setup["output_sha256"] = document["frames"][1]["output_sha256"]
        setup["output_bytes"] = 10
        setup["envelope_source"] = "stdout"
        target.write_text(json.dumps(document), encoding="utf-8")

        with pytest.raises(SequenceGoldenError) as excinfo:
            read_golden(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)
        message = str(excinfo.value)
        assert "a setup frame records only its argv, exit code and captures" in message
        assert _REFRESH_HINT in message

    @pytest.mark.parametrize("version", [1, 2])
    def test_an_earlier_version_golden_is_refused_with_the_refresh_hint(
        self,
        setup_run: SequenceTranscript,
        tmp_path: Path,
        version: int,
    ) -> None:
        """An earlier layout is refused, never read, even when its frames happen to fit."""
        target = _write(setup_run, tmp_path)
        document = json.loads(target.read_text(encoding="utf-8"))
        document["golden_schema_version"] = version
        target.write_text(json.dumps(document), encoding="utf-8")

        with pytest.raises(SequenceGoldenError) as excinfo:
            read_golden(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)
        message = str(excinfo.value)
        assert "golden_schema_version" in message
        assert _REFRESH_HINT in message
        assert target == golden_path(_PAGE, _SEQUENCE_ID, goldens_root=tmp_path)


class TestSetupFramesStillBite:
    def test_setup_exit_code_divergence_fails_the_check(self, setup_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            _setup_frame(document)["exit_code"] = 3

        problems = compare_transcript_to_golden(setup_run, _mutated(_golden(setup_run), _drift), page=_PAGE)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert "exit code 0, golden expects 3" in problems[0]

    def test_setup_capture_divergence_fails_the_check(self, setup_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            captures = cast("list[dict[str, object]]", _setup_frame(document)["captures"])
            captures[0]["value"] = "warning"

        problems = compare_transcript_to_golden(setup_run, _mutated(_golden(setup_run), _drift), page=_PAGE)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert "captured values diverged" in problems[0]

    def test_setup_argv_divergence_fails_the_check(self, setup_run: SequenceTranscript) -> None:
        def _drift(document: dict[str, object]) -> None:
            _setup_frame(document)["argv"] = ["aeat", "config", "profile", "list"]

        problems = compare_transcript_to_golden(setup_run, _mutated(_golden(setup_run), _drift), page=_PAGE)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert "argv diverged" in problems[0]

    def test_a_failing_setup_expectation_fails_the_check(self, setup_run: SequenceTranscript) -> None:
        """``@expect`` on a setup frame evaluates against the live run, so the
        missing stored output cannot hide a setup frame that means failure."""
        asserted = _sequence(_BODY.replace("@capture setup_status status", '@expect status == "warning"'))
        assert asserted.frames[0].expects

        problems = evaluate_expectations(asserted, setup_run, page=_PAGE)
        assert len(problems) == 1
        assert "frame 0" in problems[0]
        assert '@expect status == "warning" failed' in problems[0]

    def test_setup_output_changes_alone_do_not_fail_the_check(self, setup_run: SequenceTranscript) -> None:
        """The flip side: the setup frame's output is outside the contract, so a
        live change confined to it compares clean while the frame's captures
        and exit code hold."""
        document = setup_run.model_dump(mode="json")
        setup = document["frames"][0]
        setup["envelope"]["result"] = {"a_field_setup_output_no_longer_stores": True}
        setup["output"] = json.dumps(setup["envelope"])
        setup["stderr"] = "a warning nobody reads\n"
        changed = SequenceTranscript.model_validate_json(json.dumps(document))

        assert compare_transcript_to_golden(changed, _golden(setup_run), page=_PAGE) == ()


def test_ids_minted_by_a_setup_frame_stay_masked_in_later_text() -> None:
    """The setup frame's envelope is still walked for masked ids, although it is
    not stored: an id a setup frame minted must not leak into a later text frame
    as a run-specific literal. A directly built transcript, because no hermetic
    command both mints a masked id and echoes it in text."""
    run_id = "run-4f1c9a-writer-only"
    setup_envelope: dict[str, JsonValue] = {"status": "success", "result": {"run_id": run_id}}
    frames = (
        FrameExecution(
            kind=FrameKind.SETUP,
            command_line="aeat --format json app diagnostics runs",
            argv=("aeat", "--format", "json", "app", "diagnostics", "runs"),
            exit_code=0,
            output=json.dumps(setup_envelope),
            envelope=setup_envelope,
            envelope_source="stdout",
        ),
        FrameExecution(
            kind=FrameKind.RESULT,
            command_line="aeat app diagnostics runs",
            argv=("aeat", "app", "diagnostics", "runs"),
            exit_code=0,
            output=f"latest run {run_id}\n",
        ),
    )
    transcript = SequenceTranscript(
        sequence_id="setup-mask-case",
        profile_id="docs-sequence-sandbox",
        frozen_instant=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        storage_root="/sandbox/cadrumo-storage",
        workdir="/sandbox/workdir",
        frames=frames,
    )

    record = build_record(transcript)
    assert record.frames[0].envelope is None
    assert record.frames[1].text == f"latest run {MASK_SENTINEL}\n"
