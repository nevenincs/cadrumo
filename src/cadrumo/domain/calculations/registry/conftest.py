from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core import RegistryAuthorityGrade
from ....core.resources import bundled_path
from ....tests.registry_tree import bundled_registry_tree
from .authority import ValidatedRegistryAuthority, bundled_authority
from .ids import RevisionId
from .schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from .snapshot import build_snapshot


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="session")
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Compile-only registry tree, independent of ``registry_authority``.

    ``registry_authority`` (``ValidatedRegistryAuthority.load`` via
    ``resources()``) eagerly validates every modelo in the tree before it
    returns, so one modelo missing filing capability breaks every caller
    regardless of which modelo, or which grade of question, it actually
    asks. ``registry_snapshot`` below only ever needs ONE modelo's compiled
    definition plus the shared catalogues, so it loads independently of the
    authority rather than inheriting its all-or-nothing gate.
    """
    return bundled_registry_tree()


@pytest.fixture(scope="session")
def registry_snapshot(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> Callable[..., RegistrySnapshot]:
    """Build a :class:`RegistrySnapshot` for one modelo, scoped to that modelo alone.

    ``grade`` defaults to :attr:`RegistryAuthorityGrade.FILING`, preserving the
    prior ``registry_authority.snapshot(...)`` contract for callers that need
    it. Callers asking a narrower question (a formula-runtime calculation, an
    applicability/scheduling fact) should pass a lower grade explicitly to
    skip the revision-review, filing-capability and legal-review checks that
    do not bear on their claim -- see :class:`RegistryAuthorityGrade`.
    """
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
