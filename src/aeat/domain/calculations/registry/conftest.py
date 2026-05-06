from __future__ import annotations

from collections.abc import Callable

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._authority import ValidatedRegistryAuthority
from ._schema import RegistrySnapshot


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT)


@pytest.fixture
def registry_snapshot(
    registry_authority: ValidatedRegistryAuthority,
) -> Callable[[str, int, str], RegistrySnapshot]:
    def snapshot(modelo_id: str, filing_year: int, period: str) -> RegistrySnapshot:
        return registry_authority.snapshot(modelo_id, filing_year=filing_year, period=period)

    return snapshot
