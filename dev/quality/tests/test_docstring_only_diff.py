"""Tests for the docstring-only-change prover.

`dev.quality.module_test_reach` listed `dev/quality/docstring_only_diff.py` as
unreached. It exists to prove an edit added documentation and altered no
behaviour, and it had nothing establishing that it could tell the two apart.

Testing it found the prover passing on nothing. Handed an empty path list it
printed ``checked 0 file(s); 0 offender(s)`` and exited 0 - the identical result
it gives for a genuinely clean docstring-only edit - and the entry point turned
a bare invocation into exit 0 without calling it at all. An invocation whose
path expansion produced no matches therefore read as proof that behaviour was
unchanged. That is the vacuity class this repository screens for elsewhere,
inside the tool whose whole purpose is proof.

The git boundary is real: each case builds a scratch repository, commits a
version, edits the working copy, and asks the prover about the difference. No
``subprocess`` is patched, because what is being proven is precisely that the
committed bytes and the working bytes are compared correctly.
"""

from __future__ import annotations

import pathlib
import subprocess
from textwrap import dedent

import pytest

from ..docstring_only_diff import _skeleton, check

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _run(root: pathlib.Path, *arguments: str) -> None:
    subprocess.run(("git", *arguments), cwd=root, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repository(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Return a scratch repository, with the prover's relative paths resolving inside it.

    The module reads the working copy through a repo-relative path and the
    committed copy through ``git show`` in the current directory, so both sides
    have to agree on where "here" is.
    """
    _run(tmp_path, "init", "-q")
    _run(tmp_path, "config", "user.email", "prover@example.invalid")
    _run(tmp_path, "config", "user.name", "Docstring Prover")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _commit(root: pathlib.Path, name: str, source: str) -> str:
    (root / name).write_text(dedent(source), encoding="utf-8")
    _run(root, "add", "-A")
    _run(root, "commit", "-qm", f"add {name}")
    return name


def test_no_paths_at_all_refuses_rather_than_reporting_success() -> None:
    """A prover handed nothing to prove must not answer the same as a clean run.

    This returned 0, indistinguishable from a genuinely docstring-only edit, so
    an invocation whose path expansion matched nothing passed as proof.
    """
    assert check([]) == 1


def test_adding_a_docstring_is_accepted(repository: pathlib.Path) -> None:
    """The supported change, and the whole reason the tool exists."""
    name = _commit(
        repository,
        "module.py",
        """
        def widen(value):
            return value + 1
        """,
    )
    (repository / name).write_text(
        dedent(
            '''
            """A module that widens."""


            def widen(value):
                """Return one more than value."""
                return value + 1
            '''
        ),
        encoding="utf-8",
    )

    assert check([name]) == 0


def test_changing_executable_code_is_refused(repository: pathlib.Path) -> None:
    """The defect the tool exists to catch, hidden behind an added docstring.

    A reviewer reading a large documentation diff is exactly who cannot see a
    changed operator buried in it.
    """
    name = _commit(
        repository,
        "module.py",
        """
        def widen(value):
            return value + 1
        """,
    )
    (repository / name).write_text(
        dedent(
            '''
            def widen(value):
                """Return one more than value."""
                return value + 2
            '''
        ),
        encoding="utf-8",
    )

    assert check([name]) == 1


def test_reformatting_alone_is_accepted_because_the_comparison_is_structural(
    repository: pathlib.Path,
) -> None:
    """Both sides are unparsed, so quoting and spacing cannot register as change.

    Worth pinning: a textual comparison here would refuse a run where the
    formatter touched a line, and the tool would be useless on any real edit.
    """
    name = _commit(
        repository,
        "module.py",
        """
        def widen(value):
            return   value+1
        """,
    )
    (repository / name).write_text(
        dedent(
            """
            def widen(value):
                return value + 1
            """
        ),
        encoding="utf-8",
    )

    assert check([name]) == 0


def test_a_file_not_tracked_at_the_ref_is_refused(repository: pathlib.Path) -> None:
    """A new file has no committed behaviour to be unchanged from."""
    _commit(repository, "module.py", "VALUE = 1\n")
    (repository / "fresh.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert check(["fresh.py"]) == 1


def test_a_tracked_file_that_vanished_is_refused_rather_than_crashing(
    repository: pathlib.Path,
) -> None:
    """Deleting a file is not a docstring-only change, and must be SAID.

    Letting the read escape as an OSError would end the run in a traceback that
    says nothing about the files after it in the list - so a deletion in
    position one would leave the rest of the change unexamined.
    """
    name = _commit(repository, "module.py", "VALUE = 1\n")
    _commit(repository, "second.py", "OTHER = 2\n")
    (repository / name).unlink()

    assert check([name, "second.py"]) == 1


def test_an_unparsable_working_copy_is_reported_not_raised(repository: pathlib.Path) -> None:
    """A syntax error is a file the prover cannot speak about, not a clean one."""
    name = _commit(repository, "module.py", "VALUE = 1\n")
    (repository / name).write_text("def (:\n", encoding="utf-8")

    assert check([name]) == 1


def test_a_module_whose_only_statement_is_its_docstring_still_parses() -> None:
    """Stripping the sole statement must leave a body, or unparsing raises.

    A docs-only module is a real shape in this tree, and it is the one input
    that empties a body completely.
    """
    assert _skeleton('"""Only a docstring."""\n') == "pass"


def test_docstrings_are_stripped_at_every_level_that_can_carry_one() -> None:
    """Module, class, function and async function each hold one separately."""
    source = dedent(
        '''
        """Module."""


        class Thing:
            """Class."""

            def method(self):
                """Method."""
                return 1

            async def coroutine(self):
                """Coroutine."""
                return 2
        '''
    )

    skeleton = _skeleton(source)

    assert "Module." not in skeleton
    assert "Class." not in skeleton
    assert "Method." not in skeleton
    assert "Coroutine." not in skeleton
    assert "return 1" in skeleton


def test_a_string_that_is_not_in_the_docstring_position_survives() -> None:
    """Only the first statement is a docstring; the rest are values.

    Stripping any leading string constant would delete real data - a module
    whose first assignment is a string would lose it - and the comparison would
    then call a genuine change clean.
    """
    skeleton = _skeleton('VALUE = "kept"\n"""not a docstring here"""\n')

    assert "kept" in skeleton
    assert "not a docstring here" in skeleton
