"""Smoke tests for the models subpackage."""

import pytest

from ....core import errors, logging
from .. import ModeloCode
from .. import __all__ as modelos_all
from .. import __doc__ as modelos_doc

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_modelos() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert modelos_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__


def test_public_surface_includes_modelo_code() -> None:
    assert "ModeloCode" in modelos_all
    assert ModeloCode("303") == ModeloCode("303")
