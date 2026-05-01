"""Smoke tests for the auth subpackage."""

import pytest

from .....core import errors, logging
from . import __doc__ as auth_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_smoke_auth() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert auth_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
