"""Pytest fixtures for domain calculations registry tests."""

from collections.abc import Callable, Iterator

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.ids import RevisionId
from .....domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from .....tests.authority_lease_support import private_authority_lease, scoped_when_requested
from ..governed_fact_scope import validating_governed_facts
from ..schema import RegistrySnapshot
from ._formula_runtime_support import (
    _committed_modelo_130_snapshot,
    _committed_modelo_180_snapshot,
)
from .registry_tree import bundled_registry_tree


@pytest.fixture(scope="session")
def registry_authority() -> Iterator[PinnedAuthorityOperation]:
    """Expose the published authority operation lease to registry-owned tests.

    The lease scopes governed facts only for the tests that depend on it; see
    :func:`~cadrumo.tests.authority_lease_support.private_authority_lease`.
    """
    with private_authority_lease() as operation:
        yield operation


@pytest.fixture(autouse=True)
def _scope_tests_that_request_the_registry_authority(request: pytest.FixtureRequest) -> Iterator[None]:
    with scoped_when_requested(request, "registry_authority"):
        yield


@pytest.fixture(scope="session")
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Expose the committed registry tree to domain-owned structural tests."""
    return bundled_registry_tree()


@pytest.fixture(scope="session")
def registry_snapshot(
    registry_authority: PinnedAuthorityOperation,
) -> Callable[..., RegistrySnapshot]:
    """Build snapshots through the committed authority boundary."""

    def snapshot(
        modelo_id: str,
        filing_year: int,
        period: str,
        *,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> RegistrySnapshot:
        # Wider-scoped consumers build outside any test's lease scope, so the
        # builder scopes its own validation to the generation it reads.
        with validating_governed_facts(registry_authority):
            return registry_authority.snapshot(
                modelo_id,
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
