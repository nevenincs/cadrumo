"""Smoke tests for the models subpackage."""

import pytest

from ...core import errors, logging
from . import __doc__ as modelos_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_smoke_modelos() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert modelos_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
