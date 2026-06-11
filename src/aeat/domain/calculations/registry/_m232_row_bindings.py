"""M232 related-party row materialisation into positional casillas.

M232 is an informative-only modelo (Art. 18 LIS) where taxpayers declare
related-party transactions. Rows come from CLI input as ``Modelo232VinculadaRow``
objects and must be materialised into positional casillas on the form.

The form has 5 row slots (vinculada 1-5) for related parties, each with
5 fields (NIF, type_vinculacion, type_operacion, method, importe).
Total positions 144-748 on page_01.

Materialisation maps each row's fields to the registry casilla definitions
declared on the :class:`ModeloRevision` and produces :class:`CasillaObservation`
objects carrying full legal and source provenance from the registry.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...modelos._row_models import Modelo232VinculadaRow
from ._bindings import CasillaObservation
from ._errors import RegistryValidationError

if TYPE_CHECKING:
    from ._schema import ModeloRevision


def materialize_m232_related_party_rows(
    revision: ModeloRevision,
    rows: tuple[Modelo232VinculadaRow, ...],
) -> tuple[CasillaObservation, ...]:
    """Materialise related-party rows into positional casillas.

    Each row populates a 1-based row position (vinculada-1 through
    vinculada-5) with 5 fields. Total 50 casillas across 5 row slots
    at positions 144-748 on page_01.

    Creates CasillaObservation for every field in every row, pulling
    legal_refs and source_refs from the registry casilla definitions.
    Rows beyond the form's capacity (>5) are rejected.

    Args:
        revision: The :class:`ModeloRevision` with declared casillas for M232.
        rows: Tuple of Modelo232VinculadaRow objects from CLI input.

    Returns:
        Tuple of :class:`CasillaObservation` objects for all row fields

    Raises:
        RegistryValidationError: If rows exceed form capacity (>5 rows) or if
            a casilla referenced by a row is not defined on the revision.
    """
    if len(rows) > 5:
        raise RegistryValidationError(f"M232 form supports maximum 5 related-party rows; got {len(rows)}")

    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    observations: list[CasillaObservation] = []

    for row_index, row in enumerate(rows, start=1):
        row_slot = f"vinculada-{row_index}"
        row_fields = _extract_row_fields(row, row_slot)
        for field_name, field_value in row_fields.items():
            casilla_id = _resolve_casilla_id_for_field(row_slot, field_name)
            registry_casilla = casillas_by_id.get(casilla_id)
            if registry_casilla is None:
                raise RegistryValidationError(
                    f"M232 casilla {casilla_id!r} ({row_slot}.{field_name}) not found in revision casillas",
                )
            observations.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=field_value if isinstance(field_value, Decimal) else Decimal(field_value or "0"),
                    formula_id=None,
                    operand_refs=(),
                    operand_values=(),
                    legal_refs=registry_casilla.legal_refs,
                    source_refs=registry_casilla.source_refs,
                ),
            )

    return tuple(observations)


def _extract_row_fields(row: Modelo232VinculadaRow, row_slot: str) -> dict[str, str | Decimal]:
    """Extract field values from a VinculadaRow in declaration order.

    Fields map to the registry binding definitions in order:
    NIF, tipo_vinculacion, tipo_operacion, metodo, importe.
    """
    return {
        "nif": row.nif,
        "tipo-vinculacion": row.tipo_vinculacion,
        "tipo-operacion": row.tipo_operacion,
        "metodo-valoracion": row.metodo,
        "importe": row.importe,
    }


def _resolve_casilla_id_for_field(row_slot: str, field_name: str) -> str:
    """Map (row_slot, field_name) to the registry casilla ID.

    Casilla IDs follow the pattern: {row_slot}-{field_name}
    e.g., vinculada-1-nif, vinculada-2-importe, etc.
    """
    return f"{row_slot}-{field_name}"
