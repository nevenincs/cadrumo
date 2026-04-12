"""Smoke tests for the llm subpackage."""

import pytest

import aeat.errors
import aeat.llm
import aeat.logging


@pytest.mark.unit
def test_smoke_llm() -> None:
    """Assert the public package is importable and convention-compliant."""

    assert aeat.llm.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
