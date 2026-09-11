"""Gate: every scaffolding tree carrying Python is outside the linter's scope.

The removable scaffolding trees are not product code, and the project's style
rules were not written for them: the harness owns its own gates and their
conventions. Linting them judges one tree by another's standard.

Why this exists as a gate rather than a convention
--------------------------------------------------
The failure is silent and arrives from a commit that touches no product code.
A relocation moved four harness gates into a scaffolding tree that was absent
from ``extend-exclude``; the style gate went from clean to 559 findings, 558
of them in the relocated tree, and the distribution was dominated by the very
rules every other test surface waives. Nothing about the diff suggested lint,
and nothing about the lint output named the relocation. A tree gaining its
first ``.py`` file is the exact moment to check the scope, and it is a moment
no reviewer has any reason to notice.

The gate therefore keys on the trigger, not on a fixed list: a scaffolding
tree matters here only once it actually carries Python.

The membership check reads the same enumeration ``ruff`` effectively sees:
``ruff check .`` walks the filesystem directly rather than consulting a VCS
index, so a file this repository counts as present -- committed, or new and
not yet ignored -- is exactly what ruff would find too, tracked or not. Only a
``.gitignore``-listed file is correctly invisible to both.
"""

from __future__ import annotations

import tomllib
from collections.abc import Container
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Removable scaffolding layered over the product: the decision corpus, the
#: agent harness, and agent handovers. Named here to be EXCLUDED from the
#: product's lint scope, which is the one form of awareness the tooling tree
#: is permitted.
_SCAFFOLDING_TREES: Final[tuple[str, ...]] = (".vault", ".vaultspec", ".agents")


def _excluded(pyproject: Path) -> list[str]:
    """Return ruff's ``extend-exclude`` entries from a pyproject file."""
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return list(config.get("tool", {}).get("ruff", {}).get("extend-exclude", []))


def _python_bearing_trees(root: Path) -> set[str]:
    """Return the scaffolding trees that carry a Python file the repository enumerates."""
    found: set[str] = set()
    for relative in repository_files(root):
        head = relative.split("/", 1)[0]
        if head in _SCAFFOLDING_TREES and relative.endswith(".py"):
            found.add(head)
    return found


def _unscoped_trees(carrying_python: Container[str], excluded: Container[str]) -> list[str]:
    """Return the scaffolding trees that carry Python and are still linted.

    This decision was written out three times -- once in the gate and once
    in each of the two cases that prove the gate has teeth -- so neither
    teeth case ever called the gate. Three copies agree until one is edited,
    and the copies the teeth held were the ones that would go on passing.

    Discovery is the caller's to supply: the live gate enumerates the real
    repository, while a fixture tree is a small one built for the case.
    """
    return sorted(name for name in _SCAFFOLDING_TREES if name in carrying_python and name not in excluded)


def test_the_scaffolding_trees_are_named_correctly() -> None:
    """A gate naming trees that do not exist would pass by vacuity."""
    present = [name for name in _SCAFFOLDING_TREES if (REPO_ROOT / name).is_dir()]
    assert present, f"none of the scaffolding trees exist at {REPO_ROOT}"


def test_every_scaffolding_tree_with_python_is_out_of_lint_scope() -> None:
    """The direction the gate exists for: a tree gains Python, scope does not."""
    excluded = _excluded(REPO_ROOT / "pyproject.toml")
    unscoped = _unscoped_trees(_python_bearing_trees(REPO_ROOT), excluded)
    assert not unscoped, (
        "these scaffolding trees carry Python but are still linted with the "
        f"product's rules; add them to [tool.ruff] extend-exclude: {unscoped}"
    )


def test_the_gate_catches_a_tree_left_in_scope(tmp_path: Path) -> None:
    """Detector teeth: a scaffolding tree with Python and no exclusion is caught."""
    (tmp_path / ".vaultspec" / "tests").mkdir(parents=True)
    (tmp_path / ".vaultspec" / "tests" / "test_thing.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = [".vault"]\n', encoding="utf-8")
    excluded = _excluded(tmp_path / "pyproject.toml")

    assert _unscoped_trees(_python_bearing_trees(tmp_path), excluded) == [".vaultspec"]


def test_the_gate_stays_silent_on_a_tree_without_python(tmp_path: Path) -> None:
    """A prose-only scaffolding tree needs no exclusion to stay clean."""
    (tmp_path / ".vault" / "adr").mkdir(parents=True)
    (tmp_path / ".vault" / "adr" / "x.md").write_text("# a record\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nextend-exclude = []\n", encoding="utf-8")
    excluded = _excluded(tmp_path / "pyproject.toml")

    assert _unscoped_trees(_python_bearing_trees(tmp_path), excluded) == []


def test_an_ignored_python_file_does_not_force_an_exclusion(tmp_path: Path) -> None:
    """A file the contributor already declared noise is not this gate's business.

    ``ruff`` respects ``.gitignore`` by default, so a scaffolding tree holding
    only an ignored file is invisible to ruff too and needs no
    ``extend-exclude`` entry.
    """
    (tmp_path / ".vault").mkdir()
    (tmp_path / ".vault" / ".gitignore").write_text("*.py\n", encoding="utf-8")
    (tmp_path / ".vault" / "scratch.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nextend-exclude = []\n", encoding="utf-8")
    excluded = _excluded(tmp_path / "pyproject.toml")

    assert _unscoped_trees(_python_bearing_trees(tmp_path), excluded) == []
