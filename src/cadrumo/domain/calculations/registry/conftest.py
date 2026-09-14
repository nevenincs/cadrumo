from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    from dev.registry.compiler.authority import compiled_bundled_authority

    return compiled_bundled_authority()
