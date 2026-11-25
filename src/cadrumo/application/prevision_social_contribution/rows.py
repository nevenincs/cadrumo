"""The operator-visible row of one stored pension contribution record.

Both the per-ejercicio list and the grouped profile read serve this row, so the
box a record reaches is worked out once, from the pinned authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.renta.prevision_social_contribution_placement import ContributionPlacement
from .results import PrevisionSocialRowProjection

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.renta.prevision_social_contribution import PrevisionSocialContribution
    from .ports import PrevisionSocialPorts


def contribution_row(
    ports: PrevisionSocialPorts, record: PrevisionSocialContribution, revision_id: str
) -> PrevisionSocialRowProjection:
    """Project ``record`` with the box the pinned edition of its ejercicio places it in, if any."""
    placed = ports.authority.placement(record)
    casilla_id: CasillaId | None = placed.casilla_id if isinstance(placed, ContributionPlacement) else None
    return PrevisionSocialRowProjection.from_record(record, revision_id=revision_id, casilla_id=casilla_id)


def contribution_rows(
    ports: PrevisionSocialPorts, ejercicio: int, *, operation: PinnedAuthorityOperation
) -> tuple[PrevisionSocialRowProjection, ...]:
    """Return every stored record of ``ejercicio``, each with its revision and the box it reaches."""
    with validating_governed_facts(operation):
        return tuple(
            contribution_row(ports, record, revision_id)
            for record, revision_id in ports.repository.list_revisioned(ejercicio)
        )


__all__ = ["contribution_row", "contribution_rows"]
