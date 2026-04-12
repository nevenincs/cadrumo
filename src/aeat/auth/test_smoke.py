"""Smoke tests for the auth subpackage."""

import pytest

import aeat.auth
import aeat.errors
import aeat.logging


@pytest.mark.unit
def test_smoke_auth() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.auth.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
