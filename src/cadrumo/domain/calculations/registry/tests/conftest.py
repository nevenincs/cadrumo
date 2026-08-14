"""Pytest fixtures for domain calculations registry tests.

Importing :mod:`cadrumo.application.wizard` triggers the import-time
``register_profile_keys`` push (in ``cadrumo.application.wizard._compiler``) that
populates :data:`cadrumo.domain.contribuyente.PROFILE_KEYS` from the compiled wizard
flows. ``test_modelo_100_registry`` imports ``PROFILE_KEYS`` at module load, which
raises ``ProfileKeysRegistrationError`` if the keys were never registered — a
global-state precondition that happens to hold in the full test suite (some peer
module imports the wizard first) but NOT when this directory is collected in
isolation. Importing the wizard catalogue here makes the registry tests
self-sufficient regardless of run scope, instead of relying on cross-test import
order. This is test scaffolding (a conftest), not production domain code, so the
domain→application import is confined to the test boundary.

Note (deeper smell, out of scope for this fix): ``PROFILE_KEYS`` is a
domain-layer constant whose population depends on an application-layer import
side-effect. Making the domain registration independent of application bootstrap
is a larger refactor tracked separately.
"""

from collections.abc import Callable

import pytest

from .....application import wizard as _wizard  # noqa: F401  -- side-effect import: registers profile keys
from .._authority import ValidatedRegistryAuthority
from .._schema import RegistrySnapshot
from ._formula_runtime_support import (
    _committed_modelo_130_snapshot,
    _committed_modelo_180_snapshot,
)


@pytest.fixture
def committed_modelo_130_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return _committed_modelo_130_snapshot(registry_snapshot)


@pytest.fixture
def committed_modelo_180_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return _committed_modelo_180_snapshot(registry_snapshot)


@pytest.fixture
def m100_2024_snapshot(
    registry_authority: ValidatedRegistryAuthority,
) -> RegistrySnapshot:
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


@pytest.fixture
def m100_2025_snapshot(
    registry_authority: ValidatedRegistryAuthority,
) -> RegistrySnapshot:
    return registry_authority.snapshot("100", filing_year=2025, period="0A")
