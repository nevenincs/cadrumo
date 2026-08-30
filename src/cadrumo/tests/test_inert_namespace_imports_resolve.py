"""A name may not be imported from a namespace that exports nothing.

Retiring a package's export map makes its namespace inert. Every consumer that
reached a contract through the namespace has to move to the module that defines
it, and one that does not fails with ``ImportError`` -- not when the contract is
used, but the moment anything imports the consumer at all.

That is a loud failure and a late one. It has landed three times in this
codebase: a censo parser, a portals service, and a secret store whose namespace
went inert while production and the storage export map still reached through it,
taking fifteen hundred test modules down at collection. In each case the
retirement was correct and the sweep of consumers was incomplete, and nothing
said so until something imported the wrong module.

This is the check that says so. It is deliberately narrow:

* Only NAMESPACES THAT EXPORT NOTHING are judged -- an empty ``__all__``, no
  ``__getattr__``, no re-exports. A package still carrying a lazy export map is
  serving names on demand and is not this gate's business; treating one as
  empty produced six thousand false positives on the first attempt.
* A submodule is not a missing name. ``from .pkg import sibling`` where
  ``pkg/sibling.py`` exists resolves through the filesystem and is fine.
* Dunders are module attributes every module has, and are not exports.

The failure this prevents is not subtle once seen, which is the point: it is
invisible until the import runs, and the import may live behind a branch that
only a particular operator takes.
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
