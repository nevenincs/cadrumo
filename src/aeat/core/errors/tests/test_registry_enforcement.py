"""Static enforcement of the :data:`aeat.core.errors.ERROR_REGISTRY` invariants.

Walks every importable module under :mod:`aeat`, discovers each
:class:`aeat.core.errors.AeatError` subclass, and asserts:

* every subclass binds to a registered :class:`aeat.core.errors.ErrorCode`,
* each registered code maps to exactly one subclass (no aliasing),
* every :class:`aeat.core.errors.ErrorCategory` has at least one
  registered code, and
* no production raise site instantiates :class:`aeat.core.errors.AeatError`
  directly or references an unregistered subclass.

Runs at unit-test scope — failures here are CI-blocking so missing
registrations cannot ship.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import pkgutil
from pathlib import Path

import pytest

from .. import ERROR_REGISTRY, AeatError, ErrorCategory, get_registered_error_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _import_all_aeat_modules() -> None:
    from .. import __path__ as errors_path

    aeat_path = [str(Path(errors_path[0]).parent.parent)]
    for info in pkgutil.walk_packages(aeat_path, prefix="aeat."):
        name = info.name
        if ".tests." in name or ".test_" in name or "._test_" in name:
            continue
        importlib.import_module(name)


def _iter_error_subclasses(root: type[AeatError]) -> set[type[AeatError]]:
    discovered: set[type[AeatError]] = set()
    for subclass in root.__subclasses__():
        if ".tests." in subclass.__module__ or ".test_" in subclass.__module__:
            continue
        discovered.add(subclass)
        discovered.update(_iter_error_subclasses(subclass))
    return discovered


def _iter_raise_targets() -> list[tuple[Path, ast.expr]]:
    targets: list[tuple[Path, ast.expr]] = []
    for path in Path("src/aeat").rglob("*.py"):
        if path.name.startswith("test_") or path.name.startswith("_test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            targets.append((path, node.exc.func))
    return targets


def _module_name_for_path(path: Path) -> str:
    relative = path.with_suffix("").relative_to(Path("src"))
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


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


def _looks_like_aeat_error_reference(node: ast.expr, known_names: set[str]) -> bool:
    rendered = ast.unparse(node)
    last_token = rendered.rsplit(".", 1)[-1]
    return last_token in known_names


def test_every_aeat_error_subclass_has_a_registered_code() -> None:
    _import_all_aeat_modules()
    subclasses = _iter_error_subclasses(AeatError)
    ordered = sorted(subclasses, key=lambda error_type: f"{error_type.__module__}.{error_type.__name__}")

    missing = [
        f"{error_type.__module__}.{error_type.__name__}" for error_type in ordered if not hasattr(error_type, "code")
    ]
    assert missing == []

    bound = {error_type: get_registered_error_code(error_type) for error_type in subclasses}
    assert len(bound) == len(subclasses)


def test_every_registered_code_maps_to_exactly_one_error_subclass() -> None:
    _import_all_aeat_modules()
    subclasses = _iter_error_subclasses(AeatError)
    reverse: dict[str, list[str]] = {}
    for error_type in subclasses:
        code = get_registered_error_code(error_type)
        reverse.setdefault(code.code, []).append(f"{error_type.__module__}.{error_type.__name__}")

    duplicates = {code: owners for code, owners in reverse.items() if len(owners) != 1}
    assert duplicates == {}
    assert set(reverse) == set(ERROR_REGISTRY)


def test_every_category_has_at_least_one_registered_error_code() -> None:
    _import_all_aeat_modules()
    categories = {code.category for code in ERROR_REGISTRY.values()}
    assert categories == set(ErrorCategory)


def test_raise_sites_do_not_use_bare_aeat_error_and_reference_registered_subclasses() -> None:
    _import_all_aeat_modules()
    subclasses = _iter_error_subclasses(AeatError)
    index = {error_type.__name__: error_type for error_type in subclasses}
    known_names = set(index) | {"AeatError"}

    direct_base_raises: list[str] = []
    unresolved_targets: list[str] = []
    for path, target in _iter_raise_targets():
        module_name = _module_name_for_path(path)
        resolved = _resolve_raise_target(module_name, target)
        rendered = ast.unparse(target)
        last_token = rendered.rsplit(".", 1)[-1]
        if resolved is None and last_token in index:
            resolved = index[last_token]
        if resolved is AeatError:
            direct_base_raises.append(f"{path}:{rendered}")
            continue
        if isinstance(resolved, type) and issubclass(resolved, AeatError):
            error_type = index.get(resolved.__name__, resolved)
            code = get_registered_error_code(error_type)
            if code.code not in ERROR_REGISTRY:
                unresolved_targets.append(f"{path}:{rendered}")
            continue
        if resolved is None and _looks_like_aeat_error_reference(target, known_names):
            unresolved_targets.append(f"{path}:{rendered}")

    assert direct_base_raises == []
    assert unresolved_targets == []
