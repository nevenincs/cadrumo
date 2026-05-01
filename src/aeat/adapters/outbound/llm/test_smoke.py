"""Smoke tests for the llm subpackage."""

import pytest

from .... import errors, llm, logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_mediation]


def test_smoke_llm() -> None:
    """Assert the public package is importable and convention-compliant."""

    assert llm.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
