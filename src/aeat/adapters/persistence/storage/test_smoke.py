"""Smoke tests for the storage subpackage public surface."""

from __future__ import annotations

import pytest

from .... import errors, logging, storage

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert storage.__doc__ is not None
    assert issubclass(storage.StorageError, errors.AeatError)
    assert issubclass(storage.MigrationError, storage.StorageError)
    assert issubclass(storage.RepositoryError, storage.StorageError)
    assert logging.get_logger(__name__).name == __name__


def test_public_surface_is_complete() -> None:
    """Every name in ``__all__`` must be importable from the package root."""
    for name in storage.__all__:
        assert hasattr(storage, name), f"missing public export: {name}"
