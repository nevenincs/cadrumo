"""Gate: the unconsumed-export ratchet refuses in all four directions.

Constructed rather than pinned: a ratchet that has only seen a matching tree
has not been shown able to refuse a drifting one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unconsumed_export_ratchet import count_unconsumed, evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ALL = '__all__ = ["widget"]\n\n\ndef widget() -> None:\n    """Do a thing."""\n'


def _tree(tmp_path: Path, **modules: str) -> Path:
    """Write a miniature package and return the root to scan."""
    root = tmp_path / "cadrumo"
    root.mkdir()
    for name, source in modules.items():
        (root / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def _unused(root: Path, *names: str) -> set[tuple[str, str]]:
    """Stand in for the audit's finding set, keyed as the ratchet keys it."""
    return {(f"{root.name}/{module}.py", name) for module, name in (n.split(":") for n in names)}


def _baseline(tmp_path: Path, **counts: int) -> Path:
    """Write a baseline file and return its path."""
    path = tmp_path / "baseline.toml"
    body = "\n".join(f'"{name}.py" = {count}' for name, count in counts.items())
    path.write_text(f"[files]\n{body}\n", encoding="utf-8")
    return path


def test_a_published_name_nothing_imports_is_counted(tmp_path: Path) -> None:
    """The finding: a promise in ``__all__`` that no module collects."""
    root = _tree(tmp_path, lonely=_ALL)
    assert count_unconsumed(root, _unused(root, "lonely:widget")) == {"lonely.py": 1}


def test_a_name_another_module_imports_is_not_counted(tmp_path: Path) -> None:
    """Consumption is the whole question; a collected promise is not debt."""
    root = _tree(tmp_path, lonely=_ALL, user="from .lonely import widget\n")
    assert count_unconsumed(root, _unused(root, "lonely:widget")) == {}


def test_a_name_the_audit_does_not_report_is_not_counted(tmp_path: Path) -> None:
    """Both halves matter: unimported alone would flag ordinary public API.

    Counting every exported name no module imports yielded 2247 in this tree,
    most of it API whose consumer is a test or an external caller. Intersecting
    with the audit is what makes the population the one under review.
    """
    root = _tree(tmp_path, lonely=_ALL)
    assert count_unconsumed(root, set()) == {}


def test_a_test_module_neither_publishes_nor_consumes(tmp_path: Path) -> None:
    """Matches the inventory's method so the two records cannot disagree."""
    root = _tree(tmp_path, lonely=_ALL)
    (root / "tests").mkdir()
    (root / "tests" / "test_user.py").write_text("from ..lonely import widget\n", encoding="utf-8")
    assert count_unconsumed(root, _unused(root, "lonely:widget")) == {"lonely.py": 1}


def test_a_module_that_newly_publishes_one_is_refused(tmp_path: Path) -> None:
    """The direction the gate exists for."""
    root = _tree(tmp_path, fresh=_ALL)
    verdict = evaluate(root, _baseline(tmp_path))
    assert not verdict.ok


def test_paid_down_debt_must_be_written_down(tmp_path: Path) -> None:
    """A baseline holding headroom lets an export come back unnoticed."""
    root = _tree(tmp_path, known=_ALL, user="from .known import widget\n")
    verdict = evaluate(root, _baseline(tmp_path, known=1))
    assert not verdict.ok
    assert verdict.spent == ("known.py",)
