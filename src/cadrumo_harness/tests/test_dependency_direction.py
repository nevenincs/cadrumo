"""Directional gate: ``cadrumo-harness`` consumes ``cadrumo``, never the reverse.

This package's own project file states the contract - "cadrumo-harness is a
consumer of the cadrumo CLI/library, never the reverse ... cadrumo itself
carries no dependency on this package" - and until this module landed, nothing
enforced it. A repair that repointed four harness-delivery surfaces at this
package satisfied every gate in the tree while closing a dependency cycle
between the two distributions, because the statement lived only in prose.

Two ends, gated separately, because an edge broken at one end reads clean from
the other:

- **The import end.** No module in the ``cadrumo`` source tree may name
  ``cadrumo_harness`` in an import, static or dynamic. Gated at HARD ZERO with
  no allowlist: there is no reading under which the core library reaches up into
  its own consumer. Docstring cross-references are not imports and are not
  scanned - only ``import``/``from`` statements and ``import_module`` arguments.
- **The metadata end.** ``cadrumo``'s published metadata - ``[project.dependencies]``
  and every ``[project.optional-dependencies]`` extra - may not resolve
  ``cadrumo-harness``. The PEP 735 ``[dependency-groups]`` table is deliberately
  out of scope: it is never written into wheel or sdist metadata, so a dev-group
  entry (which this repository does carry, for its own tooling and for this test
  suite) creates no edge between the two published distributions.

The converse edge is asserted present rather than assumed, so a future removal
of this package's declared reliance on ``cadrumo`` cannot leave the gate passing
vacuously over an unrelated pair.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_UTF_8 = "utf-8"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORE_SOURCE_ROOT = _REPO_ROOT / "src" / "cadrumo"

_HARNESS_MODULE = "cadrumo_harness"
_HARNESS_DISTRIBUTION = "cadrumo-harness"
_CORE_DISTRIBUTION = "cadrumo"


def _names_the_harness(module: str | None) -> bool:
    """Return whether a dotted module string is ``cadrumo_harness`` or below it."""
    return module is not None and (module == _HARNESS_MODULE or module.startswith(f"{_HARNESS_MODULE}."))


def _harness_imports(tree: ast.Module) -> list[str]:
    """Return every dotted target in this module that reaches into the harness.

    Covers the three shapes an import can take: ``import cadrumo_harness.x``,
    ``from cadrumo_harness.x import y``, and the dynamic
    ``importlib.import_module("cadrumo_harness.x")`` cycle-break, whose string
    argument no import-statement walk would see.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names if _names_the_harness(alias.name))
        elif isinstance(node, ast.ImportFrom):
            # A relative import (level > 0) can never leave the cadrumo package.
            if node.level == 0 and _names_the_harness(node.module):
                found.append(node.module or "")
        elif isinstance(node, ast.Call):
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
            if name != "import_module":
                continue
            found.extend(
                argument.value
                for argument in node.args
                if isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and _names_the_harness(argument.value)
            )
    return found


def _core_source_files() -> list[Path]:
    """Return every Python file in the ``cadrumo`` distribution's source tree."""
    return sorted(path for path in _CORE_SOURCE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _requirement_distribution(requirement: str) -> str:
    """Return the normalised distribution name a requirement string resolves."""
    name = requirement.strip()
    for separator in ("[", "@", "=", ">", "<", "!", "~", ";", " "):
        name = name.split(separator, maxsplit=1)[0]
    return name.strip().replace("_", "-").lower()


def test_no_module_in_the_core_tree_imports_the_harness() -> None:
    """The ``cadrumo`` source tree reaches the harness nowhere, by any import shape."""
    source_files = _core_source_files()
    assert source_files, f"no Python source found under {_CORE_SOURCE_ROOT}; the scan subject is wrong"

    offenders: dict[str, list[str]] = {}
    for path in source_files:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        reaches = _harness_imports(tree)
        if reaches:
            offenders[path.relative_to(_REPO_ROOT).as_posix()] = sorted(reaches)

    assert offenders == {}, (
        f"the cadrumo distribution imports its own consumer, closing a dependency cycle: {offenders}. "
        f"Move the importing surface into {_HARNESS_DISTRIBUTION} instead of depending upwards."
    )
