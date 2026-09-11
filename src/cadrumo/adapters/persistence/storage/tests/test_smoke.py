"""Smoke tests for the storage subpackage's public surface.

Verifies that :mod:`cadrumo.adapters.persistence.storage` is importable,
exposes the expected error hierarchy, and that every name in
``__all__`` resolves on the package root.
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

from .....core import logging
from .....core.errors.hierarchy import CadrumoError
from ... import storage as storage_package
from ..errors import RepositoryError, StorageError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _storage_initializer() -> ast.Module:
    """Parse the storage initializer without consuming its package facade."""
    path = Path(__file__).resolve().parents[1] / "__init__.py"
    return ast.parse(path.read_text(encoding="utf-8"))


def _storage_exports() -> tuple[str, ...]:
    assignment = next(
        node
        for node in _storage_initializer().body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__"
    )
    value = assignment.value
    if not isinstance(value, (ast.List, ast.Tuple)) or not all(
        isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts
    ):
        raise AssertionError("storage package __all__ must be a literal string sequence")
    return tuple(item.value for item in value.elts)


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert ast.get_docstring(_storage_initializer()) is not None
    assert issubclass(StorageError, CadrumoError)
    assert issubclass(RepositoryError, StorageError)
    # Sanity-check that the substrate's ``get_logger`` hands back a usable
    # logger; the per-name identity is a Python stdlib invariant and is
    # not worth asserting.
    logger = logging.get_logger(__name__)
    logger.debug("smoke")


def test_public_surface_is_complete() -> None:
    """Every name in ``__all__`` must resolve on the package root.

    The facade resolves most of its surface lazily through :pep:`562`, so a
    name is legitimately absent from the module namespace until first access.
    Resolution through :func:`getattr` is what the contract actually promises,
    and it proves more than a namespace probe: the owning submodule must
    import and must genuinely define the name.
    """
    storage_all = _storage_exports()
    unresolved = sorted(name for name in storage_all if not hasattr(storage_package, name))
    assert not unresolved, f"missing public exports: {unresolved}"


def test_runtime_master_key_and_namespace_boundaries_are_public() -> None:
    """Critical storage boundaries stay public on the modules that define them.

    They were previously asserted to be importable from the package root. That
    root is now an inert namespace, so this guards the same contract read one
    layer in: each name is public, and reachable at exactly one canonical
    module rather than through a re-export.
    """
    expected_by_module = {
        "master_key.master_key": {"MasterKeyProvider"},
        "master_key.active_session": {
            "activate_session",
            "get_active_master_key",
            "has_active_bucket_session",
        },
        "runtime": {
            "StorageRuntime",
            "inspect_bucket_storage_runtime",
            "inspect_storage_runtime",
        },
        "namespace_registry": {
            "STORAGE_NAMESPACE_REGISTRY",
            "secure_object_logical_path",
        },
        "runtime_readiness": {"StorageRuntimeReadiness"},
        "storage_path_definitions": {"STORAGE_PATH_DEFINITIONS"},
    }

    unresolved: list[str] = []
    for module_name, names in expected_by_module.items():
        module = import_module(f"..{module_name}", __package__)
        unresolved += [f"{module_name}.{n}" for n in sorted(names) if not hasattr(module, n)]

    assert not unresolved, f"declared but unresolvable boundaries: {sorted(unresolved)}"
    assert not set(storage_all), "the storage package root is inert and must export nothing"
