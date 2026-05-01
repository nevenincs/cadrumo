"""Smoke tests for the models subpackage."""

import pytest

from ... import errors, logging, models

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_smoke_models() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert models.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
