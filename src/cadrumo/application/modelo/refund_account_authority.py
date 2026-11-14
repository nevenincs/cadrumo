"""The law that makes a Modelo 100 refund need an account the return states.

Each ejercicio's annual Orden approving the Modelo 100 lets a refund be asked
for only by transfer, and has a return whose result is *a devolver* state or
confirm the IBAN it is paid into. The registry declares that citation for each
ejercicio whose Orden differs; a year whose Orden is not bundled reads the
nearest one, as every governed fact does.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.facts.resolution import MappingFactQuery
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.work_unit import WorkUnit

REFUND_ACCOUNT_FACT_ID: Final = "modelo-100-devolucion-cuenta"
"""The governed fact citing, per ejercicio, the Orden articles on a refund by transfer to a stated account."""


def refund_account_legal_refs(work_unit: WorkUnit, *, operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    """The legal references a refused Modelo 100 refund without an account cites for ``work_unit``'s ejercicio."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=REFUND_ACCOUNT_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=work_unit.period.end_date,
        )
    )
    return tuple(str(ref) for ref in resolved.legal_refs)


__all__ = ["REFUND_ACCOUNT_FACT_ID", "refund_account_legal_refs"]
