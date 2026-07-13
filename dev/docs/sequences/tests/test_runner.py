"""Real-behaviour tests for the per-sequence hermetic sandbox runner (W02.P03).

Every test drives the REAL Cadrumo CLI in-process against a fresh
real-crypto sandbox (genuine ``bucket-dek-v1`` bucket, encrypted SQLite,
frozen clock, injected deterministic profile id) — no mocks, no skips, no
seeded stand-ins. The worked chain is the Modelo 130 lifecycle: ``work
create`` → ``work calculate`` (with real registry bindings) → ``work verify``,
whose verify gate genuinely refuses without clean cross-period evidence, so the
terminal ``@result`` frame exercises a real declared non-zero exit.

Determinism observation (formalised by the W02.P05 anti-tautology gate): two
executions of the chain in fresh sandboxes produced ZERO pre-mask differing
JSON paths and byte-identical raw outputs — with the clock frozen and the
profile id injected, the work-unit and calculation-revision ids are
content-addressed and every timestamp is pinned, so the residual
non-deterministic surface of this chain is empty (trivially within the central
``GOLDEN_MASK_FIELDS``). The test pins that observation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.observability import GOLDEN_MASK_FIELDS, differing_field_names, differing_paths

from .. import (
    SANDBOX_PROFILE_ID,
    FrameKind,
    ParsedSequence,
    SequenceExecutionError,
    SequenceTranscript,
    execute_sequence,
    parse_sequence,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

#: A real create → calculate → verify chain over Modelo 130 2025 1T. The verify
#: gate refuses (cross-period evidence is absent in a fresh sandbox), so the
#: result frame declares the non-zero exit and asserts the refusal semantically.
_CHAIN_BODY = "\n".join(
    [
        "aeat --format json app modelo work create --modelo 130 --year 2025 --period 1T",
        "@capture work_unit_id result.work_unit_id",
        "aeat --format json app modelo work calculate {work_unit_id}"
        " --binding irpf.previous_year_economic_activity_net_income=13000"
        " --binding modelo-130-resultados-negativos-anteriores=0",
        "@capture calculation_revision_id result.calculation_revision_id",
        "@result aeat --format json app modelo work verify {calculation_revision_id}",
        "@expect result.granted_verificado_completo == false",
        "@expect exit_code == 1",
    ],
)


def _chain_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="runner-m130-chain",
        options={"verify": "Verify the calculation before exporting."},
        body=_CHAIN_BODY,
    )


def _result_sequence(body: str, *, sequence_id: str = "runner-refusal-case") -> ParsedSequence:
    """Parse a minimal structurally-valid sequence around ``body``'s frames."""
    return parse_sequence(
        sequence_id=sequence_id,
        options={"verify": "Verify the command completed."},
        body=body,
    )


@pytest.fixture(scope="module")
def chain_transcript(tmp_path_factory: pytest.TempPathFactory) -> SequenceTranscript:
    """One real chain execution shared by the inspection tests below."""
    root = tmp_path_factory.mktemp("chain-run-a")
    return execute_sequence(_chain_sequence(), sandbox_root=root)


class TestHermeticChainExecution:
    def test_chain_executes_all_frames_in_order(self, chain_transcript: SequenceTranscript) -> None:
        kinds = [frame.kind for frame in chain_transcript.frames]
        assert kinds == [FrameKind.COMMAND, FrameKind.COMMAND, FrameKind.RESULT]
        assert chain_transcript.profile_id == SANDBOX_PROFILE_ID
        assert chain_transcript.frames[0].exit_code == 0
        assert chain_transcript.frames[1].exit_code == 0

    def test_every_json_frame_records_its_envelope(self, chain_transcript: SequenceTranscript) -> None:
        for frame in chain_transcript.frames:
            assert frame.envelope is not None, frame.output
            # The recorded document is the real shared envelope spine.
            assert {"command", "status", "schema_version", "result", "notices"} <= set(frame.envelope)

    def test_captures_thread_real_ids_into_later_frames(self, chain_transcript: SequenceTranscript) -> None:
        create, calculate, verify = chain_transcript.frames

        work_unit_id = chain_transcript.captures["work_unit_id"]
        revision_id = chain_transcript.captures["calculation_revision_id"]

        # The captured values are the REAL ids the create/calculate envelopes carry.
        assert create.envelope is not None and calculate.envelope is not None
        create_result = create.envelope["result"]
        calculate_result = calculate.envelope["result"]
        assert isinstance(create_result, dict) and isinstance(calculate_result, dict)
        assert create_result["work_unit_id"] == work_unit_id
        assert calculate_result["calculation_revision_id"] == revision_id

        # ... and the later frames executed with those ids interpolated in argv.
        assert work_unit_id in calculate.argv
        assert revision_id in verify.argv
        # The authored line keeps its placeholder; only the executed argv resolves.
        assert "{work_unit_id}" in calculate.command_line
        assert "{calculation_revision_id}" in verify.command_line

    def test_declared_nonzero_exit_is_captured_not_fatal(self, chain_transcript: SequenceTranscript) -> None:
        verify = chain_transcript.result_frame
        assert verify.exit_code == 1  # declared via '@expect exit_code == 1'
        assert verify.envelope is not None
        result = verify.envelope["result"]
        assert isinstance(result, dict)
        assert result["granted_verificado_completo"] is False


