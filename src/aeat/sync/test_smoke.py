"""Smoke tests for the sync subpackage."""

import pytest

import aeat.errors
import aeat.logging
import aeat.sync


@pytest.mark.unit
def test_smoke_sync() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.sync.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
