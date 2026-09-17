"""M232 related-party row materialisation into positional casillas.

Rows come from CLI input as ``Modelo232VinculadaRow`` objects and are
materialised into the selected revision's positional casillas.  The selected
revision owns the row capacity, field declarations, binding identities, and
export layout; this module retains only the row-materialisation boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.casilla_id import CasillaId
from ...core.time.clock import today_madrid
from ..calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    required_mapping_entry,
    unique_mapping_tokens,
)
from ..calculations.registry.schema_base import DateAxis
from .row_models import Modelo232VinculadaRow

_FACT_ID: Final = "modelo-232-related-party-row-materialisation-mapping"
_SUBJECT: Final = "Modelo 232 related-party row mapping"

#: How each registry-declared row field reads its value off a row. The registry
#: owns which fields exist and in what order; an undeclared field id is refused.
_ROW_FIELD_READERS: Final[Mapping[str, Callable[[Modelo232VinculadaRow], str | Decimal]]] = {
    "nif": lambda row: row.nif,
    "tipo-vinculacion": lambda row: str(row.tipo_vinculacion),
    "tipo-operacion": lambda row: str(row.tipo_operacion),
    "metodo-valoracion": lambda row: str(row.metodo),
    "importe": lambda row: row.importe,
}


def _resolve_m232_registry_declarations(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve the selected Modelo 232 row declaration and mapping fact."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Modelo 232 row declarations must resolve as a mapping fact")
    return resolved


def _row_capacity(entries: Mapping[str, str], slot_ids: tuple[str, ...]) -> int:
    raw = required_mapping_entry(entries, "row.capacity", subject=_SUBJECT)
    if not raw.isdigit() or int(raw) != len(slot_ids):
        raise RegistryValidationError(f"{_SUBJECT} 'row.capacity' must equal the number of declared row slots")
    return int(raw)


def m232_related_party_row_casilla_values(
    rows: tuple[Modelo232VinculadaRow, ...],
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> dict[CasillaId, str | Decimal]:
    """Materialise related-party rows using selected registry declarations.

    The row capacity, slot and field identities, and the casilla id template are
    revision-owned data read from the selected mapping fact; every produced
    casilla id must be declared by the revision that fact names.

    Args:
        rows: Related-party rows in declaration order; row ``n`` fills slot ``n``.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.

    Returns:
        Mapping of casilla id to its scalar value, ordered by row then field --
        text for the NIF and coded fields, :class:`~decimal.Decimal` for the amount.

    Raises:
        RegistryValidationError: If ``rows`` exceed the declared capacity, or the
            mapping declares a field or casilla the selected revision lacks.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return m232_related_party_row_casilla_values(rows, operation=indexed_operation)
    resolved = _resolve_m232_registry_declarations(effective_date=today_madrid(), operation=operation)
    entries = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    slot_ids = unique_mapping_tokens(entries, "row.slot_ids", subject=_SUBJECT)
    field_ids = unique_mapping_tokens(entries, "row.field_ids", subject=_SUBJECT)
    capacity = _row_capacity(entries, slot_ids)
    if len(rows) > capacity:
        raise RegistryValidationError(
            f"Modelo 232 declares at most {capacity} related-party rows; got {len(rows)}",
        )
    unknown = [field_id for field_id in field_ids if field_id not in _ROW_FIELD_READERS]
    if unknown:
        raise RegistryValidationError(f"{_SUBJECT} declares unsupported row fields: {unknown}")
    template = required_mapping_entry(entries, "row.field_id_template", subject=_SUBJECT)
    revision = operation.revision(
        required_mapping_entry(entries, "modelo", subject=_SUBJECT),
        required_mapping_entry(entries, "revision", subject=_SUBJECT),
    )
    declared = {str(casilla.id) for casilla in revision.casillas}
    values: dict[CasillaId, str | Decimal] = {}
    for slot_id, row in zip(slot_ids, rows, strict=False):
        for field_id in field_ids:
            casilla_id = template.format(slot=slot_id, field=field_id)
            if casilla_id not in declared:
                raise RegistryValidationError(
                    f"{_SUBJECT} names casilla {casilla_id!r}, which revision {revision.id} does not declare",
                )
            values[casilla_id] = _ROW_FIELD_READERS[field_id](row)
    return values


__all__ = [
    "m232_related_party_row_casilla_values",
]
