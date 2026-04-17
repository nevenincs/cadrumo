"""Smoke tests for the sync subpackage."""

import pytest

from .. import errors, logging, sync


@pytest.mark.unit
def test_smoke_sync() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert sync.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
