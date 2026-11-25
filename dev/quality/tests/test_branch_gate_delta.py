"""The branch delta gate fails on added findings and passes on removed or unchanged ones.

Each case builds a merge-base tree and a branch tree in a temporary directory and
runs the real year and complexity gates over them. Planted years are built from
the running year rather than spelled, because this module is itself read by the
year gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev.quality.branch_gate_delta import GateDelta, compute_delta, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_YEAR = datetime.now(UTC).year
_PATH = "dev/sample.py"
_CLEAN = "def f(value: int) -> int:\n    return value\n"
_YEAR_BOUND = f"FLOOR_YEAR = {_YEAR}\n"


def _branchy(count: int) -> str:
    """A callable whose cyclomatic complexity grows with ``count``."""
    body = "".join(f"    if value == {n}:\n        return {n}\n" for n in range(count))
    return f"def f(value: int) -> int:\n{body}    return value\n"


def _trees(tmp_path: Path, base: str | None, head: str | None) -> tuple[Path, Path]:
    roots = []
    for name, text in (("base", base), ("head", head)):
        file = tmp_path / name / _PATH
        file.parent.mkdir(parents=True)
        if text is not None:
            file.write_text(text, encoding="utf-8")
        roots.append(tmp_path / name)
    return roots[0], roots[1]


def _delta(tmp_path: Path, base: str | None, head: str | None) -> GateDelta:
    base_tree, head_tree = _trees(tmp_path, base, head)
    return compute_delta(base_tree, head_tree, [_PATH])


def _exit(tmp_path: Path, base: str | None, head: str | None) -> int:
    base_tree, head_tree = _trees(tmp_path, base, head)
    manifest = tmp_path / "paths.txt"
    manifest.write_text(f"{_PATH}\n", encoding="utf-8")
    return main(["--base-tree", str(base_tree), "--head-tree", str(head_tree), "--paths-from", str(manifest)])


def test_an_added_year_literal_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _exit(tmp_path, _CLEAN, _CLEAN + _YEAR_BOUND) == 1
    assert "year literal" in capsys.readouterr().out


def test_a_removed_year_literal_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _exit(tmp_path, _CLEAN + _YEAR_BOUND, _CLEAN) == 0
    assert "removed: 1" in capsys.readouterr().out


def test_a_year_literal_that_only_moves_is_not_added(tmp_path: Path) -> None:
    assert _delta(tmp_path, _CLEAN + _YEAR_BOUND, "\n\n" + _CLEAN + _YEAR_BOUND) == GateDelta((), ())


def test_a_new_complexity_hit_exits_one(tmp_path: Path) -> None:
    assert _exit(tmp_path, _CLEAN, _branchy(40)) == 1


def test_a_pre_existing_hit_with_a_new_score_is_neither_added_nor_removed(tmp_path: Path) -> None:
    assert _delta(tmp_path / "grown", _branchy(30), _branchy(40)) == GateDelta((), ())
    assert _exit(tmp_path / "grown-exit", _branchy(30), _branchy(40)) == 0


def test_a_removed_complexity_hit_exits_zero(tmp_path: Path) -> None:
    delta = _delta(tmp_path / "delta", _branchy(40), _CLEAN)
    assert delta.added == ()
    assert delta.removed
    assert _exit(tmp_path / "exit", _branchy(40), _CLEAN) == 0


def test_a_new_file_adds_all_its_findings(tmp_path: Path) -> None:
    assert _delta(tmp_path, None, _YEAR_BOUND).added


def test_a_deleted_file_adds_nothing(tmp_path: Path) -> None:
    assert _delta(tmp_path, _YEAR_BOUND, None).added == ()