class TestSandboxIsolationAndDeterminism:
    def test_second_run_is_isolated_and_byte_deterministic(
        self,
        chain_transcript: SequenceTranscript,
        tmp_path: Path,
    ) -> None:
        """A rerun in a fresh sandbox neither sees the first run's state nor drifts.

        Isolation and determinism are one assertion here: if any state leaked
        between the sandboxes, the second ``work create`` would resolve to the
        first run's existing unit as an idempotent no-op with an extra notice —
        a pre-mask envelope difference this comparison would surface.
        """
        rerun = execute_sequence(_chain_sequence(), sandbox_root=tmp_path / "chain-run-b")

        assert rerun.storage_root != chain_transcript.storage_root

        residual_paths: set[str] = set()
        residual_names: set[str] = set()
        for first, second in zip(chain_transcript.frames, rerun.frames, strict=True):
            assert first.envelope is not None and second.envelope is not None
            residual_paths |= differing_paths(first.envelope, second.envelope)
            residual_names |= differing_field_names(first.envelope, second.envelope)
            assert first.exit_code == second.exit_code
            # The raw outputs are byte-identical for this chain (observed and
            # pinned; the W02.P05 gate formalises the mask-honesty proof).
            assert first.output == second.output

        assert residual_paths == frozenset(), sorted(residual_paths)
        # Trivially within the central mask; pinned so a new residual field is
        # a loud, named regression rather than silent golden churn.
        assert residual_names <= GOLDEN_MASK_FIELDS

        assert rerun.captures == chain_transcript.captures


class TestLiveAeatRefusal:
    @pytest.mark.parametrize(
        "live_line",
        [
            "@setup aeat app live filed pull",
            "aeat app live iva-wallet pull-history",
            "aeat --format json app modelo reconcile pull some-work-unit",
        ],
    )
    def test_live_frames_are_refused_before_any_execution(self, live_line: str, tmp_path: Path) -> None:
        sequence = _result_sequence(
            f"{live_line}\n@result aeat config profile list\n@expect exit_code == 0\n",
            sequence_id="runner-live-refusal",
        )
        sandbox_root = tmp_path / "never-created"

        with pytest.raises(SequenceExecutionError, match="live-AEAT"):
            execute_sequence(sequence, sandbox_root=sandbox_root)

        # The refusal precedes the sandbox: nothing was provisioned or executed.
        assert not sandbox_root.exists()


class TestCaptureFailureDiagnostics:
    def test_capture_against_text_output_names_the_json_requirement(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat config profile list\n"
            "@capture profile_id result.profiles[0].profile_id\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-text-capture",
        )
        with pytest.raises(SequenceExecutionError, match="--format json"):
            execute_sequence(sequence, sandbox_root=tmp_path / "text-capture")

    def test_capture_path_missing_from_envelope_is_instructive(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat --format json config profile list\n"
            "@capture nope result.no_such_field\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-missing-path",
        )
        with pytest.raises(SequenceExecutionError, match=r"result\.no_such_field"):
            execute_sequence(sequence, sandbox_root=tmp_path / "missing-path")

    def test_undeclared_nonzero_exit_fails_fast_with_argv_and_output(self, tmp_path: Path) -> None:
        sequence = _result_sequence(
            "aeat --format json app modelo work create --modelo 130 --year 2025 --period 9T\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n",
            sequence_id="runner-undeclared-exit",
        )
        with pytest.raises(SequenceExecutionError, match="expected 0") as excinfo:
            execute_sequence(sequence, sandbox_root=tmp_path / "undeclared-exit")

        message = str(excinfo.value)
        assert "app modelo work create" in message  # the resolved argv
        assert "@expect exit_code ==" in message  # the instructive remedy
