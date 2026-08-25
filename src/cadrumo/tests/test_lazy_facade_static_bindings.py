"""A lazily-exposed facade name must also be bound statically, or it types as ``object``.

Several package facades resolve their public surface through a module-level
``__getattr__`` keyed by a name-to-submodule map. The mechanism is deliberate:
the ledger facade re-exports 185 names across 20 submodules, and importing it
eagerly pulled the whole transitive graph for whichever single symbol a CLI
process actually wanted.

PEP 562 resolution is invisible to a type checker. It reads ``__getattr__``'s
own return annotation -- ``object`` -- so every symbol reached that way degrades
to ``object`` at every consumer: annotations built from it are rejected as type
forms, functions become non-callable, and attribute reads on results resolve to
nothing. The convention that repairs it is a ``TYPE_CHECKING`` block importing
the same names from the same submodules; it never executes, so it costs no
import time and cannot reintroduce the cycle the laziness broke.

Nothing enforced that the two lists agreed. They drifted twice: the ``llm``
facade's interchange DTOs, and then all ten ``_batch_ingest`` names, which
landed in the map and in ``__all__`` but not in the static block -- silently
erasing the batch CLI's entire type surface. The failure is quiet by
construction, because the runtime path is completely correct.

Structural on purpose: an import-time assertion would prove only that the names
resolve, which they already did.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path("src/cadrumo")


def _lazy_export_map(tree: ast.Module) -> dict[str, str]:
    """Return the ``{name: submodule}`` map a lazy facade dispatches on.

    Recognised structurally -- a dict literal whose keys and values are all
    plain strings and whose values name relative submodules -- rather than by a
    pinned variable name, so a facade that calls its map something else is
    still covered.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict) or not node.keys:
            continue
        pairs: dict[str, str] = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                break
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                break
            if not value.value.startswith("."):
                break
            pairs[key.value] = value.value
        else:
            if pairs:
                return pairs
    return {}


def _static_bindings(tree: ast.Module) -> set[str]:
    """Return every name imported inside an ``if TYPE_CHECKING:`` block."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.ImportFrom):
                bound.update(alias.asname or alias.name for alias in sub.names)
    return bound


def _lazy_facades() -> list[tuple[Path, dict[str, str], set[str]]]:
    """Return every package facade that dispatches through ``__getattr__``."""
    facades: list[tuple[Path, dict[str, str], set[str]]] = []
    for path in scan_directory(_SRC, pattern="__init__.py", recursive=True):
        source = path.read_text(encoding="utf-8")
        if "__getattr__" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        mapping = _lazy_export_map(tree)
        if mapping:
            facades.append((path, mapping, _static_bindings(tree)))
    return facades


def test_every_lazily_exposed_name_is_also_bound_for_the_type_checker() -> None:
    """The gate: a name in the dispatch map must appear in the TYPE_CHECKING block.

    Mutation that must trip this: delete any line from a facade's
    ``TYPE_CHECKING`` import block while leaving its dispatch-map entry.
    """
    facades = _lazy_facades()
    assert facades, "no lazy facade was found; this gate would pass vacuously"

    unbound = {
        path.as_posix(): sorted(set(mapping) - static) for path, mapping, static in facades if set(mapping) - static
    }

    assert unbound == {}, (
        "these names resolve through __getattr__ but have no TYPE_CHECKING binding, so every "
        "consumer sees them as `object` while the runtime stays correct:\n"
        + "\n".join(f"  {path}: {', '.join(names)}" for path, names in sorted(unbound.items()))
    )


def test_a_static_binding_names_the_submodule_the_map_dispatches_to() -> None:
    """Bound the rule above: the two lists must agree on the OWNER, not merely on the name.

    Without this, a binding importing the right name from the wrong submodule
    satisfies the membership check while handing the type checker a different
    symbol than the one the runtime resolves -- which is worse than no binding,
    because it type-checks.
    """
    divergent: list[str] = []
    for path, mapping, _static in _lazy_facades():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.ImportFrom):
                    continue
                declared = "." * sub.level + (sub.module or "")
                for alias in sub.names:
                    name = alias.asname or alias.name
                    expected = mapping.get(name)
                    if expected is not None and expected != declared:
                        divergent.append(
                            f"{path.as_posix()}: {name} maps to {expected} but is imported from {declared}"
                        )

    assert divergent == [], (
        "a static binding disagrees with the dispatch map about which submodule owns the name:\n" + "\n".join(divergent)
    )
