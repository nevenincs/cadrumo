"""Tests for the namespace-retirement sweep's readable surface.

The module rewrites source files behind ``--apply`` and had no tests, which
`dev.quality.module_test_reach` ranks first alongside one other codemod for
exactly that pair of properties.

Two things it does are testable and one is not, and the boundary is worth
stating because it is a property of the module rather than of this file. Its
``apply`` flag is a MODULE-LEVEL global read from ``sys.argv`` at import, and
its five fix passes walk the real ``src/cadrumo`` tree through a module
constant with no injectable root. So apply-mode cannot be exercised without
rewriting the repository, and no test here does. What that leaves is the
safety property that makes importing the module safe at all - the flag is False
unless somebody typed the argument - and the two pure readers the passes are
built on.
"""

from __future__ import annotations

import pathlib

import pytest

from ..namespace_retirement_sweep import _constants, _read, apply

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_importing_the_sweep_does_not_arm_it() -> None:
    """The flag is read from ``sys.argv`` at import, so importing must be inert.

    Every test in this file imports the module, and five of its functions
    rewrite files when the flag is set. If a pytest invocation could ever set
    it, running this suite would rewrite the tree it is testing.
    """
    assert apply is False


def test_an_unreadable_path_yields_none_rather_than_killing_the_sweep(
    tmp_path: pathlib.Path,
) -> None:
    """A peer can delete a file between the glob and the read.

    The module's own docstring gives the reason: a sweep that dies at file four
    hundred has silently not checked four hundred to nine hundred and says
    nothing about them, which is worse than missing one file.
    """
    assert _read(tmp_path / "never-existed.py") is None


def test_a_readable_file_is_returned_verbatim(tmp_path: pathlib.Path) -> None:
    """The guard must not also swallow content."""
    source = tmp_path / "present.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    assert _read(source) == "VALUE = 1\n"


def test_undecodable_bytes_are_skipped_rather_than_raising(tmp_path: pathlib.Path) -> None:
    """A binary file under a ``*.py`` glob is a real thing in a shared tree."""
    source = tmp_path / "binary.py"
    source.write_bytes(b"\xff\xfe\x00\x01not utf-8")

    assert _read(source) is None


def test_string_constants_are_reported_with_their_own_lines() -> None:
    """The ordinary case the pin comparison is built on."""
    found = _constants('FIRST = "alpha"\nSECOND = "beta"\n')

    assert [(item.value, item.lineno) for item in found] == [("alpha", 1), ("beta", 2)]


def test_a_pin_inside_embedded_python_source_is_found() -> None:
    """The defect this walk exists for, and it was not hypothetical.

    A test that reproduces a crash in a fresh interpreter passes the child's
    program as one big string, so every pin inside it is a constant of the
    CHILD and the parent's walk sees one opaque string. The module's docstring
    records a config-reset gate whose pin stopped matching after a rename while
    this very sweep ran clean over it.
    """
    child = "\n".join(f"line_{index} = 'padding to exceed forty characters'" for index in range(3))
    parent = f'PROGRAM = """{child}\nimport _lifecycle\n"""\n'

    values = [item.value for item in _constants(parent)]

    assert any("_lifecycle" in value for value in values), "the embedded program was not re-walked"


def test_an_embedded_pin_is_anchored_to_the_parent_line_that_holds_it() -> None:
    """The child's own line numbers mean nothing in the file being reported.

    Reporting them would send a reader to a line that has nothing to do with
    the pin, in the file the sweep names.
    """
    child = "\n".join(f"value_{index} = 'padding to exceed forty characters'" for index in range(4))
    parent = f'HEADER = 1\nPROGRAM = """{child}\n"""\n'

    embedded = [item for item in _constants(parent) if "padding" in item.value]

    assert embedded, "no embedded constant was found"
    assert {item.lineno for item in embedded} == {2}


def test_a_string_that_is_not_python_is_left_alone() -> None:
    """Most strings are not programs, and failing to parse is the filter."""
    prose = 'NOTE = """This is a long sentence that is certainly not valid Python source at all."""\n'

    assert [item.value for item in _constants(prose)] == [
        "This is a long sentence that is certainly not valid Python source at all."
    ]


def test_a_file_that_does_not_parse_reports_no_constants() -> None:
    """A syntax error is a file this sweep cannot speak about, not an empty one."""
    assert _constants("def (:\n") == []
