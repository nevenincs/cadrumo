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
import builtins
import importlib
import inspect
import pkgutil
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import pytest

from ....tests import module_name, production_ast_items, repo_relative
from ..error_codes import ERROR_REGISTRY, ErrorCategory, get_registered_error_code
from ..hierarchy import CadrumoError
from ..registry.declared_codes import _ALL_DECLARED_ERROR_CODES
from .optional_extras import describe_optional_extras

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _import_all_cadrumo_modules() -> None:
    from .. import __path__ as errors_path

    cadrumo_path = [str(Path(errors_path[0]).parent.parent)]
    for info in pkgutil.walk_packages(cadrumo_path, prefix="cadrumo."):
        name = info.name
        if ".tests." in name or ".test_" in name or "._test_" in name:
            continue
        importlib.import_module(name)


def _iter_error_subclasses(root: type[CadrumoError]) -> set[type[CadrumoError]]:
    discovered: set[type[CadrumoError]] = set()
    for subclass in root.__subclasses__():
        if ".tests." in subclass.__module__ or ".test_" in subclass.__module__:
            continue
        discovered.add(subclass)
        discovered.update(_iter_error_subclasses(subclass))
    return discovered


def _iter_raise_targets(source_tree_ast: Mapping[Path, ast.AST]) -> list[tuple[Path, ast.expr]]:
    targets: list[tuple[Path, ast.expr]] = []
    for path, tree in production_ast_items(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            targets.append((path, node.exc.func))
    return targets


def _resolve_raise_target(module_name: str, node: ast.expr) -> object | None:
    module = importlib.import_module(module_name)
    namespace = module.__dict__

    def _resolve(current: ast.expr) -> object | None:
        if isinstance(current, ast.Name):
            if current.id in namespace:
                return namespace[current.id]
            return getattr(builtins, current.id, None)
        if isinstance(current, ast.Attribute):
            parent = _resolve(current.value)
            if parent is None:
                return None
            return getattr(parent, current.attr, None)
        return None

    return _resolve(node)


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
    _import_all_cadrumo_modules()
    subclasses = _iter_error_subclasses(CadrumoError)
    print(f"error-registry scope: {len(subclasses)} CadrumoError subclasses walked; {describe_optional_extras()}")
    assert len(subclasses) >= _MIN_ERROR_SUBCLASSES, (
        f"only {len(subclasses)} CadrumoError subclasses discovered (floor {_MIN_ERROR_SUBCLASSES}); "
        f"the import walk collapsed, so every assertion in this module would pass by examining "
        f"nothing. Scope: {describe_optional_extras()}"
    )


def test_every_cadrumo_error_subclass_has_a_registered_code() -> None:
    _import_all_cadrumo_modules()
    subclasses = _iter_error_subclasses(CadrumoError)
    ordered = sorted(subclasses, key=lambda error_type: f"{error_type.__module__}.{error_type.__name__}")

    missing = [
        f"{error_type.__module__}.{error_type.__name__}" for error_type in ordered if not hasattr(error_type, "code")
    ]
    assert missing == []

    bound = {error_type: get_registered_error_code(error_type) for error_type in subclasses}
    assert len(bound) == len(subclasses)


def test_raw_error_declarations_have_single_class_and_code_authority() -> None:
    qualname_counts = Counter(qualname for qualname, _ in _ALL_DECLARED_ERROR_CODES)
    code_counts = Counter(code.code for _, code in _ALL_DECLARED_ERROR_CODES)

    assert {qualname: count for qualname, count in qualname_counts.items() if count > 1} == {}
    assert {code: count for code, count in code_counts.items() if count > 1} == {}


def test_modelo_calculate_input_errors_have_registered_codes() -> None:
    """The public calculate CLI imports this module before handling overrides."""

    module = importlib.import_module("cadrumo.application.modelo._calculate_input")
    concrete_errors = [
        error_type
        for _, error_type in inspect.getmembers(module, inspect.isclass)
        if error_type.__module__ == module.__name__ and issubclass(error_type, CadrumoError)
    ]

    assert concrete_errors
    missing: list[str] = []
    for error_type in concrete_errors:
        code = get_registered_error_code(error_type)
        if code.code not in ERROR_REGISTRY:
            missing.append(f"{error_type.__module__}.{error_type.__name__}")
    assert missing == []


def test_every_registered_code_maps_to_exactly_one_error_subclass() -> None:
    _import_all_cadrumo_modules()
    subclasses = _iter_error_subclasses(CadrumoError)
    reverse: dict[str, list[str]] = {}
    for error_type in subclasses:
        code = get_registered_error_code(error_type)
        reverse.setdefault(code.code, []).append(f"{error_type.__module__}.{error_type.__name__}")

    duplicates = {code: owners for code, owners in reverse.items() if len(owners) != 1}
    assert duplicates == {}
    assert set(reverse) == set(ERROR_REGISTRY)


def test_every_category_has_at_least_one_registered_error_code() -> None:
    _import_all_cadrumo_modules()
    categories = {code.category for code in ERROR_REGISTRY.values()}
    assert categories == set(ErrorCategory)


def test_raise_sites_do_not_use_bare_cadrumo_error_and_reference_registered_subclasses(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    _import_all_cadrumo_modules()
    subclasses = _iter_error_subclasses(CadrumoError)
    index = {error_type.__name__: error_type for error_type in subclasses}
    known_names = set(index) | {"CadrumoError"}

    direct_base_raises: list[str] = []
    unresolved_targets: list[str] = []
    for path, target in _iter_raise_targets(source_tree_ast):
        resolved = _resolve_raise_target(module_name(path), target)
        rendered = ast.unparse(target)
        last_token = rendered.rsplit(".", 1)[-1]
        if resolved is None and last_token in index:
            resolved = index[last_token]
        if resolved is CadrumoError:
            direct_base_raises.append(f"{repo_relative(path)}:{rendered}")
            continue
        if isinstance(resolved, type) and issubclass(resolved, CadrumoError):
            error_type = index.get(resolved.__name__, resolved)
            code = get_registered_error_code(error_type)
            if code.code not in ERROR_REGISTRY:
                unresolved_targets.append(f"{repo_relative(path)}:{rendered}")
            continue
        if resolved is None and _looks_like_cadrumo_error_reference(target, known_names):
            unresolved_targets.append(f"{repo_relative(path)}:{rendered}")

    assert direct_base_raises == []
    assert unresolved_targets == []
