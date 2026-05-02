"""Smoke tests for the :mod:`aeat.application.sync` subpackage.

Asserts the public package import surface is intact and that the shared
:mod:`aeat.core.errors` / :mod:`aeat.core.logging` conventions used by the
package still hold.
"""

import pytest

from ...core import errors, logging
from . import __doc__ as sync_doc

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_smoke_sync() -> None:
    """Assert the subpackage is importable and its conventions hold."""
    assert sync_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__
