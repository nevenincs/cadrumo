"""M232 related-party row materialisation into positional casillas.

M232 is an informative-only modelo (Art. 18 LIS) where taxpayers declare
related-party transactions. Rows come from CLI input as ``Modelo232VinculadaRow``
objects and must be materialised into positional casillas on the form.

The form has 5 row slots (vinculada 1-5) for related parties, each with
5 fields (NIF, type_vinculacion, type_operacion, method, importe).
Total positions 144-748 on page_01.

Materialisation maps each row's fields onto the positional casilla ids the
registry declares, carrying each field in its declared scalar form -- text for
the NIF and the coded fields, a :class:`~decimal.Decimal` for the amount. Four
of the five fields per row are therefore non-numeric, which is why this surface
stops at the casilla-id-to-scalar mapping and leaves rendering to its consumer.
This is a domain row-model surface, not a registry ``DataBindingDefinition``
family; it consumes the registry symbols it needs through the registry package
facade.
"""

from __future__ import annotations

from decimal import Decimal

from ...core import CasillaId
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from ._row_models import Modelo232VinculadaRow

M232_MAX_RELATED_PARTY_ROWS = 5
"""Row slots the M232 form declares (vinculada 1-5, positions 144-748, page_01)."""


def m232_related_party_row_casilla_values(
    rows: tuple[Modelo232VinculadaRow, ...],
) -> dict[CasillaId, str | Decimal]:
    """Return the positional casilla id -> value map for related-party ``rows``.

    The single authority mapping a :class:`Modelo232VinculadaRow` onto the form's
    positional casillas, read by the filing replay projection that rehydrates a
    persisted revision's detail rows. Deriving the ids at a second site is how a
    persisted row silently stops reaching the surface that renders it.

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
        for field_name, field_value in _extract_row_fields(row).items():
            values[_resolve_casilla_id_for_field(row_slot, field_name)] = field_value
    return values


def _extract_row_fields(row: Modelo232VinculadaRow) -> dict[str, str | Decimal]:
    """Extract field values from a VinculadaRow in declaration order.

    Fields map to the registry binding definitions in order:
    NIF, tipo_vinculacion, tipo_operacion, metodo, importe. The row slot is
    not a parameter here: it joins the field name into a casilla id one level
    up, in :func:`_resolve_casilla_id_for_field`.
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
]
