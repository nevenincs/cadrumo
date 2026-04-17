"""Smoke tests for the auth subpackage."""

import pytest

from .. import auth, errors, logging


@pytest.mark.unit
def test_smoke_auth() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert auth.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
