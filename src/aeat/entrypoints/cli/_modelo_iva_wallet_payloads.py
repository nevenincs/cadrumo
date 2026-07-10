"""IVA wallet payload schemas split from the main modelo registry.

These strict :class:`~entrypoints.cli._schemas.OutputSchema` subclasses are
registered through :func:`~entrypoints.cli._schemas.register_schema` and
re-exported by :mod:`~entrypoints.cli._modelo_payloads` so the IVA wallet CLI
keeps one payload import surface. The application/calculations facade remains
authoritative for wallet balance queries; the application/modelo facade remains
authoritative for seed and override behavior. This module only pins the JSON
transport shapes.

See Also:
    :mod:`~entrypoints.cli._modelo_iva_wallet_cli`
        Typer command group that emits these payload classes.
    :func:`~application.calculations.query_iva_wallet_balance`
        Application query that supplies :class:`IvaWalletBalanceResult`.
    :func:`~application.modelo.seed_iva_compensation_period_for_bucket`
        Seed service projected by :class:`IvaWalletSeedResult`.
    :func:`~application.modelo.record_iva_compensation_override_for_bucket`
        Override recorder projected by :class:`IvaWalletOverrideResult`.
    :class:`~domain.iva_compensation.IvaWalletBalanceReport`
        Domain balance summary converted into the balance payload.
    :class:`~domain.iva_compensation.IvaCompensationPeriodState`
        Persisted period-state record returned by seed operations.
    :class:`~domain.iva_compensation.IvaCompensationReconciliationDecision`
        Persisted wallet-authority decision returned by override operations.
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
