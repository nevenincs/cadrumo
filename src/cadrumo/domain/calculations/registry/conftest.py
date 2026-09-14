from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from .authority import ValidatedRegistryAuthority


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()
