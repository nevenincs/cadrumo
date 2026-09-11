"""Pytest fixtures for domain calculations registry tests.

Importing :mod:`cadrumo.application.wizard` triggers the import-time
``register_profile_keys`` push (in ``cadrumo.application.wizard.compiler``) that
populates the registered profile keys from the compiled wizard
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

from cadrumo.application.wizard import compiler as _wizard  # noqa: F401  -- side-effect import: registers profile keys
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from cadrumo.tests.registry_snapshot import build_snapshot
from cadrumo.tests.registry_tree import bundled_registry_tree

from ..compiler.authority import compiled_bundled_authority
from ._formula_runtime_support import (
    _committed_modelo_130_snapshot,
    _committed_modelo_180_snapshot,
)


@pytest.fixture(scope="session")
def registry_authority():
    """The development compiler's bundled authority, never a release artifact."""
    return compiled_bundled_authority()


@pytest.fixture(scope="session")
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load mutable authored declarations for compiler-owned tests only."""
    return bundled_registry_tree()


@pytest.fixture(scope="session")
def registry_snapshot(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> Callable[..., RegistrySnapshot]:
    """Build a model-local snapshot from mutable authoring inputs."""
    modelos, catalogues = registry_tree
    modelos_by_id = {modelo.id: modelo for modelo in modelos}

    def snapshot(
        modelo_id: str,
        filing_year: int,
        period: str,
        *,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> RegistrySnapshot:
        return build_snapshot(
            modelos_by_id[modelo_id],
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            grade=grade,
        )

    return snapshot


@pytest.fixture
def committed_modelo_130_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    return _committed_modelo_130_snapshot(registry_snapshot)


@pytest.fixture
def committed_modelo_180_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    return _committed_modelo_180_snapshot(registry_snapshot)


@pytest.fixture
def m100_2024_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    """M100/2024 at calculation grade.

    These tests assert settlement-chain arithmetic, never filing eligibility,
    so they must not fail on the revision-review, filing-capability or
    legal-review attestation gates.
    """
    return registry_snapshot("100", 2024, "0A", grade=RegistryAuthorityGrade.CALCULATION)


@pytest.fixture
def m100_2025_snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("100", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)
