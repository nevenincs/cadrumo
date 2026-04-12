"""Smoke tests for the schema subpackage."""

import pytest

import aeat.errors
import aeat.logging
import aeat.schema


@pytest.mark.unit
def test_smoke_schema() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.schema.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
