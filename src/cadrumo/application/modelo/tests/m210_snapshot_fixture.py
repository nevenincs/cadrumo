"""Canonical Modelo 210 Convenio registry snapshot fixture."""

import pytest

from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Build the real M210 / horizon exercise / EVENT-1 registry snapshot.

    Treaty consumers resolve their own canonical governed facts, so the
    snapshot need not retain the superseded treaty projection.
    """

    return published_snapshot("210", filing_year=filing_year_envelope().horizon, period="EVENT-1")


__all__ = ["m210_snapshot"]
