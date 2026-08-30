"""Smoke tests for the storage subpackage's public surface.

Verifies that :mod:`cadrumo.adapters.persistence.storage` is importable,
exposes the expected error hierarchy, and that every name in
``__all__`` resolves on the package root.
"""

from __future__ import annotations

import pytest

from .....core import logging
from .....core.errors.hierarchy import CadrumoError
from ... import storage as storage_package
from .. import RepositoryError, StorageError
from .. import __all__ as storage_all
from .. import __doc__ as storage_doc

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert storage_doc is not None
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
    unresolved = sorted(name for name in storage_all if not hasattr(storage_package, name))
    assert not unresolved, f"missing public exports: {unresolved}"


def test_runtime_master_key_and_namespace_boundaries_are_public() -> None:
    """Critical storage boundaries must be imported from the package root."""
    expected_exports = {
        "MasterKeyProvider",
        "activate_session",
        "get_active_master_key",
        "has_active_bucket_session",
        "inspect_bucket_storage_runtime",
        "inspect_storage_runtime",
        "secure_object_logical_path",
        "StorageRuntime",
        "StorageRuntimeReadiness",
        "STORAGE_NAMESPACE_REGISTRY",
        "STORAGE_PATH_DEFINITIONS",
    }

    assert expected_exports <= set(storage_all)
    unresolved = sorted(name for name in expected_exports if not hasattr(storage_package, name))
    assert not unresolved, f"declared but unresolvable boundaries: {unresolved}"
