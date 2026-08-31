"""IVA wallet payload schemas split from the main modelo registry.

These strict :class:`~core.json_contract.OutputSchema` subclasses are
referenced as deferred public schema targets by production-authored CommandSpec and
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

from pydantic import NonNegativeInt, field_validator

from ...core.decimal._grammar import is_non_negative_canonical_decimal
from ...core.filing_year import FilingYear
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.json_contract import OutputSchema
from ...core.period import Period
from ...domain.iva_compensation.balance import CompensationExpiryYear


class IvaWalletBalanceResult(OutputSchema):
    """IVA compensation carry-forward wallet balance.

    Every field mirrors the constraint the canonical
    :class:`~domain.iva_compensation.IvaWalletBalanceReport` already enforces.
    Redeclared as free strings and unbounded primitives this payload accepted
    balance claims the domain report refuses -- a 1900 reference year, a
    negative or ``NaN`` balance, a negative lot count -- and emitted them at the
    operator-facing boundary, which is the one surface a reader has no way to
    check against the domain.

    The amounts stay wire strings, matching every other amount-bearing CLI
    payload, but are validated through the canonical decimal grammar rather
    than accepted as arbitrary text.
    """

    operation: str = "modelo.iva_wallet.balance"
    as_of_year: FilingYear
    total_balance: str
    active_balance: str
    expired_balance: str
    lot_count: NonNegativeInt
    next_expiry_year: CompensationExpiryYear | None = None
    unallocated_applied_amount: str

    @field_validator("total_balance", "active_balance", "expired_balance", "unallocated_applied_amount")
    @classmethod
    def _is_a_non_negative_canonical_amount(cls, value: str) -> str:
        """Refuse an amount the canonical balance report could never have produced.

        ``signed=False`` rejects a negative amount, and the canonical grammar
        rejects ``NaN``, ``Infinity`` and free text, so the wire carries only
        amounts the domain report's ``ge=0`` Decimal fields admit.
        """
        if not is_non_negative_canonical_decimal(value):
            raise ValueError(f"amount must be a non-negative canonical decimal, got {value!r}")
        return value


class IvaWalletSeedResult(OutputSchema):
    """IVA compensation period seed confirmation."""

    operation: str = "modelo.iva_wallet.seed"
    filing_year: int
    period: Period
    taxpayer_nif: str
    amount: str
    provenance: IvaCompensationStateProvenance
    register_status: str | None = None


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
