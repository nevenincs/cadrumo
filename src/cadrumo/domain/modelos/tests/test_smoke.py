"""Smoke tests for the models subpackage."""

import pytest

from ....core import logging
from ....core.errors.hierarchy import CadrumoError
from .. import __all__ as modelos_all
from .. import __doc__ as modelos_doc
from ..codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_modelos() -> None:
    """Asserts the subpackage is importable and conventions hold."""
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
    assert modelos_all == ()
    assert ModeloCode("303") == ModeloCode("303")
