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

The scan surface spans the five shipped source packages and the development
tree that compiles and validates them, so this gate lives with the other
repository-wide quality ratchets rather than beside one package it scans.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import pytest

from cadrumo.tests.inventory import REPO_ROOT, python_files_under
from dev.first_party_source import FIRST_PARTY_ROOTS, is_production_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SRC_ROOT = REPO_ROOT / "src"
_SOURCE_PACKAGE_ROOTS = tuple(REPO_ROOT / root for root in FIRST_PARTY_ROOTS if root.startswith("src/"))


def _module_name(path: Path, root: Path) -> tuple[str, bool]:
    parts = list(path.with_suffix("").relative_to(root).parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _module_root(path: Path) -> Path:
    """Return the import root for a shipped source module or development module."""
    return SRC_ROOT if path.is_relative_to(SRC_ROOT) else REPO_ROOT


def _absolute_target(node: ast.ImportFrom, here: str, is_package: bool) -> str | None:
    if node.level == 0:
        return node.module
    parts = here.split(".")
    anchor = parts[: len(parts) - node.level + (1 if is_package else 0)]
    if not anchor:
        return None
    tail: list[str] = [node.module] if (node.module is not None and node.module) else []
    return ".".join(anchor + tail)


@cache
def _scanned_sources() -> dict[Path, str]:
    """Read the scanned tree once per process.

    Cached because every assertion in this module needs the same text, and
    re-reading it per test doubled the gate's file I/O for nothing.
    """
    sources: dict[Path, str] = {}
    for root in (*_SOURCE_PACKAGE_ROOTS, REPO_ROOT / "dev"):
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


def _orphan_paths(
    sources: dict[Path, str],
    production_paths: tuple[Path, ...],
    *,
    token_index: dict[Path, frozenset[str]] | None = None,
    name_counts: dict[str, int] | None = None,
) -> tuple[str, ...]:
    """Return production paths without a static import or an outside name reference."""
    imported = _statically_imported(sources)
    if token_index is None:
        token_index = {path: frozenset(_WORD.findall(text)) for path, text in sources.items()}
    if name_counts is None:
        name_counts = {}
        for words in token_index.values():
            for word in words:
                name_counts[word] = name_counts.get(word, 0) + 1

    orphans: list[str] = []
    for path in production_paths:
        if path.name == "__init__.py":
            continue
        dotted, _ = _module_name(path, _module_root(path))
        if dotted in imported:
            continue
        own = 1 if path.stem in token_index.get(path, frozenset()) else 0
        if name_counts.get(path.stem, 0) - own > 0:
            continue
        orphans.append(path.relative_to(REPO_ROOT).as_posix())
    return tuple(sorted(orphans))


def _production_source_paths() -> tuple[Path, ...]:
    """Enumerate production modules from every configured shipped source root."""
    return tuple(
        sorted(
            path
            for root in _SOURCE_PACKAGE_ROOTS
            for path in python_files_under(root)
            if is_production_source(path.relative_to(REPO_ROOT).as_posix())
        )
    )


def _statically_imported(sources: dict[Path, str]) -> set[str]:
    imported: set[str] = set()
    for path, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        anchor = _module_root(path)
        here, is_package = _module_name(path, anchor)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = _absolute_target(node, here, is_package)
                if target is not None and target:
                    imported.add(target)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
    return imported


def test_every_production_module_is_imported_or_named_somewhere() -> None:
    sources = _scanned_sources()
    orphans = _orphan_paths(
        sources,
        _production_source_paths(),
        token_index=_tokens_by_source(),
        name_counts=_sources_naming(),
    )

    assert not orphans, (
        "these production modules are neither imported nor named anywhere, so a "
        "structural ratchet would walk them as production code without anything "
        "establishing that they are: " + ", ".join(sorted(orphans))
    )


def test_the_detector_would_catch_a_scratch_file_in_the_package_root() -> None:
    """A planted unreferenced module must fail even when sources are in memory."""
    scratch = SRC_ROOT / "cadrumo" / "application" / "_untracked_scratch_probe_sentinel_4711.py"
    assert _orphan_paths({scratch: "VALUE = 1\n"}, (scratch,)) == (
        "src/cadrumo/application/_untracked_scratch_probe_sentinel_4711.py",
    )

    # A real module, by contrast, must be reachable by the same rule.
    reachable = sum(
        1 for path in _production_source_paths()[:200] if path.name != "__init__.py" and _named_outside(path.stem, path)
    )
    assert reachable, "the name-reference arm matched nothing at all, so it proves nothing"


def test_cross_package_imports_are_reachability_evidence() -> None:
    """A module imported by another shipped package belongs to the live graph."""
    module = SRC_ROOT / "cadrumo" / "application" / "_cross_package_probe.py"
    runtime_caller = SRC_ROOT / "cadrumo_runtime" / "host" / "probe.py"
    sources = {
        module: "VALUE = 1\n",
        runtime_caller: "import cadrumo.application._cross_package_probe\n",
    }

    assert _orphan_paths(sources, (module,)) == ()
