"""Canonical validated registry authority fixture for documentation tests."""

import pytest

from cadrumo.domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


__all__ = ["authority"]
