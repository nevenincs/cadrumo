"""M232 related-party row materialisation into positional casillas.

M232 is an informative-only modelo (Art. 18 LIS) where taxpayers declare
related-party transactions. Rows come from CLI input as ``Modelo232VinculadaRow``
objects and must be materialised into positional casillas on the form.

The form has 5 row slots (vinculada 1-5) for related parties, each with
5 fields (NIF, type_vinculacion, type_operacion, method, importe).
Total positions 144-748 on page_01.

Materialisation maps each row's fields to the registry casilla definitions
declared on the :class:`ModeloRevision` and produces :class:`CasillaObservation`
objects carrying full legal and source provenance from the registry. This is a
CLI-row materialiser on the domain row-model surface, not a registry
``DataBindingDefinition`` family; it consumes the registry symbols it needs
through the registry package facade.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ..calculations.registry import (
    CasillaId,
    CasillaObservation,
    RegistryValidationError,
    casillas_by_id,
)
from ._row_models import Modelo232VinculadaRow

if TYPE_CHECKING:
    from ..calculations.registry import ModeloRevision


M232_MAX_RELATED_PARTY_ROWS = 5
"""Row slots the M232 form declares (vinculada 1-5, positions 144-748, page_01)."""


def m232_related_party_row_casilla_values(
    rows: tuple[Modelo232VinculadaRow, ...],
) -> dict[CasillaId, str | Decimal]:
    """Return the positional casilla id -> value map for related-party ``rows``.

    The single authority mapping a :class:`Modelo232VinculadaRow` onto the form's
    positional casillas. Both consumers read it: the observation materialiser
    below, and the filing replay projection that rehydrates a persisted revision's
    detail rows. Deriving the ids twice is how a persisted row silently stops
    reaching one of the two surfaces.

    Values are returned in their declared scalar form -- text for the NIF and the
    coded fields, :class:`~decimal.Decimal` for the amount -- so a caller can
    render them without re-deriving which casilla is money.

    Args:
        rows: Related-party rows in declaration order; row ``n`` populates the
            ``vinculada-n`` slot.

    Returns:
        Mapping of casilla id to its scalar value, ordered by row then field.

    Raises:
        RegistryValidationError: If ``rows`` exceeds the form's row capacity.
    """
    if len(rows) > M232_MAX_RELATED_PARTY_ROWS:
        raise RegistryValidationError(
            f"M232 form supports maximum {M232_MAX_RELATED_PARTY_ROWS} related-party rows; got {len(rows)}",
        )
    values: dict[CasillaId, str | Decimal] = {}
    for row_index, row in enumerate(rows, start=1):
        row_slot = f"vinculada-{row_index}"
        for field_name, field_value in _extract_row_fields(row, row_slot).items():
            values[_resolve_casilla_id_for_field(row_slot, field_name)] = field_value
    return values


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
    # Capacity is checked before the revision is touched, so an over-capacity
    # call is refused on the rows alone rather than on whatever the revision
    # happens to be.
    row_casilla_values = m232_related_party_row_casilla_values(rows)
    revision_casillas_by_id = casillas_by_id(revision)
    observations: list[CasillaObservation] = []

    for casilla_id, field_value in row_casilla_values.items():
        registry_casilla = revision_casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise RegistryValidationError(
                f"M232 casilla {casilla_id!r} not found in revision casillas",
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=field_value if isinstance(field_value, Decimal) else Decimal(field_value or "0"),
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
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


def _resolve_casilla_id_for_field(row_slot: str, field_name: str) -> CasillaId:
    """Map (row_slot, field_name) to the registry casilla ID.

    Casilla IDs follow the pattern: {row_slot}-{field_name}
    e.g., vinculada-1-nif, vinculada-2-importe, etc.
    """
    return f"{row_slot}-{field_name}"


__all__ = [
    "M232_MAX_RELATED_PARTY_ROWS",
    "m232_related_party_row_casilla_values",
    "materialize_m232_related_party_rows",
]
