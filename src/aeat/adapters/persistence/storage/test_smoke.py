"""Smoke tests for the storage subpackage's public surface.

Verifies that :mod:`aeat.adapters.persistence.storage` is importable,
exposes the expected error hierarchy, and that every name in
``__all__`` resolves on the package root.
"""

from __future__ import annotations

import pytest

from ....core import errors, logging
from . import RepositoryError, StorageError
from . import __all__ as storage_all
from . import __dict__ as storage_namespace
from . import __doc__ as storage_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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
