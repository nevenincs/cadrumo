"""Smoke tests for the :mod:`portals` subpackage."""

from __future__ import annotations

import sys

import pytest

from ....core import logging
from ....core.errors.hierarchy import CadrumoError
from .. import registry as portals_registry
from ..registry import PORTAL_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_portals_namespace_and_registry() -> None:
    """The package is inert and the defining registry module is usable."""
    package = sys.modules[portals_registry.__package__]
    portals_all = vars(package).get("__all__", ())
    portals_doc = vars(package).get("__doc__")
    assert portals_doc is not None
    assert issubclass(CadrumoError, Exception)
    assert logging.get_logger(__name__).name == __name__

    assert portals_all == ()
    assert "__getattr__" not in vars(package)

    # Sanity: the registry materialises on first access.
    assert len(PORTAL_REGISTRY) == 41
