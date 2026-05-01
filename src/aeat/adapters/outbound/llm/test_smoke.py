"""Smoke tests for the :mod:`aeat.adapters.outbound.llm` subpackage.

Asserts that the package is importable, exposes a module docstring, and
remains wired into the substrate's :mod:`aeat.core.errors` and
:mod:`aeat.core.logging` conventions.
"""

import pytest

from ....core import errors, logging
from . import __doc__ as llm_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_smoke_llm() -> None:
    """Assert the public package is importable and convention-compliant."""

    assert llm_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
