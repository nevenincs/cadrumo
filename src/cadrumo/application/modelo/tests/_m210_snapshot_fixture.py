"""Canonical Modelo 210 Convenio registry snapshot fixture."""

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Build the real M210 / 2025 / EVENT-1 registry snapshot.

    Treaty consumers resolve their own canonical governed facts, so the
    snapshot need not retain the superseded treaty projection.
    """

    return bundled_authority().snapshot("210", filing_year=2025, period="EVENT-1")


__all__ = ["m210_snapshot"]
