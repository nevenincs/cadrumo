"""Smoke tests for the browser subpackage."""

import pytest

import aeat.browser
import aeat.errors
import aeat.logging


@pytest.mark.unit
def test_smoke_browser() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.browser.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
