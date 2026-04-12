"""Smoke tests for the corpus subpackage."""

import pytest

import aeat.corpus
import aeat.errors
import aeat.logging


@pytest.mark.unit
def test_smoke_corpus() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.corpus.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__
