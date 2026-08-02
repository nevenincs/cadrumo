"""``_not_found`` may only be imported after its base class is bound.

``_not_found.py`` does ``from . import CoreError`` at module level — a facade
import that resolves only because ``errors/__init__`` defines ``CoreError``
BEFORE it imports ``_not_found``. Nothing states that ordering is load-bearing,
so moving the import above the class definition would make
``import cadrumo.core.errors`` fail outright for the whole process.

This is the same order-dependent shape as the settings-path facade imports,
with one difference that decides the remedy: ``CoreError`` has no owning
submodule to import from instead. It is defined in ``errors/__init__`` itself,
and relocating it to a leaf would move ``CadrumoError.__init_subclass__`` —
which drives the deferred-bind queue the lazy-import policy gate classifies as
``ERROR_REGISTRY_BOOTSTRAP``, "a protected core-authority boundary". Pinning
the ordering removes the silent-breakage risk without disturbing that.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ERRORS_DIR = Path(__file__).resolve().parent.parent

#: Names ``_not_found`` imports from the package facade at module scope.
_FACADE_NAMES_NEEDED_BY_NOT_FOUND = ("CoreError",)


def _module_tree(name: str) -> ast.Module:
    return ast.parse((_ERRORS_DIR / name).read_text(encoding="utf-8"))


def test_not_found_still_imports_its_base_from_the_facade() -> None:
    """Anti-tautology: the ordering guard is only meaningful while this holds.

    If ``_not_found`` ever stops importing from the facade — because
    ``CoreError`` gained an owning submodule, say — the ordering constraint
    below becomes vacuous, and this fails to say so rather than passing
    silently.
    """
    imported: set[str] = set()
    for node in ast.walk(_module_tree("_not_found.py")):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            imported.update(alias.name for alias in node.names)

    assert set(_FACADE_NAMES_NEEDED_BY_NOT_FOUND) <= imported, (
        "_not_found no longer imports these from the facade; if CoreError now has an "
        "owning submodule, import it from there and delete this ordering guard"
    )


def test_the_base_class_is_defined_before_not_found_is_imported() -> None:
    """The load-bearing ordering, asserted so a line move fails loudly.

    ``_not_found`` asks the half-built package for ``CoreError``; that resolves
    only while the class statement precedes the import.
    """
    tree = _module_tree("__init__.py")

    definitions = {node.name: node.lineno for node in tree.body if isinstance(node, ast.ClassDef)}
    not_found_import = next(
        node.lineno for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "_not_found"
    )

    for name in _FACADE_NAMES_NEEDED_BY_NOT_FOUND:
        assert name in definitions, f"{name} is no longer defined in errors/__init__"
        assert definitions[name] < not_found_import, (
            f"{name} is defined at line {definitions[name]} but _not_found is imported at "
            f"line {not_found_import}; _not_found asks the half-built package for {name}, "
            "so this ordering is load-bearing and the package will not import"
        )


def test_the_package_actually_imports() -> None:
    """The behaviour the ordering exists to protect, not just its shape."""
    from ... import errors as errors_package

    assert issubclass(errors_package.CoreNotFoundError, errors_package.CoreError)
    assert issubclass(errors_package.CoreNotFoundError, KeyError)
