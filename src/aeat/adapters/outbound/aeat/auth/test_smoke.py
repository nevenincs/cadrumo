"""Smoke tests for the auth subpackage."""

import pytest

from ..... import auth, errors, logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_smoke_auth() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert auth.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
