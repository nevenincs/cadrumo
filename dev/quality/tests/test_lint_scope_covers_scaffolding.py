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
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

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


def _tracked_python_trees(repo_root: Path) -> set[str]:
    """Return the scaffolding trees that carry TRACKED Python, asked of git.

    Git is both faster and more correct than walking: a scaffolding tree holds
    generated data (the search index among it) that a ``rglob`` must traverse
    in full to prove a negative, and an untracked scratch file in a corpus is
    not something the project's lint scope has any business covering.
    """
    git = shutil.which("git")
    assert git is not None, "git is required to establish which trees carry tracked Python"
    listed = subprocess.run(  # noqa: S603
        [git, "-C", str(repo_root), "ls-files", "--", *(f"{n}/**/*.py" for n in _SCAFFOLDING_TREES)],
        capture_output=True,
        text=True,
        check=False,
    )
    found: set[str] = set()
    for line in listed.stdout.splitlines():
        head = line.split("/", 1)[0]
        if head in _SCAFFOLDING_TREES:
            found.add(head)
    return found


def _carries_python(tree: Path) -> bool:
    """Whether a tree exists and holds at least one Python file (fixture use)."""
    return tree.is_dir() and any(tree.rglob("*.py"))


def test_the_scaffolding_trees_are_named_correctly() -> None:
    """A gate naming trees that do not exist would pass by vacuity."""
    present = [name for name in _SCAFFOLDING_TREES if (REPO_ROOT / name).is_dir()]
    assert present, f"none of the scaffolding trees exist at {REPO_ROOT}"


def test_every_scaffolding_tree_with_python_is_out_of_lint_scope() -> None:
    """The direction the gate exists for: a tree gains Python, scope does not."""
    excluded = _excluded(REPO_ROOT / "pyproject.toml")
    unscoped = sorted(name for name in _SCAFFOLDING_TREES if _carries_python(REPO_ROOT / name) and name not in excluded)
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
    unscoped = [name for name in _SCAFFOLDING_TREES if _carries_python(tmp_path / name) and name not in excluded]
    assert unscoped == [".vaultspec"]


def test_the_gate_stays_silent_on_a_tree_without_python(tmp_path: Path) -> None:
    """A prose-only scaffolding tree needs no exclusion to stay clean."""
    (tmp_path / ".vault" / "adr").mkdir(parents=True)
    (tmp_path / ".vault" / "adr" / "x.md").write_text("# a record\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nextend-exclude = []\n", encoding="utf-8")
    excluded = _excluded(tmp_path / "pyproject.toml")
    unscoped = [name for name in _SCAFFOLDING_TREES if _carries_python(tmp_path / name) and name not in excluded]
    assert unscoped == []
