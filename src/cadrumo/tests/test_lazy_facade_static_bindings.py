"""No shipped module resolves a name through ``__getattr__``, and the one that may stays honest.

Several package facades once resolved their public surface through a
module-level ``__getattr__`` keyed by a name-to-submodule map. The
consolidation campaign ruled that a contract is reached at its own defining
module and that a package namespace is inert, and the maps were removed one
package at a time. That retirement is now COMPLETE for shipped code, and the
first gate below is what keeps it complete.

This file used to police the retreating mechanism instead, and it had quietly
outlived its subject. Its non-vacuity guard asserted only that SOME lazy facade
was found, which stayed true after the last shipped one went because the test
package keeps a deliberate facade of its own. A gate written to protect shipped
code was passing on a test helper, and the docstring's own warning -- that when
the last map is gone the file has nothing to scan and should be deleted rather
than left passing over an empty population -- had come true without anyone
noticing. Asserting the ABSENCE is what cannot go vacuous.

PEP 562 resolution is invisible to a type checker. It reads ``__getattr__``'s
own return annotation -- ``object`` -- so every symbol reached that way degrades
to ``object`` at every consumer: annotations built from it are rejected as type
forms, functions become non-callable, and attribute reads on results resolve to
nothing. That is the substance of the ruling, not a style preference.

``cadrumo.tests`` keeps one facade, deliberately and permanently: two
domain-bearing fixtures whose import cost the rest of the facade must not pay,
each documented at the dispatch site as not a template. The second and third
gates below are the original checks, kept because the same drift is still
possible there: a name in the dispatch map with no ``TYPE_CHECKING`` binding
types as ``object`` at every consumer, and a binding that names the wrong
submodule is worse than none because it type-checks.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path("src/cadrumo")

#: The one package permitted a dispatch map, and the only one exempt below.
_PERMITTED_LAZY_PACKAGE = "src/cadrumo/tests/__init__.py"


def _module_getattr(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the module-level ``__getattr__`` definition, if the module has one."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "__getattr__":
            return node
    return None


def _shipped_modules() -> list[Path]:
    """Every module that ships, which is every module outside a test tree."""
    return [
        path
        for path in scan_directory(_SRC, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts and not path.name.startswith("test_")
    ]


def test_no_shipped_module_resolves_a_name_through_getattr() -> None:
    """The retirement is complete; this is what keeps it complete.

    Mutation that must trip this: add a module-level ``__getattr__`` to any
    module under ``src/cadrumo`` outside a test tree.
    """
    shipped = _shipped_modules()
    assert len(shipped) > 500, "the shipped-module scan found almost nothing; it would pass vacuously"

    offenders = [
        f"{path.as_posix()}:{node.lineno}"
        for path in shipped
        if (node := _module_getattr(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))) is not None
    ]
    assert offenders == [], (
        "these shipped modules resolve names through a module-level __getattr__, which types every "
        "consumer's view of them as `object` and reintroduces the lazy surface the consolidation "
        "retired:\n" + "\n".join(f"  {entry}" for entry in offenders)
    )


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


def _permitted_facade() -> tuple[Path, dict[str, str], set[str]]:
    """Return the one permitted lazy facade, refusing if it has stopped being one."""
    path = Path(_PERMITTED_LAZY_PACKAGE)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mapping = _lazy_export_map(tree)
    assert mapping, (
        f"{_PERMITTED_LAZY_PACKAGE} no longer dispatches through a map. If its last lazy name is "
        "gone, delete the exemption and the two checks below with it rather than leaving them "
        "passing over nothing."
    )
    return (path, mapping, _static_bindings(tree))


def test_every_lazily_exposed_name_is_also_bound_for_the_type_checker() -> None:
    """A name in the dispatch map must appear in the ``TYPE_CHECKING`` block.

    Mutation that must trip this: delete any line from the facade's
    ``TYPE_CHECKING`` import block while leaving its dispatch-map entry.
    """
    path, mapping, static = _permitted_facade()
    unbound = sorted(set(mapping) - static)
    assert unbound == [], (
        f"these names resolve through __getattr__ in {path.as_posix()} but have no TYPE_CHECKING "
        f"binding, so every consumer sees them as `object` while the runtime stays correct: "
        f"{', '.join(unbound)}"
    )


def test_a_static_binding_names_the_submodule_the_map_dispatches_to() -> None:
    """Bound the rule above: the two lists must agree on the OWNER, not merely on the name.

    Without this, a binding importing the right name from the wrong submodule
    satisfies the membership check while handing the type checker a different
    symbol than the one the runtime resolves -- which is worse than no binding,
    because it type-checks.
    """
    path, mapping, _static = _permitted_facade()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    divergent: list[str] = []
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
                    divergent.append(f"{name} maps to {expected} but is imported from {declared}")

    assert divergent == [], (
        f"a static binding in {path.as_posix()} disagrees with the dispatch map about which "
        "submodule owns the name:\n" + "\n".join(f"  {entry}" for entry in divergent)
    )
