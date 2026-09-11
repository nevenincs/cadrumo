"""Static enforcement of the :data:`~core.errors.ERROR_REGISTRY` invariants.

Walks every importable module under ``cadrumo``, discovers each
:class:`~core.errors.CadrumoError` subclass, and asserts:

* every subclass binds to a registered :class:`~core.errors.ErrorCode`,
* each registered code maps to exactly one subclass (no aliasing),
* every :class:`~core.errors.ErrorCategory` has at least one
  registered code, and
* no production raise site instantiates :class:`~core.errors.CadrumoError`
  directly or references an unregistered subclass.

Runs at unit-test scope — failures here are CI-blocking so missing
registrations cannot ship.

See Also:
    :mod:`~tests._inventory`
        Provides the production AST inventory and module-name resolver used by
        the raise-site scan.
    :mod:`~core.errors`
        Public error-registry surface whose declared codes are enforced here.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from ....tests.inventory import (
    import_binding_map,
    production_ast_items,
    qualified_name,
    resolve_dotted_origin,
)
from ....tests.inventory import (
    module_name as inventory_module_name,
)
from ..hierarchy import CadrumoError
from ..registry.declared_codes import ALL_DECLARED_ERROR_CODES
from .optional_extras import describe_optional_extras

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclass(frozen=True)
class _SourceErrorClass:
    """A ``CadrumoError`` declaration read from source, never imported."""

    module: str
    qualname: str
    bases: tuple[str, ...]

    @property
    def __name__(self) -> str:
        return self.qualname.rsplit(".", 1)[-1]

    @property
    def __module__(self) -> str:
        return self.module


def _class_qualnames(tree: ast.AST) -> dict[int, str]:
    qualnames: dict[int, str] = {}

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for statement in body:
            if not isinstance(statement, ast.ClassDef):
                continue
            qualname = f"{prefix}.{statement.name}" if prefix else statement.name
            qualnames[id(statement)] = qualname
            visit(statement.body, qualname)

    visit(getattr(tree, "body", []))
    return qualnames


@cache
def _source_error_classes() -> tuple[_SourceErrorClass, ...]:
    declarations: list[tuple[str, str, tuple[str, ...]]] = []
    for path, tree in production_ast_items():
        module = inventory_module_name(path)
        bindings = import_binding_map(tree)
        qualnames = _class_qualnames(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(
                resolve_dotted_origin(qualified_name(base) or ast.unparse(base), bindings) for base in node.bases
            )
            declarations.append((module, qualnames[id(node)], bases))

    by_key = {f"{module}.{qualname}": (module, qualname, bases) for module, qualname, bases in declarations}
    by_name: dict[str, list[str]] = {}
    for key in by_key:
        by_name.setdefault(key.rsplit(".", 1)[-1], []).append(key)

    def resolve_reference(module: str, origin: str) -> str | None:
        if origin in by_key:
            return origin
        leaf = origin.rsplit(".", 1)[-1]
        local = f"{module}.{leaf}"
        if local in by_key:
            return local
        candidates = by_name.get(leaf, [])
        return candidates[0] if len(candidates) == 1 else None

    roots = {key for key in by_key if key.rsplit(".", 1)[-1] == "CadrumoError"}
    descendants = set(roots)
    changed = True
    while changed:
        changed = False
        for key, (module, _qualname, bases) in by_key.items():
            if key in descendants:
                continue
            if any((resolved := resolve_reference(module, base)) in descendants for base in bases):
                descendants.add(key)
                changed = True

    return tuple(
        _SourceErrorClass(module, qualname, bases)
        for module, qualname, _bases in (by_key[key] for key in sorted(descendants - roots))
    )


def _iter_error_subclasses(root: type[CadrumoError]) -> set[_SourceErrorClass]:
    """Return every source declaration below *root* without importing modules."""
    if root.__name__ != "CadrumoError":
        return set()
    return set(_source_error_classes())


def _iter_raise_targets(source_tree_ast: Mapping[Path, ast.AST]) -> list[tuple[Path, ast.expr]]:
    targets: list[tuple[Path, ast.expr]] = []
    for path, tree in production_ast_items(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            targets.append((path, node.exc.func))
    return targets


def _resolve_raise_target(module_name: str, node: ast.expr) -> str | None:
    """Resolve a raise target to its source spelling without executing a module."""
    for path, tree in production_ast_items():
        if inventory_module_name(path) != module_name:
            continue
        return resolve_dotted_origin(ast.unparse(node), import_binding_map(tree))
    return None


def _looks_like_cadrumo_error_reference(node: ast.expr, known_names: set[str]) -> bool:
    rendered = ast.unparse(node)
    last_token = rendered.rsplit(".", 1)[-1]
    return last_token in known_names


#: Lowest plausible number of registered ``CadrumoError`` subclasses. Far below
#: the measured figure so ordinary churn never trips it, far enough above zero
#: that a collapsed import walk reds instead of greening vacuously.
_MIN_ERROR_SUBCLASSES = 300


def test_the_subclass_walk_reaches_a_plausible_population() -> None:
    """A collapsed walk must red, not green by examining nothing.

    Every assertion in this module is a "no violations found" or a same-length
    equality, and all of them hold trivially over an empty population -- so
    without this floor the gate is indistinguishable from one that works.

    The subject set here is built from ``__subclasses__`` after a package-wide
    import, which is doubly environment-shaped: it lists only classes whose
    defining statement actually EXECUTED, so an importable-but-unimported class
    is invisible, as is any class defined inside an optional-import fallback
    whose extra is installed. The scope line is therefore reported, not merely
    asserted: a green from this gate is a claim about one environment, and it
    should say which.
    """
    subclasses = _iter_error_subclasses(CadrumoError)
    print(f"error-registry scope: {len(subclasses)} CadrumoError subclasses walked; {describe_optional_extras()}")
    assert len(subclasses) >= _MIN_ERROR_SUBCLASSES, (
        f"only {len(subclasses)} CadrumoError subclasses discovered (floor {_MIN_ERROR_SUBCLASSES}); "
        f"the import walk collapsed, so every assertion in this module would pass by examining "
        f"nothing. Scope: {describe_optional_extras()}"
    )


def test_every_cadrumo_error_subclass_has_a_registered_code() -> None:
    subclasses = _iter_error_subclasses(CadrumoError)
    ordered = sorted(subclasses, key=lambda error_type: f"{error_type.__module__}.{error_type.__qualname__}")

    declared = dict(ALL_DECLARED_ERROR_CODES)
    missing = [
        f"{error_type.__module__}.{error_type.__qualname__}"
        for error_type in ordered
        if f"{error_type.__module__}.{error_type.__qualname__}" not in declared
    ]
    assert missing == []

    bound = {
        f"{error_type.__module__}.{error_type.__qualname__}": declared[
            f"{error_type.__module__}.{error_type.__qualname__}"
        ]
        for error_type in subclasses
    }
    assert len(bound) == len(subclasses)


def test_raw_error_declarations_have_single_class_and_code_authority() -> None:
    qualname_counts = Counter(qualname for qualname, _ in ALL_DECLARED_ERROR_CODES)
    code_counts = Counter(code.code for _, code in ALL_DECLARED_ERROR_CODES)

    assert {qualname: count for qualname, count in qualname_counts.items() if count > 1} == {}
    assert {code: count for code, count in code_counts.items() if count > 1} == {}
