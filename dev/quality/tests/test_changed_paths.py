"""Tests for the changed-path preflight's file selection.

`dev.quality.module_test_reach` listed `dev/quality/changed_paths.py` as
unreached. It answers "did THIS change leave the paths it touched clean?", and
what it selects is the whole of that answer: a path it does not return is a path
no check runs against, and the preflight still exits 0.

It selected from ``git diff`` alone. Git reports only what it already knows
about, so a change consisting entirely of NEW files produced an empty path set
and the run exited 0 having checked nothing - reporting the change clean at the
exact moment its files had never been looked at once. Reproduced against a real
repository before the fix: a committed tree plus one brand-new file gave
``git diff --name-only HEAD`` no output at all.

Selection is now driven against scratch repositories through an injected root.
That parameter was added for this: the module read a module-level constant, so
the union could not be exercised without committing to the real tree.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from ..changed_paths import changed_python_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _run(root: pathlib.Path, *arguments: str) -> None:
    subprocess.run(("git", *arguments), cwd=root, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repository(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch repository with one committed Python file."""
    _run(tmp_path, "init", "-q")
    _run(tmp_path, "config", "user.email", "preflight@example.invalid")
    _run(tmp_path, "config", "user.name", "Preflight")
    (tmp_path / "seed.py").write_text("VALUE = 1" + chr(10), encoding="utf-8")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def _names(root: pathlib.Path) -> set[str]:
    return {path.name for path in changed_python_paths("HEAD", repo_root=root)}


def test_a_brand_new_file_is_checked(repository: pathlib.Path) -> None:
    """The defect: a change made only of new files was reported clean unchecked.

    ``git diff`` says nothing about a file git has never seen, so the preflight
    had no paths, ran no checks, and exited 0.
    """
    (repository / "fresh.py").write_text("import os" + chr(10), encoding="utf-8")

    assert "fresh.py" in _names(repository)


def test_a_modified_tracked_file_is_still_checked(repository: pathlib.Path) -> None:
    """The case that already worked must survive the union."""
    (repository / "seed.py").write_text("VALUE = 2" + chr(10), encoding="utf-8")

    assert "seed.py" in _names(repository)


def test_a_staged_new_file_is_not_counted_twice(repository: pathlib.Path) -> None:
    """A staged addition appears in BOTH queries, and duplicates would double every check."""
    (repository / "staged.py").write_text("VALUE = 3" + chr(10), encoding="utf-8")
    _run(repository, "add", "staged.py")

    selected = changed_python_paths("HEAD", repo_root=repository)

    assert [path.name for path in selected].count("staged.py") == 1


def test_an_ignored_file_stays_out(repository: pathlib.Path) -> None:
    """The contributor already declared it noise; the preflight must honour that.

    Without this, build output and caches become the preflight's problem and
    its cost stops being bounded by the size of the change.
    """
    (repository / ".gitignore").write_text("generated/" + chr(10), encoding="utf-8")
    (repository / "generated").mkdir()
    (repository / "generated" / "emitted.py").write_text("VALUE = 4" + chr(10), encoding="utf-8")

    assert "emitted.py" not in _names(repository)


def test_a_non_python_change_is_not_selected(repository: pathlib.Path) -> None:
    """Every downstream check reads Python; a document handed to ruff is a crash."""
    (repository / "notes.md").write_text("# notes" + chr(10), encoding="utf-8")

    assert not _names(repository) & {"notes.md"}


def test_a_deleted_file_is_dropped(repository: pathlib.Path) -> None:
    """A check cannot speak about a file that is no longer there."""
    (repository / "seed.py").unlink()

    assert "seed.py" not in _names(repository)


def test_the_selection_is_sorted(repository: pathlib.Path) -> None:
    """Two runs over one change must present the same order to the same checks."""
    for name in ("zulu.py", "alpha.py", "mike.py"):
        (repository / name).write_text("VALUE = 5" + chr(10), encoding="utf-8")

    selected = changed_python_paths("HEAD", repo_root=repository)

    assert list(selected) == sorted(selected)


def test_an_unknown_base_refuses_rather_than_selecting_nothing(
    repository: pathlib.Path,
) -> None:
    """An empty selection is how this preflight says "clean", so it must not mean "broken".

    A mistyped base that returned no paths would exit 0 and read exactly like a
    change with nothing to check.
    """
    with pytest.raises(SystemExit, match="check-changed"):
        changed_python_paths("no-such-base-anywhere", repo_root=repository)


def test_a_clean_tree_selects_nothing(repository: pathlib.Path) -> None:
    """The honest empty case: nothing changed, so there is nothing to check."""
    assert changed_python_paths("HEAD", repo_root=repository) == ()
