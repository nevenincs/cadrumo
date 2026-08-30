"""Refuse a repository carrying a source file Python cannot parse.

A mechanical sweep across many files -- an import repoint, a rename, a codemod
-- can leave a file syntactically invalid, and nothing here notices until some
unrelated suite happens to import it. Three such files sat in this tree at once,
each surfacing only as a different gate's failure, and each attributed to that
gate's subject rather than to the broken file: an architecture-parity check
reporting an ``IndentationError`` reads as an architecture violation, and the
reader goes looking for a relocation defect that does not exist.

The discovery was also serial. Fixing one and re-running surfaced the next,
because no enumeration existed -- only whatever the next import chain happened
to touch. A per-file failure that reappears at a new location after each fix is
the signature of a population nobody counted.

This gate counts it. Parsing every source file is total rather than sampled,
costs one pass, and converts three accidental discoveries across three unrelated
suites into one list with every offender named.

It asserts nothing about what the code MEANS. A file that parses can still be
wrong in every other way; this only refuses the state in which no other gate's
verdict can be trusted, because a module that cannot be parsed cannot be
imported, scanned, or reasoned about by any check downstream of it.

See Also:
    :mod:`cadrumo.tests._lost_test_hook`
        The reporter for the other way a suite's verdict misleads: tests that
        were collected and then never ran.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PARSED_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "cadrumo",
    REPO_ROOT / "dev",
    REPO_ROOT / "packaging",
)
"""The shipped package and the tooling that gates it.

These are the trees whose syntax every other repository-wide check depends on:
a scanner that walks source cannot walk a file that does not parse, and a suite
cannot import one.
"""


_PRUNE_DIRECTORY_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", ".venv", ".pytest_cache"})


def _python_files(root: Path) -> tuple[Path, ...]:
    """Walk ``root`` for ``.py`` files using the standard library only.

    Deliberately does NOT reuse the project's own directory scanner. That
    helper is the canonical enumerator and reusing it would be the correct
    instinct anywhere else -- but importing it pulls the package's import
    graph, and this gate exists precisely for the state in which that graph
    is broken. Verified the hard way: while a peer's in-flight sweep left
    ``core/redaction`` unparseable, the earlier version of this module could
    not be imported at all, because the scanner it reused reaches that file
    transitively. A gate that cannot run when the tree is broken is useless
    exactly when it is needed, so this walk owes the tree nothing.
    """
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in _PRUNE_DIRECTORY_NAMES]
        found.extend(Path(directory) / name for name in filenames if name.endswith(".py"))
    return tuple(sorted(found))


def _display(path: Path) -> str:
    """Render a scanned path for the failure line, repo-relative where possible.

    ``relative_to`` RAISES on a path outside the repository, so calling it
    unguarded puts a second failure inside the reporting path of the first --
    the gate would crash with a confusing ValueError instead of naming the
    unparseable file it had correctly found.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _syntax_failures() -> tuple[str, ...]:
    """Return one line per source file the interpreter refuses to parse."""
    failures: list[str] = []
    for root in _PARSED_ROOTS:
        if not root.is_dir():
            continue
        for path in _python_files(root):
            try:
                source = path.read_text(encoding="utf-8")
            except OSError as error:  # pragma: no cover - unreadable file is its own defect
                failures.append(f"{_display(path)}: unreadable: {error}")
                continue
            try:
                ast.parse(source, filename=str(path))
            except SyntaxError as error:
                where = f"{_display(path)}:{error.lineno}"
                failures.append(f"{where}: {type(error).__name__}: {error.msg}")
    return tuple(sorted(failures))


def test_every_source_file_parses() -> None:
    """No tracked source file may be syntactically invalid.

    Names every offender rather than the first, because these arrive in
    batches -- one mechanical sweep produced three -- and a gate that reports
    only the first turns a single list into a serial rediscovery.
    """
    scanned = sum(len(_python_files(root)) for root in _PARSED_ROOTS if root.is_dir())
    assert scanned, "no source files were scanned; this gate would pass vacuously"

    failures = _syntax_failures()
    assert not failures, (
        f"{len(failures)} of {scanned} source file(s) do not parse. Every check that walks or "
        "imports source is unreliable until these are fixed, and each will surface as an "
        "unrelated suite's failure attributed to that suite's subject:\n  " + "\n  ".join(failures)
    )
