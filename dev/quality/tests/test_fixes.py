"""Contract tests for the explicit-path mechanical repair owner."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dev.exit_codes import DRIFT, FIX_STRICT_ENV, OK, TOOL_BROKEN, TOOL_MISSING
from dev.quality import fixes

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_paths_must_be_explicit_python_files_inside_the_worktree(tmp_path: Path) -> None:
    """Omitted, broad, non-Python, missing, and external scope is refused."""
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "owned.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 2\n", encoding="utf-8")
    non_python = root / "notes.md"
    non_python.write_text("notes\n", encoding="utf-8")

    assert fixes.resolve_paths(["owned.py", "owned.py"], repo_root=root) == (source,)
    for refused in ([], ["."], ["notes.md"], ["missing.py"], [str(outside)]):
        with pytest.raises((OSError, ValueError)):
            fixes.resolve_paths(refused, repo_root=root)


def test_repair_runs_locked_tools_in_the_contractual_order_and_keeps_findings_advisory(tmp_path: Path) -> None:
    """Ruff lint, ty, and final formatting all run when diagnostics remain."""
    source = tmp_path / "owned.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    statuses = iter((1, 1, 0))

    def run(command: Sequence[str]) -> int:
        calls.append(tuple(command))
        return next(statuses)

    assert fixes.repair((source,), runner=run) == OK
    assert [command[:7] for command in calls] == [
        ("uv", "run", "--no-sync", "ruff", "check", "--fix", "--"),
        ("uv", "run", "--no-sync", "ty", "check", "--fix", "--"),
        ("uv", "run", "--no-sync", "ruff", "format", "--", str(source)),
    ]
    assert all(command[-1] == str(source) for command in calls)


@pytest.mark.parametrize(("status", "expected"), ((2, TOOL_BROKEN), (101, TOOL_BROKEN), (127, TOOL_MISSING)))
def test_operational_failure_is_nonzero_and_stops_mutation(
    tmp_path: Path,
    status: int,
    expected: int,
) -> None:
    """Usage, configuration, missing-tool, and internal failures never go green."""
    source = tmp_path / "owned.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def run(command: Sequence[str]) -> int:
        calls.append(tuple(command))
        return status

    assert fixes.repair((source,), runner=run) == expected
    assert len(calls) == 1


def test_formatter_failure_is_operational_not_an_advisory_finding(tmp_path: Path) -> None:
    """Formatting has no residual-diagnostic status to suppress."""
    source = tmp_path / "owned.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    statuses = iter((0, 0, 1))

    assert fixes.repair((source,), runner=lambda _command: next(statuses)) == TOOL_BROKEN


def test_strict_repair_reports_drift_only_in_the_explicit_path_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fleet strict contract fingerprints no file outside caller ownership."""
    source = tmp_path / "owned.py"
    neighbor = tmp_path / "neighbor.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    neighbor.write_text("VALUE = 2\n", encoding="utf-8")
    monkeypatch.setenv(FIX_STRICT_ENV, "1")
    calls = 0

    def run(_command: Sequence[str]) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            source.write_text("VALUE = 3\n", encoding="utf-8")
            neighbor.write_text("VALUE = 4\n", encoding="utf-8")
        return OK

    assert fixes.repair((source,), runner=run) == DRIFT
    assert calls == 3

    source.write_text("VALUE = 3\n", encoding="utf-8")
    neighbor.write_text("VALUE = 2\n", encoding="utf-8")
    calls = 0

    def mutate_only_unowned(_command: Sequence[str]) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            neighbor.write_text("VALUE = 5\n", encoding="utf-8")
        return OK

    assert fixes.repair((source,), runner=mutate_only_unowned) == OK
    assert calls == 3
