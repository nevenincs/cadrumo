"""Gate: no module publishes a name that exists only so a test can import it.

The shape is ``PUBLIC = ORIGIN`` at module level, where ``ORIGIN`` is defined
or imported in the same module and the public alias is imported by nothing but
tests.
It reads as published API and is not: the architecture rule bars alias and
re-export layers outright, and the alias also hides that the module's real
surface is the private one.

The target must be bound in the same module, including by import. The alias
must have at least one test consumer, which excludes an export
  nothing reads at all, a published-surface decision rather than an alias;
and the alias must be dead in production, so a genuine second name in use is
  untouched.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"


def _module_texts() -> tuple[dict[Path, str], dict[Path, str], tuple[str, ...]]:
    """Return (production, test) sources, and what this walk could not read.

    One skip fails three ways, and only one of them is safe. A production
    module lost as EVIDENCE lowers the production use count, so an alias
    looks less used and the gate flags more -- a false alarm. But the same
    module lost as SUBJECT takes its own aliases out of the scan entirely,
    and a test module lost drops the test use count below the threshold the
    offender condition requires, so a genuine test-only alias stops looking
    like one. Two of the three directions are silent."""
    production: dict[Path, str] = {}
    tests: dict[Path, str] = {}
    unread: list[str] = []
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            unread.append(path.relative_to(_PACKAGE_ROOT).as_posix())
            continue
        (tests if "tests" in path.parts else production)[path] = text
    return production, tests, tuple(unread)


def _uses(name: str, corpus: dict[Path, str], skip: Path | None = None) -> int:
    """Count whole-word occurrences of ``name`` across ``corpus``."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return sum(len(pattern.findall(text)) for path, text in corpus.items() if path != skip)


def _bound_names(tree: ast.Module) -> set[str]:
    """Return every name the module binds at its top level."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            names.add(node.targets[0].id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def find_test_only_aliases(production: dict[Path, str], tests: dict[Path, str]) -> list[tuple[str, str, str]]:
    """Return every ``PUBLIC = _PRIVATE`` alias only tests consume."""
    offenders: list[tuple[str, str, str]] = []
    for path, text in production.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        local = _bound_names(tree)
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                continue
            target, value = node.targets[0], node.value
            if not (isinstance(target, ast.Name) and isinstance(value, ast.Name)):
                continue
            alias, origin = target.id, value.id
            if alias.startswith("_") or origin not in local:
                continue
            if _uses(alias, production, skip=path) == 0 and _uses(alias, tests) >= 1:
                try:
                    where = path.relative_to(REPO_ROOT).as_posix()
                except ValueError:
                    # A fixture tree lives outside the repository root.
                    where = path.as_posix()
                offenders.append((alias, origin, where))
    return offenders


def test_the_scanned_population_is_not_empty() -> None:
    """An empty population would make the assertion below vacuous."""
    production, _tests, _unread = _module_texts()

    assert len(production) > 500


def test_no_public_alias_exists_only_for_a_test() -> None:
    """The direction the gate exists for."""
    production, tests, unread = _module_texts()
    offenders = [f"{alias} = {origin} ({path})" for alias, origin, path in find_test_only_aliases(production, tests)]
    assert not offenders, (
        "these names are published only so a test can import them; point the test at "
        f"the private symbol production already calls and delete the alias: {offenders}"
    )
    assert not unread, (
        "this gate could not read these modules, so an alias declared in one "
        f"of them, or a test use that would have exposed one, is missing: {list(unread)}"
    )


def test_the_gate_catches_a_planted_alias(tmp_path: Path) -> None:
    """Detector teeth: the exact shape removed twenty-four times."""
    module = tmp_path / "subject.py"
    module.write_text("def _work() -> int:\n    return _work()\n\n\nwork = _work\n", encoding="utf-8")
    test = tmp_path / "test_subject.py"
    test.write_text("from .subject import work\n", encoding="utf-8")

    found = find_test_only_aliases(
        {module: module.read_text(encoding="utf-8")}, {test: test.read_text(encoding="utf-8")}
    )

    assert [(alias, origin) for alias, origin, _ in found] == [("work", "_work")]


def test_the_gate_catches_an_imported_target_alias(tmp_path: Path) -> None:
    """A different public spelling for an imported authority is still test-only."""
    module = tmp_path / "subject.py"
    module.write_text("from .other import WALLET_URL\n\nPUBLIC_URL = WALLET_URL\n", encoding="utf-8")
    test = tmp_path / "test_subject.py"
    test.write_text("from .subject import PUBLIC_URL\n", encoding="utf-8")

    assert [
        (alias, origin)
        for alias, origin, _ in find_test_only_aliases(
            {module: module.read_text(encoding="utf-8")},
            {test: test.read_text(encoding="utf-8")},
        )
    ] == [("PUBLIC_URL", "WALLET_URL")]


def test_an_alias_production_still_uses_is_not_an_offender(tmp_path: Path) -> None:
    """A genuine second name in live use must be left alone."""
    module = tmp_path / "subject.py"
    module.write_text("def _work() -> int:\n    return 1\n\n\nwork = _work\n", encoding="utf-8")
    caller = tmp_path / "caller.py"
    caller.write_text("from .subject import work\n\nVALUE = work()\n", encoding="utf-8")
    test = tmp_path / "test_subject.py"
    test.write_text("from .subject import work\n", encoding="utf-8")
    production = {p: p.read_text(encoding="utf-8") for p in (module, caller)}

    assert find_test_only_aliases(production, {test: test.read_text(encoding="utf-8")}) == []
