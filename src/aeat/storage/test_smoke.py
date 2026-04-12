"""Smoke tests for the storage subpackage."""

import pytest

import aeat.errors
import aeat.logging
import aeat.storage


@pytest.mark.unit
def test_smoke_storage() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.storage.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
