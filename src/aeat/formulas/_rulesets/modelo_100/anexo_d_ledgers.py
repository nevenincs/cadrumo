"""Ledger-derived inputs for Modelo 100 Anexo D normal."""

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

    Args:
        provided: Existing casilla input map. It is copied before changes.
        year: Filing year.
        actividad_id: Economic activity identifier for inventory and asset
            allocation.
        assets: Optional asset records. When omitted, `0173` is not changed.
        amortization_ledger: Optional amortization ledger used with `assets`.
        inventory_ledgers: Optional inventory ledgers. When omitted, `0155` is
            not changed.

    Returns:
        New casilla input map. Ledgers win for `0155` and `0173` when supplied;
        all other values remain caller-owned.
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
