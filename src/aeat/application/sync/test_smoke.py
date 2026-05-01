"""Smoke tests for the sync subpackage."""

import pytest

from ...core import errors, logging
from . import __doc__ as sync_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_smoke_sync() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert sync_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
