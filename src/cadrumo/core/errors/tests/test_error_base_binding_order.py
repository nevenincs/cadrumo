"""No module in the errors package may reach its own package namespace.

``not_found.py`` used to do ``from . import CoreError`` — a facade import that
resolved only because ``errors/__init__`` defined ``CoreError`` BEFORE it
imported ``not_found``. Nothing stated that ordering was load-bearing, so
moving the import above the class definition would have made
``import cadrumo.core.errors`` fail outright for the whole process.

That was pinned rather than fixed, because the remedy looked unavailable:
``CoreError`` had no owning submodule to import from instead. It was defined in
``errors/__init__`` itself, and relocating it meant moving
``CadrumoError.__init_subclass__``, which drives the deferred-bind queue.

The hierarchy now lives in :mod:`cadrumo.core.errors.hierarchy` and the
namespace is inert, so the remedy was available after all. This asserts the
stronger property that replaces the pin: no module here imports from the
package namespace, which makes the ordering question unanswerable rather than
merely answered correctly. A facade import cannot be mis-ordered if there is no
facade to import from.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ERRORS_DIR = Path(__file__).resolve().parent.parent


def _namespace_imports(path: Path) -> list[str]:
    """Names the module imports from its own package namespace, if any."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            found.extend(alias.name for alias in node.names)
    return found


def test_no_module_imports_from_the_errors_namespace() -> None:
    """The namespace exports nothing, so reaching for it can only be a mistake."""
    offenders = {
        path.name: names
        for path in sorted(_ERRORS_DIR.glob("*.py"))
        if path.name != "__init__.py" and (names := _namespace_imports(path))
    }
    assert not offenders, (
        "these modules import from the errors package namespace, which is inert. "
        f"Import from the module that defines the name instead: {offenders}"
    )


def test_the_namespace_offers_nothing_to_import() -> None:
    """Anti-tautology: the check above is vacuous if the namespace still exports."""
    from ... import errors

    assert errors.__all__ == (), (
        "the errors namespace exports names again; the check above stops being a "
        "guard and becomes a description of a facade nobody is using yet"
    )


def test_the_hierarchy_owns_the_base_classes() -> None:
    """The relocation that made the guard possible must not be undone."""
    from ..hierarchy import CadrumoError, CoreError
    from ..not_found import CoreNotFoundError

    assert issubclass(CoreError, CadrumoError)
    assert issubclass(CoreNotFoundError, CoreError)
    assert CoreError.__module__ == "cadrumo.core.errors.hierarchy"
