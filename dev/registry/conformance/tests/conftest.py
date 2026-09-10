"""Fixtures owned by development registry-conformance tests."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    """Provide the real validated bundled authority to conformance tests."""
    return bundled_authority()
