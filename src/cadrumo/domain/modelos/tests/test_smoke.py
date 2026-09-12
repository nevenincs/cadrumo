"""Smoke tests for the models subpackage."""

import sys

import pytest

from ....core import logging
from ....core.errors.hierarchy import CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_smoke_modelos() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    modelos_namespace = sys.modules[__package__.rsplit(".", 1)[0]]
    modelos_doc = modelos_namespace.__doc__
    assert modelos_doc is not None
    assert issubclass(CadrumoError, Exception)
    assert logging.get_logger(__name__).name == __name__
