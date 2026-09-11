from __future__ import annotations

import pytest

from .authority import ValidatedRegistryAuthority, bundled_authority


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    return bundled_authority()
