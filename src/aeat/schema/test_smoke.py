"""Smoke tests for the schema subpackage."""

import pytest

from .. import errors, logging, schema

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_smoke_schema() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert schema.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
