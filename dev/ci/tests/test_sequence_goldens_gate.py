"""The merge gate's committed-goldens step: selection, delegation to the per-sequence cache, and refusal.

Verdict reuse happens sequence by sequence inside the engine check this gate
delegates to; its behaviour is proven with real sequences in
``dev/docs/sequences/tests/test_verdict_check_flow.py``. These tests cover what
the gate itself owns: which change sets select it, which check it runs and how
wide, and how a divergence or an engine refusal becomes a failed gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.sequences.errors import SequenceEngineError

from .. import sequence_goldens_gate
from ..sequence_goldens_gate import DEFAULT_JOBS, check_committed_goldens, main, run_sequence_goldens_gate

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SELECTING = ("src/cadrumo/entrypoints/cli/app.py",)


class _Recorder:
    """A check stand-in returning a fixed report and counting its invocations."""

    def __init__(self, problems: tuple[str, ...] = ()) -> None:
        self.problems = problems
        self.jobs: list[int] = []

    def __call__(self, jobs: int) -> tuple[str, ...]:
        self.jobs.append(jobs)
        return self.problems


@pytest.mark.parametrize("changed", [(), (".github/workflows/merge-gate.yml", "README.md", "dev/ci/change_scope.py")])
def test_unselected_change_set_does_not_execute(changed: tuple[str, ...], capsys: pytest.CaptureFixture[str]) -> None:
    check = _Recorder()

    assert run_sequence_goldens_gate(changed, check=check) == 0

    assert check.jobs == []
    assert "not selected" in capsys.readouterr().out


@pytest.mark.parametrize("changed", [_SELECTING, ("dev/registry/bindings.py",), ("src/cadrumo_runtime/host/app.py",)])
def test_a_selected_change_set_runs_the_check_at_the_requested_width(
    changed: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    check = _Recorder()

    assert run_sequence_goldens_gate(changed, jobs=3, check=check) == 0

    assert check.jobs == [3]
    assert "cli-sequence goldens: clean" in capsys.readouterr().out


def test_missing_change_metadata_runs_the_goldens_gate_at_the_default_width() -> None:
    check = _Recorder()
    assert run_sequence_goldens_gate(None, check=check) == 0
    assert check.jobs == [DEFAULT_JOBS]


def test_both_surfaces_delegate_to_the_one_sharded_engine_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pytest surface and the CLI surface run the engine's own check with no tree override.

    Verdict reuse is keyed on contents, not on which surface ran, so a full docs
    build and this gate share the records only if both reach the engine over the
    committed docs tree and goldens; the engine child is replaced here to read
    the arguments the gate passes it.
    """
    calls: list[dict[str, object]] = []

    def engine(**kwargs: object) -> tuple[str, ...]:
        calls.append(kwargs)
        return ()

    monkeypatch.setattr(sequence_goldens_gate, "check_sequences_in_subprocess", engine)

    assert check_committed_goldens(jobs=3) == ()
    assert run_sequence_goldens_gate(None, jobs=3) == 0

    assert calls == [{"jobs": 3}, {"jobs": 3}]


def test_a_divergence_fails_with_the_report_and_the_refresh_remedy(capsys: pytest.CaptureFixture[str]) -> None:
    check = _Recorder(problems=("page 'how-to/quickstart': frame 0 exit_code 0 != 99",))

    assert run_sequence_goldens_gate(_SELECTING, check=check) == 1

    captured = capsys.readouterr()
    assert "frame 0 exit_code" in captured.err
    assert "python -m dev.docs.sequences refresh" in captured.err
    assert "clean" not in captured.out


@pytest.mark.parametrize(
    "message",
    ["the registry authority is stale", "cli-sequence inputs changed during execution (uv.lock)"],
)
def test_an_engine_refusal_fails_the_gate(message: str, capsys: pytest.CaptureFixture[str]) -> None:
    def refuse(_jobs: int) -> tuple[str, ...]:
        raise SequenceEngineError(message)

    assert run_sequence_goldens_gate(_SELECTING, check=refuse) == 1

    captured = capsys.readouterr()
    assert f"FAIL: {message}" in captured.err
    assert "clean" not in captured.out


def test_cli_reads_an_explicit_change_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = tmp_path / "changed.txt"
    manifest.write_text("README.md\n", encoding="utf-8")
    assert main(["--changed-files", str(manifest), "--jobs", "4"]) == 0
    assert "not selected" in capsys.readouterr().out


def test_cli_refuses_a_non_positive_width() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--jobs", "0"])
    assert exit_info.value.code == 2
