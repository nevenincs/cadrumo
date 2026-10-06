"""Materialize typed affiliate facts through the selected revision's bindings."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ..calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.ids import BindingId
from ..calculations.registry.schema import ModeloRevision
from .m156_rows import Modelo156AfiliadoRow


def _source_value(row: Modelo156AfiliadoRow, field: str) -> str | Decimal | None:
    if field == "nif":
        return row.nif
    if field == "nombre":
        return row.nombre
    if field == "numero_afiliacion":
        return row.numero_afiliacion
    # Field syntax is closed by AfiliadoContributionProvider, not by callers.
    _, month, component = field.split("_")
    value = row.cotizaciones[int(month) - 1]
    return value.status if component == "situacion" else value.amount


def materialize_m156_member_bindings(
    revision: ModeloRevision,
    members: Sequence[Modelo156AfiliadoRow],
) -> dict[tuple[BindingId, int], str | Decimal]:
    """Preserve row identity and missing facts without taking values from scalar casillas.

    Reordering supplied members does not change occurrence indices. Duplicate
    identities refuse rather than double-counting a member or choosing a winner.
    This pure projection is shared groundwork for saved replay and source routing;
    a provider still marked deferred cannot claim production filing capability.
    """
    bindings = tuple(
        (binding.id, binding.provider)
        for binding in revision.bindings
        if isinstance(binding.provider, AfiliadoContributionProvider)
    )
    if members and not bindings:
        raise RegistryValidationError("the selected revision declares no affiliate row bindings")
    ordered = sorted(members, key=lambda row: (row.nif, row.numero_afiliacion))
    identities = [(row.nif, row.numero_afiliacion) for row in ordered]
    if len(identities) != len(set(identities)):
        raise RegistryValidationError("affiliate rows contain a duplicate member identity")
    result: dict[tuple[BindingId, int], str | Decimal] = {}
    for index, row in enumerate(ordered, 1):
        for binding_id, provider in bindings:
            value = _source_value(row, provider.row_field)
            if value is not None:
                result[binding_id, index] = value
    return result
