"""Every production module is reached, by import or by name.

A structural ratchet's scan surface is only as trustworthy as its definition of
"production". A scratch file left in the package root is walked as production
code and discovered as a real capability, which reads as census drift to whoever
runs the gate next -- a false finding that costs a diagnosis rather than a crash
that announces itself.

Two obvious exclusions were rejected before this one:

* a NAME CONVENTION guesses what a scratch file will be called, and the guess is
  wrong the first time someone picks a different prefix;
* a GIT-TRACKED filter couples a pure filesystem walk to a checkout, and would
  hide legitimate uncommitted modules from every ratchet that uses it. During a
  relocation campaign the uncommitted set is dominated by real new modules, so
  that filter fails false-clean on exactly the surface under change.

What survives both is REACHABILITY, widened past static imports. A production
module earns its place by being imported, or by being named somewhere -- a
command-spec enrolment, an error-code registry entry, a string module path. Real
modules satisfy one or the other; a scratch probe satisfies neither.

The check refuses rather than filters. An orphan is either a scratch file or a
module whose enrolment is missing, and both deserve a failure that names the
file instead of being silently dropped from a ratchet's surface.

The scan surface spans both the shipped package and the development tree that
compiles and validates it, so this gate lives with the other repository-wide
quality ratchets rather than beside the package it also happens to scan.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import pytest

from cadrumo.tests.inventory import REPO_ROOT, SRC_CADRUMO, production_python_files, python_files_under

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module_name(path: Path, root: Path) -> tuple[str, bool]:
    parts = list(path.with_suffix("").relative_to(root).parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _absolute_target(node: ast.ImportFrom, here: str, is_package: bool) -> str | None:
    if node.level == 0:
        return node.module
    parts = here.split(".")
    anchor = parts[: len(parts) - node.level + (1 if is_package else 0)]
    if not anchor:
        return None
    tail: list[str] = [node.module] if node.module else []
    return ".".join(anchor + tail)


@cache
def _scanned_sources() -> dict[Path, str]:
    """Read the scanned tree once per process.

    Cached because every assertion in this module needs the same text, and
    re-reading it per test doubled the gate's file I/O for nothing.
    """
    sources: dict[Path, str] = {}
    for root in (SRC_CADRUMO, REPO_ROOT / "dev"):
        if not root.exists():
            continue
        for path in python_files_under(root):
            if "__pycache__" in path.parts:
                continue
            try:
                sources[path] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return sources


_WORD = re.compile(r"\w+")


@cache
def _tokens_by_source() -> dict[Path, frozenset[str]]:
    r"""Return each scanned source's set of whole words.

    ``\bstem\b`` matches a module stem exactly when that stem appears as a
    complete run of word characters, because the stem is a Python identifier and
    is therefore all word characters itself -- those boundaries assert nothing
    more than "the neighbours are not word characters". Membership in this set
    asks the same question, once per source instead of once per source PER
    unimported module.
    """
    return {path: frozenset(_WORD.findall(text)) for path, text in _scanned_sources().items()}


@cache
def _sources_naming() -> dict[str, int]:
    """Return, per word, how many scanned sources contain it."""
    counts: dict[str, int] = {}
    for words in _tokens_by_source().values():
        for word in words:
            counts[word] = counts.get(word, 0) + 1
    return counts


def _named_outside(word: str, path: Path) -> bool:
    """Whether ``word`` appears in some scanned source other than ``path``.

    The question both reachability arms ask. Answered from the index rather than
    by sweeping every source per candidate, which is what made this gate
    quadratic.
    """
    own = 1 if word in _tokens_by_source().get(path, frozenset()) else 0
    return _sources_naming().get(word, 0) - own > 0


def _statically_imported(sources: dict[Path, str]) -> set[str]:
    imported: set[str] = set()
    for path, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        anchor = SRC_CADRUMO.parent if path.is_relative_to(SRC_CADRUMO) else REPO_ROOT
        here, is_package = _module_name(path, anchor)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = _absolute_target(node, here, is_package)
                if target:
                    imported.add(target)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
    return imported


def test_every_production_module_is_imported_or_named_somewhere() -> None:
    sources = _scanned_sources()
    imported = _statically_imported(sources)
    # `_named_outside` replaces a fresh regex swept across every source for each
    # unimported module. That inner sweep was O(modules x bytes) and dominated
    # this gate at 91 s; the index answers the same question, as its own note
    # explains.
    orphans: list[str] = []
    for path in production_python_files():
        if path.name == "__init__.py":
            continue
        dotted, _ = _module_name(path, SRC_CADRUMO.parent)
        if dotted in imported:
            continue
        if _named_outside(path.stem, path):
            continue
        orphans.append(path.relative_to(REPO_ROOT).as_posix())

    assert not orphans, (
        "these production modules are neither imported nor named anywhere, so a "
        "structural ratchet would walk them as production code without anything "
        "establishing that they are: " + ", ".join(sorted(orphans))
    )


def test_the_detector_would_catch_a_scratch_file_in_the_package_root() -> None:
    """A zero-orphan result must mean the tree is clean, not that nothing is checked."""
    invented = "_untracked_scratch_probe_sentinel_4711"

    here = next((path for path in _scanned_sources() if path.resolve() == Path(__file__).resolve()), None)
    assert here is not None, "this module must itself sit inside the scanned tree, or the sentinel proves nothing"
    assert not _named_outside(invented, here), "the sentinel name was expected to appear nowhere but this file"

    # A real module, by contrast, must be reachable by the same rule.
    reachable = sum(
        1 for path in production_python_files()[:200] if path.name != "__init__.py" and _named_outside(path.stem, path)
    )
    assert reachable, "the name-reference arm matched nothing at all, so it proves nothing"
