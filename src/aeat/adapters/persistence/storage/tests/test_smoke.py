"""Smoke tests for the storage subpackage's public surface.

Verifies that :mod:`aeat.adapters.persistence.storage` is importable,
exposes the expected error hierarchy, and that every name in
``__all__`` resolves on the package root.
"""

from __future__ import annotations

import pytest

from .....core import errors, logging
from .. import RepositoryError, StorageError
from .. import __all__ as storage_all
from .. import __dict__ as storage_namespace
from .. import __doc__ as storage_doc

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert storage_doc is not None
    assert issubclass(StorageError, errors.AeatError)
    assert issubclass(RepositoryError, StorageError)
    # Sanity-check that the substrate's ``get_logger`` hands back a usable
    # logger; the per-name identity is a Python stdlib invariant and is
    # not worth asserting.
    logger = logging.get_logger(__name__)
    logger.debug("smoke")


def test_public_surface_is_complete() -> None:
    """Every name in ``__all__`` must be importable from the package root."""
    for name in storage_all:
        assert name in storage_namespace, f"missing public export: {name}"


def test_runtime_master_key_and_namespace_boundaries_are_public() -> None:
    """Critical storage boundaries must be imported from the package root."""
    expected_exports = {
        "MasterKeyProvider",
        "activate_master_key_provider",
        "activate_session",
        "get_active_master_key",
        "get_master_key_provider",
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
    assert expected_exports <= storage_namespace.keys()
