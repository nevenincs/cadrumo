"""Smoke tests for the models subpackage."""

import pytest

import aeat.errors
import aeat.logging
import aeat.models


@pytest.mark.unit
def test_smoke_models() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.models.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
