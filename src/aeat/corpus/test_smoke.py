"""Smoke tests for the corpus subpackage."""

import pytest

from .. import corpus, errors, logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_smoke_corpus() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert corpus.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
