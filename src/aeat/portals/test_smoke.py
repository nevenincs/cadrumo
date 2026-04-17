"""Smoke tests for the :mod:`portals` subpackage."""

from __future__ import annotations

import pytest

from .. import errors, logging, portals

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_smoke_portals_public_surface() -> None:
    """The subpackage is importable and publishes the documented surface."""
    assert portals.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__

    # Every name advertised in __all__ is resolvable.
    for name in portals.__all__:
        assert hasattr(portals, name), name

    # Sanity: the registry materialises on first access.
    assert len(portals.PORTAL_REGISTRY) == 41
