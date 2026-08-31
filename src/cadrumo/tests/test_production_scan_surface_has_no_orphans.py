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
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from .inventory import REPO_ROOT, SRC_CADRUMO, production_python_files, python_files_under

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
    return ".".join(anchor + ([node.module] if node.module else []))


def _scanned_sources() -> dict[Path, str]:
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

    orphans: list[str] = []
    for path in production_python_files():
        if path.name == "__init__.py":
            continue
        dotted, _ = _module_name(path, SRC_CADRUMO.parent)
        if dotted in imported:
            continue
        pattern = re.compile(rf"\b{re.escape(path.stem)}\b")
        if any(pattern.search(text) for other, text in sources.items() if other != path):
            continue
        orphans.append(path.relative_to(REPO_ROOT).as_posix())

    assert not orphans, (
        "these production modules are neither imported nor named anywhere, so a "
        "structural ratchet would walk them as production code without anything "
        "establishing that they are: " + ", ".join(sorted(orphans))
    )


def test_the_detector_would_catch_a_scratch_file_in_the_package_root() -> None:
    """A zero-orphan result must mean the tree is clean, not that nothing is checked."""
    sources = _scanned_sources()
    invented = "_untracked_scratch_probe_sentinel_4711"
    pattern = re.compile(rf"\b{re.escape(invented)}\b")

    here = Path(__file__).resolve()
    elsewhere = {path: text for path, text in sources.items() if path.resolve() != here}
    assert not any(pattern.search(text) for text in elsewhere.values()), (
        "the sentinel name was expected to appear nowhere but this file"
    )

    # A real module, by contrast, must be reachable by the same rule.
    reachable = 0
    for path in production_python_files()[:200]:
        if path.name == "__init__.py":
            continue
        stem = re.compile(rf"\b{re.escape(path.stem)}\b")
        if any(stem.search(text) for other, text in sources.items() if other != path):
            reachable += 1
    assert reachable, "the name-reference arm matched nothing at all, so it proves nothing"
