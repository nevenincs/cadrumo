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
import sys
from pathlib import Path
from typing import Final

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

# Keep the source grammar pinned to the installation floor.  Running this gate
# on Python 3.14 or 3.15 must not silently bless syntax that Python 3.13 users
# cannot parse yet.
_OLDEST_SUPPORTED_PYTHON: Final[tuple[int, int]] = (3, 13)


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


def _parse_source(source: str, *, filename: str) -> ast.Module:
    """Parse one module using the oldest grammar the package promises."""
    return ast.parse(
        source,
        filename=filename,
        mode="exec",
        feature_version=_OLDEST_SUPPORTED_PYTHON,
    )


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
                _parse_source(source, filename=str(path))
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
    # Every declared root must EXIST and contribute, rather than be filtered out
    # of the scan by ``is_dir()``. Filtering is how this measurement dies
    # quietly: a root that moves is dropped, the remaining roots still make the
    # total non-zero, and the gate reports a clean parse over a tree it no
    # longer reaches. That exact loss is on record in this repository -- a
    # census whose roster was filtered the same way silently became one root
    # when the top-level tests tree moved under src. An aggregate guard cannot
    # catch it either: the roots differ by orders of magnitude, so the largest
    # alone keeps any total-based check satisfied however far the others fall.
    missing = tuple(str(root) for root in _PARSED_ROOTS if not root.is_dir())
    assert not missing, (
        "declared parse root(s) no longer exist, so this gate would report a clean parse "
        f"over a tree it never reached: {missing}"
    )
    per_root = {str(root): len(_python_files(root)) for root in _PARSED_ROOTS}
    empty = {name: count for name, count in per_root.items() if count == 0}
    assert not empty, f"declared parse root(s) contributed no modules, so nothing in them was parsed: {empty}"
    scanned = sum(per_root.values())

    failures = _syntax_failures()
    assert not failures, (
        f"{len(failures)} of {scanned} source file(s) do not parse. Every check that walks or "
        "imports source is unreliable until these are fixed, and each will surface as an "
        "unrelated suite's failure attributed to that suite's subject:\n  " + "\n  ".join(failures)
    )


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Python 3.14 template-string grammar is unavailable on the 3.13 floor",
)
def test_parser_rejects_syntax_newer_than_the_supported_floor() -> None:
    """A newer interpreter must not make newer-only syntax look supported."""
    with pytest.raises(SyntaxError):
        _parse_source('value = t"template {name}"', filename="newer_syntax.py")


def test_the_independent_prune_list_still_matches_the_shared_one() -> None:
    """The copy above is required; nothing was making it stay a copy.

    ``_python_files`` deliberately restates the prune names rather than
    importing them, for the reason its own docstring gives: importing the
    shared inventory pulls the package import graph, and this gate exists for
    the state in which that graph is broken. That independence is right, and
    it is also why the two lists can drift apart without anything noticing --
    each walk stays self-consistent, so a divergence changes which tree is
    scanned and nothing compares the two.

    The join is placed here, in the module that owns the copy, and imports
    inside the function body on purpose: the module still imports with only
    the standard library, so a broken graph fails THIS test alone and leaves
    the parse gate above running, which is the whole point of the copy.
    """
    from ._project_inventory import _PRUNE_DIRECTORY_NAMES as SHARED_PRUNE_DIRECTORY_NAMES

    assert SHARED_PRUNE_DIRECTORY_NAMES == _PRUNE_DIRECTORY_NAMES, (
        "the independent prune list has drifted from the shared inventory's, so the two walks "
        f"no longer cover the same tree: here={sorted(_PRUNE_DIRECTORY_NAMES)} "
        f"shared={sorted(SHARED_PRUNE_DIRECTORY_NAMES)}"
    )
