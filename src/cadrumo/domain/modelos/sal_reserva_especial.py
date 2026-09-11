"""Deferred SAL/SLL special-reserve calculation boundary.

The versioned registry owns the allocation formula, scalar operands,
applicability, strict-cap boundary, and rounding declarations. This module
retains only the typed calculation boundary while registry-backed evaluation
is wired into its consumers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.schema_base import DateAxis

if TYPE_CHECKING:
    from .modelo_fact_context import ModeloFactResolutionContext


# RegistryQueryService and MappingFactQuery consume the dated SAL/SLL formula mapping
def compute_sal_reserva_especial_dotacion(
    *,
    beneficio_neto: Decimal,
    reserva_dotada: Decimal,
    capital_social: Decimal,
    context: ModeloFactResolutionContext,
) -> Decimal:
    """Evaluate SAL/SLL reserve allocation from the registry specification."""
    del beneficio_neto, reserva_dotada, capital_social
    authority = context.authority
    RegistryQueryService(authority).describe_modelo("100")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="sal-special-reserve-formula-spec",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=context.filing_period,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("SAL/SLL reserve formula must resolve as a mapping fact")
    raise NotImplementedError("SAL/SLL reserve formula specification is unresolved")


__all__ = ["compute_sal_reserva_especial_dotacion"]
