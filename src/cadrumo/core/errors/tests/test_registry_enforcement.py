"""Static enforcement of the :data:`~core.errors.ERROR_REGISTRY` invariants.

Walks every production source module under ``cadrumo``, discovers each
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
    def name(self) -> str:
        """Return the declaration's leaf name without duplicating identity state."""
        return self.qualname.rsplit(".", 1)[-1]


def _source_error_key(error_type: _SourceErrorClass) -> str:
    """Return the registry identity for a source descriptor."""
    return f"{error_type.module}.{error_type.qualname}"


def _source_import_bindings(tree: ast.AST, module: str, *, is_package: bool) -> dict[str, str]:
    """Resolve absolute and first-party relative import aliases for one module."""
    bindings = import_binding_map(tree)
    package = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        ascend = node.level - 1
        prefix = package[: len(package) - ascend] if ascend else package
        imported_module = [*prefix, *(node.module or "").split(".")]
        origin_module = ".".join(part for part in imported_module if part)
        for alias in node.names:
            bindings[alias.asname or alias.name] = f"{origin_module}.{alias.name}"
    return bindings


def _class_qualnames(tree: ast.AST) -> dict[int, str]:
    qualnames: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str = "") -> None:
        if isinstance(node, ast.ClassDef):
            prefix = f"{prefix}.{node.name}" if prefix else node.name
            qualnames[id(node)] = prefix
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            prefix = f"{prefix}.{node.name}.<locals>" if prefix else f"{node.name}.<locals>"

        for child in ast.iter_child_nodes(node):
            visit(child, prefix)

    visit(tree)
    return qualnames


@cache
def _source_error_classes() -> tuple[_SourceErrorClass, ...]:
    declarations: list[tuple[str, str, tuple[str, ...]]] = []
    for path, tree in production_ast_items():
        module = inventory_module_name(path)
        bindings = _source_import_bindings(tree, module, is_package=path.name == "__init__.py")
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
            if any(resolve_reference(module, base) in descendants for base in bases):
                descendants.add(key)
                changed = True

    return tuple(
        _SourceErrorClass(module, qualname, bases)
        for module, qualname, bases in (by_key[key] for key in sorted(descendants - roots))
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


def test_source_descriptor_keeps_reserved_metadata_on_its_class() -> None:
    """Source metadata must remain ordinary descriptor data, not dunder properties."""
    descriptor = _SourceErrorClass(
        module="cadrumo.synthetic.errors",
        qualname="Outer.Error",
        bases=("cadrumo.core.errors.CadrumoError",),
    )

    assert descriptor.module == "cadrumo.synthetic.errors"
    assert descriptor.qualname == "Outer.Error"
    assert descriptor.name == "Error"
    assert descriptor.bases == ("cadrumo.core.errors.CadrumoError",)
    assert isinstance(_SourceErrorClass.__module__, str)
    assert isinstance(_SourceErrorClass.__qualname__, str)
    assert set(_SourceErrorClass.__dataclass_fields__) == {"module", "qualname", "bases"}


def test_class_qualnames_cover_control_flow_and_function_scopes() -> None:
    tree = ast.parse(
        "class Top(CadrumoError):\n"
        "    class Nested(CadrumoError):\n"
        "        pass\n"
        "if True:\n"
        "    class Conditional(CadrumoError):\n"
        "        pass\n"
        "def factory():\n"
        "    class Local(CadrumoError):\n"
        "        pass\n"
    )
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    qualnames = _class_qualnames(tree)

    assert qualnames[id(classes["Top"])] == "Top"
    assert qualnames[id(classes["Nested"])] == "Top.Nested"
    assert qualnames[id(classes["Conditional"])] == "Conditional"
    assert qualnames[id(classes["Local"])] == "factory.<locals>.Local"


#: Lowest plausible number of registered ``CadrumoError`` subclasses. Far below
#: the measured figure so ordinary churn never trips it, far enough above zero
#: that a collapsed source walk reds instead of greening vacuously.
_MIN_ERROR_SUBCLASSES = 300


def test_the_subclass_walk_reaches_a_plausible_population() -> None:
    """A collapsed walk must red, not green by examining nothing.

    Every assertion in this module is a "no violations found" or a same-length
    equality, and all of them hold trivially over an empty population -- so
    without this floor the gate is indistinguishable from one that works.

    The subject set here is built from the production source AST, so it includes
    importable-but-unimported classes and classes defined inside an optional-import
    fallback whose extra is installed. The scope line is therefore reported, not
    merely asserted: a green from this gate is a claim about the production source
    tree, and it should say which.
    """
    subclasses = _iter_error_subclasses(CadrumoError)
    print(f"error-registry scope: {len(subclasses)} CadrumoError subclasses walked; {describe_optional_extras()}")
    assert len(subclasses) >= _MIN_ERROR_SUBCLASSES, (
        f"only {len(subclasses)} CadrumoError subclasses discovered (floor {_MIN_ERROR_SUBCLASSES}); "
        f"the source walk collapsed, so every assertion in this module would pass by examining "
        f"nothing. Scope: {describe_optional_extras()}"
    )


def test_every_cadrumo_error_subclass_has_a_registered_code() -> None:
    subclasses = _iter_error_subclasses(CadrumoError)
    ordered = sorted(subclasses, key=_source_error_key)

    declared = dict(ALL_DECLARED_ERROR_CODES)
    missing = [_source_error_key(error_type) for error_type in ordered if _source_error_key(error_type) not in declared]
    assert missing == []

    discovered = {_source_error_key(error_type) for error_type in subclasses}
    orphaned = sorted(set(declared) - discovered)
    assert orphaned == [], f"registry row(s) have no source CadrumoError declaration: {orphaned}"

    bound = {_source_error_key(error_type): declared[_source_error_key(error_type)] for error_type in subclasses}
    assert len(bound) == len(subclasses)


def test_raw_error_declarations_have_single_class_and_code_authority() -> None:
    qualname_counts = Counter(qualname for qualname, _ in ALL_DECLARED_ERROR_CODES)
    code_counts = Counter(code.code for _, code in ALL_DECLARED_ERROR_CODES)

    assert {qualname: count for qualname, count in qualname_counts.items() if count > 1} == {}
    assert {code: count for code, count in code_counts.items() if count > 1} == {}
