"""The native manager's strings come from the catalogues without the desktop shell's declarations."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..manager_chrome import MANAGER_CHROME_KEYS, manager_chrome_strings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = Path(__file__).resolve().parents[1]


def _sibling_imports(module: str) -> set[str]:
    """Return the ``dev.locales`` modules one module imports at load, by relative or absolute name."""
    tree = ast.parse((_LOCALES / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    # Only module-level statements run on import; a function-local import is deferred.
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module is not None:
                found.add(node.module.split(".")[0])
            elif node.level == 1:
                found.update(alias.name for alias in node.names)
            elif node.level == 0 and node.module is not None and node.module.startswith("dev.locales."):
                found.add(node.module.split(".")[2])
        elif isinstance(node, ast.Import):
            found.update(alias.name.split(".")[2] for alias in node.names if alias.name.startswith("dev.locales."))
    return {name for name in found if (_LOCALES / f"{name}.py").is_file()}


def test_manager_strings_do_not_load_the_desktop_key_declarations() -> None:
    """The native build reruns the projection whenever a module it imports changes; keep it to the catalogues."""
    pending, loaded = ["manager_chrome"], set[str]()
    while pending:
        module = pending.pop()
        if module not in loaded:
            loaded.add(module)
            pending.extend(_sibling_imports(module))

    assert "chrome_projection" in loaded
    assert not {name for name in loaded if name.startswith("desktop_")}, sorted(loaded)


def test_every_manager_key_is_projected_in_every_output_language() -> None:
    strings = manager_chrome_strings()

    assert strings
    assert all(set(values) == MANAGER_CHROME_KEYS for values in strings.values())
