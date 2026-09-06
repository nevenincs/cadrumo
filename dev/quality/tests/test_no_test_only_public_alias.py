"""Gate: no module publishes a name that exists only so a test can import it.

The shape is ``PUBLIC = _PRIVATE`` at module level, where the private symbol is
defined in the same module and carries the real implementation, production
calls the PRIVATE name, and the public alias is imported by nothing but tests.
It reads as published API and is not: the architecture rule bars alias and
re-export layers outright, and the alias also hides that the module's real
surface is the private one.

Twenty-four of these were removed across the shipped tree. Each removal was the
same edit -- point the test at the private name, which a test in the same
package may import, and delete the alias with its ``__all__`` entry.

Deliberately narrow, so the rule catches that shape and not its neighbours:

* the target must be defined in the SAME module, which excludes a re-export
  under a clearer name (``IVA_COMPENSATION_WALLET_URL = WALLET_URL``, whose
  target is imported) -- a different question about package vocabulary;
* the alias must have at least one TEST consumer, which excludes an export
  nothing reads at all, a published-surface decision rather than an alias;
* the alias must be dead in production, so a genuine second name in use is
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


def _module_texts() -> tuple[dict[Path, str], dict[Path, str]]:
    """Return (production, test) module sources, read once."""
    production: dict[Path, str] = {}
    tests: dict[Path, str] = {}
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        (tests if "tests" in path.parts else production)[path] = text
    return production, tests


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
            if alias.startswith("_") or not origin.startswith("_") or origin not in local:
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
    production, _ = _module_texts()
    assert len(production) > 500


def test_no_public_alias_exists_only_for_a_test() -> None:
    """The direction the gate exists for."""
    production, tests = _module_texts()
    offenders = [f"{alias} = {origin} ({path})" for alias, origin, path in find_test_only_aliases(production, tests)]
    assert not offenders, (
        "these names are published only so a test can import them; point the test at "
        f"the private symbol production already calls and delete the alias: {offenders}"
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


def test_a_reexport_under_a_clearer_name_is_not_an_offender(tmp_path: Path) -> None:
    """The target is imported, not defined here, so it is a vocabulary question."""
    module = tmp_path / "subject.py"
    module.write_text("from .other import WALLET_URL\n\nPUBLIC_URL = WALLET_URL\n", encoding="utf-8")
    test = tmp_path / "test_subject.py"
    test.write_text("from .subject import PUBLIC_URL\n", encoding="utf-8")

    assert (
        find_test_only_aliases({module: module.read_text(encoding="utf-8")}, {test: test.read_text(encoding="utf-8")})
        == []
    )


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
