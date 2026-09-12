"""A name may not be imported from a namespace that exports nothing.

Such an import fails as soon as its consumer loads, even when the named
submodule itself exists. This check is deliberately narrow:

* Only NAMESPACES THAT EXPORT NOTHING are judged -- an empty ``__all__``, no
  ``__getattr__``, no re-exports.
* A submodule is not a missing name. ``from .pkg import sibling`` where
  ``pkg/sibling.py`` exists resolves through the filesystem and is fine.
* Dunders are module attributes every module has, and are not exports.

The import may live behind a branch that only a particular operator takes, so
static reachability is the useful signal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent
_ROOT = _SRC.parent


def _exports_nothing(init: Path) -> bool:
    """Whether this namespace serves no names at all."""
    try:
        tree = ast.parse(init.read_text(encoding="utf-8"))
    except SyntaxError:  # a peer's mid-edit file is not this gate's finding
        return False
    empty_all = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            return False  # defines something, or carries a __getattr__ hook
        if isinstance(node, ast.ImportFrom) and node.level >= 1:
            return False  # re-exports
        if isinstance(node, ast.Assign | ast.AnnAssign):
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                empty_all = isinstance(value, ast.Tuple | ast.List) and not value.elts
    return empty_all


def _unresolvable_imports() -> list[str]:
    findings: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        package = path.relative_to(_ROOT).with_suffix("").parts[:-1]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            keep = len(package) - (node.level - 1)
            if keep < 0:
                continue
            target = _ROOT / "/".join(package[:keep]) / (node.module.replace(".", "/") if node.module else "")
            init = target / "__init__.py"
            if not init.exists() or init == path or target.with_suffix(".py").exists():
                continue
            if not _exports_nothing(init):
                continue
            for alias in node.names:
                if alias.name.startswith("__"):
                    continue
                if (target / f"{alias.name}.py").exists() or (target / alias.name / "__init__.py").exists():
                    continue
                relative = path.relative_to(_ROOT).as_posix()
                package_name = target.relative_to(_ROOT).as_posix()
                findings.append(f"{relative}:{node.lineno} imports {alias.name!r} from {package_name}")
    return findings


def test_no_name_is_imported_from_a_namespace_that_exports_nothing() -> None:
    """A retirement that missed a consumer must fail here, not at collection."""
    findings = _unresolvable_imports()
    assert not findings, (
        "these imports name a package whose namespace is inert, so they raise "
        "ImportError the moment the importing module is loaded. Point each at "
        f"the module that defines the name: {findings}"
    )
