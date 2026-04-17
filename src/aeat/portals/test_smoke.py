"""Smoke tests for the :mod:`aeat.portals` subpackage."""

from __future__ import annotations

import pytest

import aeat.errors
import aeat.logging
import aeat.portals

pytestmark = pytest.mark.unit


def test_smoke_portals_public_surface() -> None:
    """The subpackage is importable and publishes the documented surface."""
    assert aeat.portals.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__

    # Every name advertised in __all__ is resolvable.
    for name in aeat.portals.__all__:
        assert hasattr(aeat.portals, name), name

    # Sanity: the registry materialises on first access.
    assert len(aeat.portals.PORTAL_REGISTRY) == 41
