"""M232 related-party row materialisation into positional casillas.

Rows come from CLI input as ``Modelo232VinculadaRow`` objects and are
materialised into the selected revision's positional casillas.  The selected
revision owns the row capacity, field declarations, binding identities, and
export layout; this module retains only the row-materialisation boundary.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.time.clock import today_madrid
from ..calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.schema_base import DateAxis
from .row_models import Modelo232VinculadaRow


def _resolve_m232_registry_declarations(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve the selected Modelo 232 row declaration and mapping fact."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-232-related-party-row-materialisation-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Modelo 232 row declarations must resolve as a mapping fact")
    return resolved


def m232_related_party_row_casilla_values(
    rows: tuple[Modelo232VinculadaRow, ...],
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> dict[CasillaId, str | Decimal]:
    """Materialise related-party rows using selected registry declarations.

    The row schema and its casilla bindings are revision-owned data.  The
    selected revision and mapping fact are resolved at this boundary; no local
    slot/field fallback is retained.

    Args:
        rows: Related-party rows in declaration order.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.

    Returns:
        An empty mapping for an empty row collection.

    Raises:
        RegistryValidationError: If the generic materialisation adapter receives
            rows before a concrete registry projection is supplied.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return m232_related_party_row_casilla_values(rows, operation=indexed_operation)
    _resolve_m232_registry_declarations(effective_date=today_madrid(), operation=operation)
    if rows:
        raise RegistryValidationError(
            "M232 row materialisation requires selected registry detail/binding declarations",
        )
    return {}


__all__ = [
    "m232_related_party_row_casilla_values",
]
