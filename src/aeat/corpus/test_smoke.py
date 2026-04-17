"""Smoke tests for the corpus subpackage."""

import pytest

from .. import corpus, errors, logging


@pytest.mark.unit
def test_smoke_corpus() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert corpus.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
