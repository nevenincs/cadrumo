"""Registry-aware values used by cross-period persistence fixtures.

These helpers only inspect the published registry and construct deterministic
domain values.  Real storage and application workflow orchestration belongs to
the owning adapter test package, so domain tests and outer integration tests
can use the same registry-derived inputs without pulling persistence inward.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from .....core.casilla_id import CasillaId
from ..bindings_previous_filing import previous_filing_observation_requirements
from ..relations import relation_source_requirements
from ..temporal import select_revision
from .registry_tree import bundled_registry_tree

if TYPE_CHECKING:
    from ....modelos.work_unit import WorkUnit
    from ..schema import ModeloRevision


def resolved_revision(*, modelo: str, filing_year: int, period: str) -> ModeloRevision:
    """Resolve a law-determined revision without touching persistence.

    The registry tree accessor compiles the published tree and
    ``select_revision`` is a pure function, so this works for any modelo and
    filing target without constructing or reading a persistence adapter.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return select_revision(modelo_definition, filing_year=filing_year, period=period)


def cross_period_source_groups(work_unit: WorkUnit) -> dict[tuple[str, int, str], set[CasillaId]]:
    """Group every declared cross-period source by its own filing coordinates."""
    revision = resolved_revision(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    groups: dict[tuple[str, int, str], set[CasillaId]] = {}
    for requirement in previous_filing_observation_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        groups.setdefault(
            (requirement.source_modelo, requirement.filing_year, requirement.periods[0]),
            set(),
        ).update(requirement.source_casilla_ids)
    for requirement in relation_source_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        for source_period in requirement.periods:
            groups.setdefault(
                (requirement.source_modelo, requirement.filing_year, source_period),
                set(),
            ).update(requirement.source_casilla_ids)
    return groups


def source_casilla_values(source_casilla_ids: set[CasillaId]) -> dict[CasillaId, Decimal]:
    """Give each source casilla a distinct, deterministic non-zero value."""
    return {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casilla_ids))}


__all__ = [
    "cross_period_source_groups",
    "resolved_revision",
    "source_casilla_values",
]
