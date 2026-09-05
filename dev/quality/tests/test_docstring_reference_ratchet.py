"""Gate: the docstring-reference ratchet refuses in all four directions.

A ratchet that has only ever seen a matching tree has not been shown able to
refuse a drifting one, so every direction is constructed here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..docstring_reference_ratchet import count_dangling, evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree(tmp_path: Path, **modules: str) -> Path:
    """Write a miniature package and return the root to scan."""
    root = tmp_path / "cadrumo"
    root.mkdir()
    for name, source in modules.items():
        (root / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def _baseline(tmp_path: Path, **counts: int) -> Path:
    """Write a baseline file and return its path."""
    path = tmp_path / "baseline.toml"
    body = "\n".join(f'"{name}.py" = {count}' for name, count in counts.items())
    path.write_text(f"[files]\n{body}\n", encoding="utf-8")
    return path


def test_a_reference_in_an_attribute_docstring_is_counted(tmp_path: Path) -> None:
    """The blind spot that nearly shipped this gate broken.

    ``ast.get_docstring`` reaches a module, class and function docstring and
    nothing else, so the bare string beneath an assignment -- the form this
    codebase documents its constants with -- was invisible. A reference planted
    in one did not fail the gate, which is why the end-to-end plant matters and
    why this direction is pinned here.
    """
    root = _tree(
        tmp_path,
        mod='WIDTH = 3\n"""Sized by :func:`a_function_that_is_not_defined`."""\n',
    )
    assert count_dangling(root) == {"mod.py": 1}


def test_a_module_that_newly_names_something_absent_is_refused(tmp_path: Path) -> None:
    """The direction the gate exists for."""
    root = _tree(tmp_path, fresh='"""Points at :func:`nothing_defines_this`."""\n')
    verdict = evaluate(root, _baseline(tmp_path))
    assert not verdict.ok
    assert verdict.added == {"fresh.py": 1}


def test_a_recorded_module_that_gains_one_is_refused(tmp_path: Path) -> None:
    """Growth inside an already-indebted module must not pass unnoticed."""
    root = _tree(
        tmp_path,
        known='"""Names :func:`absent_one` and :class:`absent_two`."""\n',
    )
    verdict = evaluate(root, _baseline(tmp_path, known=1))
    assert not verdict.ok
    assert verdict.grown == {"known.py": (2, 1)}


def test_paid_down_debt_must_be_written_down(tmp_path: Path) -> None:
    """A baseline holding headroom lets a reference come back unnoticed."""
    root = _tree(tmp_path, known='"""Names :func:`absent_one`."""\n')
    verdict = evaluate(root, _baseline(tmp_path, known=2))
    assert not verdict.ok
    assert verdict.shrunk == {"known.py": (1, 2)}


def test_a_spent_entry_must_be_removed(tmp_path: Path) -> None:
    """A module naming nothing absent has no business holding a baseline line."""
    root = _tree(tmp_path, clean='"""Everything here resolves."""\n')
    verdict = evaluate(root, _baseline(tmp_path, clean=1))
    assert not verdict.ok
    assert verdict.spent == ("clean.py",)


def test_a_tree_matching_its_baseline_passes(tmp_path: Path) -> None:
    """The normal case, so the gate is not merely always-red."""
    root = _tree(tmp_path, known='"""Names :func:`absent_one`."""\n')
    assert evaluate(root, _baseline(tmp_path, known=1)).ok
