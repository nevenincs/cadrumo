"""Ledger-derived inputs for Modelo 100 Anexo D normal.

Bridges :mod:`aeat.domain.profile.assets` and
:mod:`aeat.domain.profile.inventory` ledgers to the per-casilla input
map consumed by Anexo D normal. The single helper
:func:`derive_anexo_d_normal_inputs` overlays ledger-computed values on
top of caller-provided inputs without mutating the original mapping.
"""

from __future__ import annotations

from decimal import Decimal

from ....profile.assets import (
    AmortizationLedger,
    AssetRecord,
    compute_anexo_d_amortization_aggregate,
)
from ....profile.inventory import (
    InventoryLedger,
    compute_anexo_d_inventory_variation,
)

_ZERO = Decimal("0.00")


def derive_anexo_d_normal_inputs(
    provided: dict[str, Decimal],
    *,
    year: int,
    actividad_id: str,
    assets: tuple[AssetRecord, ...] | None = None,
    amortization_ledger: AmortizationLedger | None = None,
    inventory_ledgers: tuple[InventoryLedger, ...] | None = None,
) -> dict[str, Decimal]:
    """Overlay ledger-derived Anexo D normal inputs on caller values.

    Casillas ``0155`` (variación de existencias) and ``0173``
    (amortización del inmovilizado) are computed from the supplied
    ledgers via
    :func:`~aeat.domain.profile.inventory.compute_anexo_d_inventory_variation`
    and
    :func:`~aeat.domain.profile.assets.compute_anexo_d_amortization_aggregate`
    respectively; all other casilla values remain caller-owned.

    Args:
        provided: Existing casilla input map. It is copied before being
            mutated, so the original mapping is untouched.
        year: Filing year.
        actividad_id: Economic activity identifier used for inventory and
            asset allocation.
        assets: Optional tuple of :class:`~aeat.domain.profile.assets.AssetRecord`
            entries. When omitted, casilla ``0173`` is left as-is.
        amortization_ledger: Optional
            :class:`~aeat.domain.profile.assets.AmortizationLedger` consulted
            together with ``assets``. Defaults to an empty ledger when
            ``assets`` is supplied without one.
        inventory_ledgers: Optional tuple of
            :class:`~aeat.domain.profile.inventory.InventoryLedger`
            entries. When omitted, casilla ``0155`` is left as-is.

    Returns:
        A new casilla input map. Ledger-derived values win for ``0155``
        and ``0173`` when supplied; all other values are copied through
        from ``provided``.
    """

    resolved = dict(provided)
    if inventory_ledgers is not None:
        resolved["0155"] = compute_anexo_d_inventory_variation(
            year,
            actividad_id,
            ledgers=inventory_ledgers,
        )
    if assets is not None:
        resolved["0173"] = compute_anexo_d_amortization_aggregate(
            year,
            assets=assets,
            ledger=amortization_ledger or AmortizationLedger(),
            actividad_id=actividad_id,
        )
    return resolved


__all__ = ["derive_anexo_d_normal_inputs"]
