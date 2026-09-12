"""Smoke tests for the models subpackage."""

import sys

import pytest

from ....core import logging
from ....core.errors.hierarchy import CadrumoError
from ..codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_modelos() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    modelos_namespace = sys.modules[__package__.rsplit(".", 1)[0]]
    modelos_doc = modelos_namespace.__doc__
    assert modelos_doc is not None
    assert issubclass(CadrumoError, Exception)
    assert logging.get_logger(__name__).name == __name__


def test_the_namespace_offers_nothing_of_its_own() -> None:
    """The package is a directory, not a surface.

    This assertion used to be its inverse: ``ModeloCode`` had to be present in
    ``__all__``, because the namespace re-exported a hundred and thirteen
    symbols through a lazy export map. Retiring the map inverts the contract --
    a name reappearing here means someone rebuilt the facade.
    """
    modelos_namespace = sys.modules[__package__.rsplit(".", 1)[0]]
    assert modelos_namespace.__all__ == ()
    assert ModeloCode("303") == ModeloCode("303")
