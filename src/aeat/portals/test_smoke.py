"""Smoke tests for the portals subpackage."""

import pytest

import aeat.errors
import aeat.logging
import aeat.portals


@pytest.mark.unit
def test_smoke_portals() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.portals.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
