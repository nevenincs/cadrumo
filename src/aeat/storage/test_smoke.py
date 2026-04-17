"""Smoke tests for the storage subpackage public surface."""

from __future__ import annotations

import pytest

import aeat.errors
import aeat.logging
import aeat.storage

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert aeat.storage.__doc__ is not None
    assert issubclass(aeat.storage.StorageError, aeat.errors.AeatError)
    assert issubclass(aeat.storage.MigrationError, aeat.storage.StorageError)
    assert issubclass(aeat.storage.RepositoryError, aeat.storage.StorageError)
    assert aeat.logging.get_logger(__name__).name == __name__


def test_public_surface_is_complete() -> None:
    """Every name in ``__all__`` must be importable from the package root."""
    for name in aeat.storage.__all__:
        assert hasattr(aeat.storage, name), f"missing public export: {name}"
