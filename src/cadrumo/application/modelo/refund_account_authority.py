"""The law that makes a Modelo 100 refund need an account the return states.

Each ejercicio's annual Orden approving the Modelo 100 lets a refund be asked
for only by transfer, and has a return whose result is *a devolver* state or
confirm the IBAN it is paid into. The registry declares that citation once per
ejercicio whose Orden is bundled. A year whose own Orden is not declared cites
the statute alone: the citation of another year's Orden is never carried over.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import GovernedFactNotApplicableError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_references import TemporalProjectionDirection
from ...domain.modelos.work_unit import WorkUnit

REFUND_ACCOUNT_FACT_ID: Final = "modelo-100-devolucion-cuenta"
"""The governed fact citing, per ejercicio, the Orden articles on a refund by transfer to a stated account."""

REFUND_ACCOUNT_STATUTE: Final[tuple[str, ...]] = ("ley-35-2006:art-103",)
"""The refund the Modelo 100 settles, by statute, whatever year's Orden is bundled."""


def refund_account_legal_refs(work_unit: WorkUnit, *, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    """The legal references a refused Modelo 100 refund without an account cites for ``work_unit``'s ejercicio."""
    try:
        resolved = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id=REFUND_ACCOUNT_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=work_unit.period.end_date,
            )
        )
    except GovernedFactNotApplicableError:
        return REFUND_ACCOUNT_STATUTE
    if not isinstance(resolved, ResolvedMappingFact):
        return REFUND_ACCOUNT_STATUTE
    if resolved.projection_direction is not TemporalProjectionDirection.AUTHORED:
        return REFUND_ACCOUNT_STATUTE
    return tuple(str(ref) for ref in resolved.legal_refs)


__all__ = ["REFUND_ACCOUNT_FACT_ID", "REFUND_ACCOUNT_STATUTE", "refund_account_legal_refs"]
