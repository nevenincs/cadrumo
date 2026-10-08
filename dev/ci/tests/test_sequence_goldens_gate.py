"""The merge gate's committed-goldens step: selection, verdict reuse and refusal."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.cache_root import DEV_CACHE_ROOT_ENV
from dev.docs.sequences.errors import SequenceEngineError
from dev.docs.sequences.verdict_cache import FORCE_ENV

from ..sequence_goldens_gate import DEFAULT_JOBS, main, run_sequence_goldens_gate

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


def _unreachable_key() -> str:
    raise AssertionError("the input key must not be computed for an unselected change set")


@pytest.fixture
def verdict_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the real verdict cache at an empty isolated root."""
    root = tmp_path / "dev-cache"
    monkeypatch.setenv(DEV_CACHE_ROOT_ENV, str(root))
    monkeypatch.delenv(FORCE_ENV, raising=False)
    return root


@pytest.mark.parametrize("changed", [(), (".github/workflows/merge-gate.yml", "README.md", "dev/ci/change_scope.py")])
def test_unselected_change_set_neither_keys_nor_executes(
    verdict_root: Path, changed: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    check = _Recorder()

    assert run_sequence_goldens_gate(changed, input_key=_unreachable_key, check=check) == 0

    assert check.jobs == []
    assert "not selected" in capsys.readouterr().out
    assert not verdict_root.exists()


def test_a_miss_executes_then_the_same_inputs_reuse_the_clean_verdict(
    verdict_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    check = _Recorder()

    assert run_sequence_goldens_gate(_SELECTING, jobs=3, input_key=lambda: "a" * 64, check=check) == 0
    assert check.jobs == [3]
    assert any(verdict_root.rglob("*.json")), "a clean verdict must be recorded under the configured root"

    assert run_sequence_goldens_gate(_SELECTING, jobs=3, input_key=lambda: "a" * 64, check=check) == 0
    assert check.jobs == [3], "an unchanged input set must reuse the recorded verdict, not execute again"
    assert "reused clean verdict" in capsys.readouterr().out


def test_a_changed_input_set_executes_again(verdict_root: Path) -> None:
    check = _Recorder()

    run_sequence_goldens_gate(_SELECTING, input_key=lambda: "a" * 64, check=check)
    run_sequence_goldens_gate(_SELECTING, input_key=lambda: "b" * 64, check=check)

    assert check.jobs == [DEFAULT_JOBS, DEFAULT_JOBS]


def test_force_bypasses_a_recorded_verdict(verdict_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    check = _Recorder()
    run_sequence_goldens_gate(_SELECTING, input_key=lambda: "a" * 64, check=check)

    monkeypatch.setenv(FORCE_ENV, "1")
    run_sequence_goldens_gate(_SELECTING, input_key=lambda: "a" * 64, check=check)

    assert len(check.jobs) == 2


def test_a_divergence_fails_and_is_never_recorded(verdict_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    check = _Recorder(problems=("page 'how-to/quickstart': frame 0 exit_code 0 != 99",))

    assert run_sequence_goldens_gate(_SELECTING, input_key=lambda: "c" * 64, check=check) == 1
    err = capsys.readouterr().err
    assert "frame 0 exit_code" in err
    assert "python -m dev.docs.sequences refresh" in err
    assert not any(verdict_root.rglob("*.json"))

    assert run_sequence_goldens_gate(_SELECTING, input_key=lambda: "c" * 64, check=check) == 1
    assert len(check.jobs) == 2, "a failing verdict must be re-executed, never reused"


def test_an_engine_refusal_fails_without_recording(verdict_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def refuse(_jobs: int) -> tuple[str, ...]:
        raise SequenceEngineError("the registry authority is stale")

    assert run_sequence_goldens_gate(_SELECTING, input_key=lambda: "d" * 64, check=refuse) == 1

    assert "FAIL: the registry authority is stale" in capsys.readouterr().err
    assert not any(verdict_root.rglob("*.json"))


def test_cli_reads_an_explicit_change_manifest(verdict_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    verdict_root.mkdir()
    manifest = verdict_root / "changed.txt"
    manifest.write_text("README.md\n", encoding="utf-8")
    assert main(["--changed-files", str(manifest), "--jobs", "4"]) == 0
    assert "not selected" in capsys.readouterr().out


def test_cli_refuses_a_non_positive_width() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--jobs", "0"])
    assert exit_info.value.code == 2


def test_missing_change_metadata_runs_the_goldens_gate(verdict_root: Path) -> None:
    check = _Recorder()
    assert run_sequence_goldens_gate(None, input_key=lambda: "e" * 64, check=check) == 0
    assert check.jobs == [DEFAULT_JOBS]
