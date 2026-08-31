"""Proofs for the guard that refuses an artefact generated over a moving tree.

The defect this guards is not hypothetical: a regeneration run on 2026-08-31
captured seventeen references to a module a peer deleted mid-run, and the
artefact's own `--check` then failed on the missing file rather than on the
race. The guard has to fire on exactly that shape.

See Also:
    :mod:`dev.quality.stable_tree_generation`
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.stable_tree_generation import (
    TreeMovedDuringGenerationError,
    refuse_if_tree_moves,
    tree_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree(root: Path, *names: str) -> Path:
    """Build a throwaway source tree the guard will treat as real."""
    package = root / "src"
    package.mkdir(parents=True, exist_ok=True)
    for name in names:
        (package / name).write_text("value = 1\n", encoding="utf-8")
    return root


def test_a_still_tree_passes(tmp_path: Path) -> None:
    """The guard must not fire on the normal case, or it blocks every run."""
    root = _tree(tmp_path, "alpha.py", "beta.py")

    with refuse_if_tree_moves(root):
        pass


def test_a_deleted_module_is_refused(tmp_path: Path) -> None:
    """The exact shape that contaminated the census: a module removed mid-run."""
    root = _tree(tmp_path, "alpha.py", "_envelope.py")

    with pytest.raises(TreeMovedDuringGenerationError, match="changed while this artefact"), refuse_if_tree_moves(root):
        (root / "src/_envelope.py").unlink()


def test_a_renamed_module_is_refused(tmp_path: Path) -> None:
    """A rename preserves every byte and still invalidates the artefact.

    Fingerprinting content rather than paths would miss this: the bytes all
    survive, at a path the artefact does not name.
    """
    root = _tree(tmp_path, "_envelope.py")

    with pytest.raises(TreeMovedDuringGenerationError), refuse_if_tree_moves(root):
        (root / "src/_envelope.py").rename(root / "src/contract.py")


def test_an_added_module_is_refused(tmp_path: Path) -> None:
    """A peer landing a new module mid-run also makes the walk unrepeatable."""
    root = _tree(tmp_path, "alpha.py")

    with pytest.raises(TreeMovedDuringGenerationError), refuse_if_tree_moves(root):
        (root / "src/gamma.py").write_text("value = 2\n", encoding="utf-8")


def test_the_fingerprint_distinguishes_two_different_trees(tmp_path: Path) -> None:
    """Anti-tautology: a fingerprint equal for every input would pass everything."""
    one = _tree(tmp_path / "one", "alpha.py")
    two = _tree(tmp_path / "two", "alpha.py", "beta.py")

    assert tree_fingerprint(one) != tree_fingerprint(two)


def test_the_fingerprint_is_stable_when_nothing_changes(tmp_path: Path) -> None:
    """The converse: an unstable fingerprint would refuse every honest run."""
    root = _tree(tmp_path, "alpha.py", "beta.py")

    assert tree_fingerprint(root) == tree_fingerprint(root)


def test_pycache_churn_does_not_refuse_a_run(tmp_path: Path) -> None:
    """Bytecode is written by the generator's own imports, not by a peer.

    Counting it would make the guard refuse the very runs it exists to protect,
    which is the failure mode that retires a gate rather than fixing one.
    """
    root = _tree(tmp_path, "alpha.py")
    cache = root / "src/__pycache__"
    cache.mkdir()

    with refuse_if_tree_moves(root):
        (cache / "alpha.cpython-313.pyc").write_text("bytecode", encoding="utf-8")
