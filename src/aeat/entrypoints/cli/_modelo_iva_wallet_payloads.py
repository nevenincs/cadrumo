"""IVA wallet payload schemas split from the main modelo registry.

These strict :class:`OutputSchema` subclasses are registered through
:func:`register_schema` and re-exported by :mod:`_modelo_payloads` so the
IVA wallet CLI keeps one payload import surface. The application/modelo
facade remains authoritative for wallet balance, seed, and override behavior;
this module only pins the JSON transport shapes.
"""

from __future__ import annotations

from ...core import Period
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.iva_wallet.balance")
class IvaWalletBalanceResult(OutputSchema):
    """IVA compensation carry-forward wallet balance."""

    operation: str = "modelo.iva_wallet.balance"
    as_of_year: int
    total_balance: str
    active_balance: str
    expired_balance: str
    lot_count: int
    next_expiry_year: int | None
    unallocated_applied_amount: str


@register_schema("modelo.iva_wallet.seed")
class IvaWalletSeedResult(OutputSchema):
    """IVA compensation period seed confirmation."""

    operation: str = "modelo.iva_wallet.seed"
    filing_year: int
    period: Period
    taxpayer_nif: str
    amount: str
    status: str


@register_schema("modelo.iva_wallet.override")
class IvaWalletOverrideResult(OutputSchema):
    """IVA compensation taxpayer-override decision confirmation.

    Records the explicit taxpayer override that releases the Modelo 303
    cross-period compensacion carry the reconciliation gate refuses to auto-apply
    without live AEAT wallet evidence. ``selected_authority`` is
    ``taxpayer_override`` and ``divergence`` is ``override``; ``reason`` and
    ``evidence_locator`` carry the mandatory provenance. The override unblocks
    the carry CALCULATION only - it does not satisfy the dependent period's
    official-evidence verify gate.
    """

    operation: str = "modelo.iva_wallet.override"
    filing_year: int
    period: Period
    taxpayer_nif: str
    amount: str
    reason: str
    evidence_locator: str
    selected_authority: str
    divergence: str
