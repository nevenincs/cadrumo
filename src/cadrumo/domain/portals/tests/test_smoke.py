"""Smoke tests for the :mod:`portals` subpackage."""

from __future__ import annotations

import pytest

from ....core import errors, logging
from .. import __all__ as portals_all
from .. import __doc__ as portals_doc
from .. import __name__ as _package_name
from ..registry import PORTAL_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_portals_public_surface() -> None:
    """The subpackage is importable and publishes the documented surface."""
    assert portals_doc is not None
    assert issubclass(errors.CadrumoError, Exception)
    assert logging.get_logger(__name__).name == __name__

    # Every name advertised in __all__ is resolvable.
    import importlib

    package = importlib.import_module(_package_name)
    for name in portals_all:
        assert hasattr(package, name), name

    # Sanity: the registry materialises on first access.
    assert len(PORTAL_REGISTRY) == 41
