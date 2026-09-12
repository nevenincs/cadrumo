"""Smoke tests for storage defining modules."""

from __future__ import annotations

import pytest

from .....core import logging
from .....core.errors.hierarchy import CadrumoError
from ... import storage as storage_package
from ..errors import RepositoryError, StorageError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_smoke_storage() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert storage_package.__doc__ is not None
    assert issubclass(StorageError, CadrumoError)
    assert issubclass(RepositoryError, StorageError)
    # Sanity-check that the substrate's ``get_logger`` hands back a usable
    # logger; the per-name identity is a Python stdlib invariant and is
    # not worth asserting.
    logger = logging.get_logger(__name__)
    logger.debug("smoke")
