"""IVA compensation wallet reconciliation decisions.

The live AEAT wallet is external state. Local Modelo 303 recurrence is
internal reconstruction. This module is the boundary that turns those
evidence sources, plus an explicit taxpayer override when present, into
the effective binding decision consumed by Modelo 303 calculation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.outbound.aeat.sede._schema import IvaCompensationWalletObservation
from ...domain.calculations.registry._schema import RegistrySnapshot

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
_DEFAULT_MAX_WALLET_AGE_DAYS: Final[int] = 31
_MODELO_303_IVA_COMPENSATION_BINDING_ID: Final[str] = "modelo-303-compensacion-pendiente-anteriores"

type IvaCompensationAuthority = Literal["aeat_wallet", "taxpayer_override", "local_recurrence", "missing"]
type IvaCompensationDivergence = Literal[
    "match",
    "wallet_only",
    "wallet_higher",
    "wallet_lower",
    "wallet_missing",
    "wallet_stale",
    "override",
    "missing",
]


class IvaCompensationOverride(BaseModel):
    """Explicit taxpayer override for Modelo 303 prior compensation."""

    model_config = _STRICT_FROZEN

    amount: Decimal = Field(ge=Decimal("0"))
    reason: str = Field(min_length=1, max_length=1024)
    evidence_locator: str = Field(min_length=1, max_length=1024)
    recorded_at: datetime


class IvaCompensationReconciliationDecision(BaseModel):
    """Effective prior-compensation binding decision for Modelo 303.

    This record is persisted and replayed by calculation. A live wallet
    fetch creates evidence; this decision says whether that evidence can
    safely drive the binding or whether review is required.
    """

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    target_year: int = Field(ge=2000, le=2099)
    target_period: str = Field(min_length=1, max_length=8)
    selected_authority: IvaCompensationAuthority
    selected_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    wallet_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    local_recurrence_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    override_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    divergence: IvaCompensationDivergence
    blocked: bool
    stale_wallet: bool
    reason: str = Field(min_length=1, max_length=2048)
    wallet_captured_at: datetime | None = None
    decided_at: datetime

    @model_validator(mode="after")
    def _validate_selected_amount(self) -> IvaCompensationReconciliationDecision:
        if self.selected_authority != "missing" and self.selected_amount is None:
            raise ValueError("selected_amount is required unless selected_authority is 'missing'")
        if self.selected_authority == "missing" and self.selected_amount is not None:
            raise ValueError("selected_amount must be absent when selected_authority is 'missing'")
        if self.blocked and self.selected_authority == "aeat_wallet":
            raise ValueError("blocked wallet divergence cannot select aeat_wallet for calculation")
        return self


class IvaCompensationReconciliationReport(BaseModel):
    """Application-level reconciliation result for one Modelo 303 target."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    decision: IvaCompensationReconciliationDecision
    prefill_report: Any


class IvaCompensationReconciliationInputError(ValueError):
    """Raised when wallet evidence does not match the target Modelo 303 snapshot."""


def reconcile_modelo_303_iva_compensation(
    snapshot: RegistrySnapshot,
    *,
    taxpayer_nif: str,
    wallet: IvaCompensationWalletObservation | None,
    repository=None,  # type: ignore[no-untyped-def]
    override: IvaCompensationOverride | None = None,
    decided_at: datetime | None = None,
    max_wallet_age_days: int = _DEFAULT_MAX_WALLET_AGE_DAYS,
    persist: bool = True,
) -> IvaCompensationReconciliationReport:
    """Resolve, compare, and optionally persist the Modelo 303 IVA wallet decision.

    The local side is not recomputed here. It is read through the same
    previous-filing binding resolver used by the calculation chain.
    """

    if str(getattr(snapshot.modelo, "id", snapshot.modelo)) != "303":
        raise IvaCompensationReconciliationInputError(
            "IVA compensation wallet reconciliation only applies to Modelo 303"
        )
    if wallet is not None:
        _validate_wallet_matches_snapshot(
            wallet,
            taxpayer_nif=taxpayer_nif,
            target_year=snapshot.filing_year,
            target_period=snapshot.period,
        )

    from ._binding_prefill import resolve_bindings_from_local_store
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository

    repo = repository if repository is not None else CalculationObservationRepository()
    prefill_report = resolve_bindings_from_local_store(
        snapshot,
        repository=repo,
        captured_at=decided_at,
    )
    local_amount = prefill_report.binding_values.get(_MODELO_303_IVA_COMPENSATION_BINDING_ID)
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=taxpayer_nif,
        target_year=snapshot.filing_year,
        target_period=snapshot.period,
        wallet=wallet,
        local_recurrence_amount=Decimal(local_amount) if local_amount is not None else None,
        override=override,
        decided_at=decided_at,
        max_wallet_age_days=max_wallet_age_days,
    )
    if persist:
        IvaWalletDecisionRepository().save_decision(decision)
    return IvaCompensationReconciliationReport(
        decision=decision,
        prefill_report=prefill_report,
    )


def reconcile_iva_compensation_wallet(
    *,
    taxpayer_nif: str,
    target_year: int,
    target_period: str,
    wallet: IvaCompensationWalletObservation | None,
    local_recurrence_amount: Decimal | None,
    override: IvaCompensationOverride | None = None,
    decided_at: datetime | None = None,
    max_wallet_age_days: int = _DEFAULT_MAX_WALLET_AGE_DAYS,
) -> IvaCompensationReconciliationDecision:
    """Return the deterministic effective-value decision for casilla `110`.

    Authority order is wallet, explicit taxpayer override, local
    recurrence. Divergence between fresh wallet evidence and local
    recurrence blocks automatic calculation unless an override is
    recorded.
    """

    when = decided_at if decided_at is not None else datetime.now(UTC)
    wallet_amount = wallet.total_pending if wallet is not None else None
    wallet_captured_at = wallet.captured_at if wallet is not None else None
    stale_wallet = _is_wallet_stale(wallet_captured_at, when, max_wallet_age_days)

    if override is not None:
        return IvaCompensationReconciliationDecision(
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
            selected_authority="taxpayer_override",
            selected_amount=override.amount,
            wallet_amount=wallet_amount,
            local_recurrence_amount=local_recurrence_amount,
            override_amount=override.amount,
            divergence="override",
            blocked=False,
            stale_wallet=stale_wallet,
            reason=override.reason,
            wallet_captured_at=wallet_captured_at,
            decided_at=when,
        )

    if wallet_amount is None:
        if local_recurrence_amount is None:
            return IvaCompensationReconciliationDecision(
                taxpayer_nif=taxpayer_nif,
                target_year=target_year,
                target_period=target_period,
                selected_authority="missing",
                selected_amount=None,
                wallet_amount=None,
                local_recurrence_amount=None,
                override_amount=None,
                divergence="missing",
                blocked=True,
                stale_wallet=False,
                reason="No AEAT wallet observation or local recurrence is available for Modelo 303 prior compensation.",
                wallet_captured_at=None,
                decided_at=when,
            )
        return IvaCompensationReconciliationDecision(
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
            selected_authority="local_recurrence",
            selected_amount=local_recurrence_amount,
            wallet_amount=None,
            local_recurrence_amount=local_recurrence_amount,
            override_amount=None,
            divergence="wallet_missing",
            blocked=False,
            stale_wallet=False,
            reason="AEAT wallet is unavailable; using lower-confidence local recurrence.",
            wallet_captured_at=None,
            decided_at=when,
        )

    if stale_wallet:
        if local_recurrence_amount is None:
            return IvaCompensationReconciliationDecision(
                taxpayer_nif=taxpayer_nif,
                target_year=target_year,
                target_period=target_period,
                selected_authority="missing",
                selected_amount=None,
                wallet_amount=wallet_amount,
                local_recurrence_amount=None,
                override_amount=None,
                divergence="wallet_stale",
                blocked=True,
                stale_wallet=True,
                reason="AEAT wallet observation is stale and no local recurrence fallback is available.",
                wallet_captured_at=wallet_captured_at,
                decided_at=when,
            )
        return IvaCompensationReconciliationDecision(
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
            selected_authority="local_recurrence",
            selected_amount=local_recurrence_amount,
            wallet_amount=wallet_amount,
            local_recurrence_amount=local_recurrence_amount,
            override_amount=None,
            divergence="wallet_stale",
            blocked=False,
            stale_wallet=True,
            reason="AEAT wallet observation is stale; using lower-confidence local recurrence.",
            wallet_captured_at=wallet_captured_at,
            decided_at=when,
        )

    if local_recurrence_amount is not None and wallet_amount != local_recurrence_amount:
        divergence: IvaCompensationDivergence = (
            "wallet_higher" if wallet_amount > local_recurrence_amount else "wallet_lower"
        )
        return IvaCompensationReconciliationDecision(
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
            selected_authority="missing",
            selected_amount=None,
            wallet_amount=wallet_amount,
            local_recurrence_amount=local_recurrence_amount,
            override_amount=None,
            divergence=divergence,
            blocked=True,
            stale_wallet=False,
            reason="AEAT wallet and local recurrence diverge; review is required before automatic output.",
            wallet_captured_at=wallet_captured_at,
            decided_at=when,
        )

    if local_recurrence_amount is None:
        return IvaCompensationReconciliationDecision(
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
            selected_authority="aeat_wallet",
            selected_amount=wallet_amount,
            wallet_amount=wallet_amount,
            local_recurrence_amount=None,
            override_amount=None,
            divergence="wallet_only",
            blocked=False,
            stale_wallet=False,
            reason=(
                "Using latest valid AEAT wallet observation for Modelo 303 prior compensation; "
                "no local prior-filing recurrence was available for cross-check."
            ),
            wallet_captured_at=wallet_captured_at,
            decided_at=when,
        )

    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=target_year,
        target_period=target_period,
        selected_authority="aeat_wallet",
        selected_amount=wallet_amount,
        wallet_amount=wallet_amount,
        local_recurrence_amount=local_recurrence_amount,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="Using latest valid AEAT wallet observation for Modelo 303 prior compensation.",
        wallet_captured_at=wallet_captured_at,
        decided_at=when,
    )


def _validate_wallet_matches_snapshot(
    wallet: IvaCompensationWalletObservation,
    *,
    taxpayer_nif: str,
    target_year: int,
    target_period: str,
) -> None:
    if wallet.taxpayer_nif != taxpayer_nif:
        raise IvaCompensationReconciliationInputError(
            "IVA wallet observation taxpayer does not match the requested taxpayer"
        )
    if wallet.target_year != target_year or wallet.target_period != target_period:
        raise IvaCompensationReconciliationInputError(
            "IVA wallet observation target does not match the Modelo 303 snapshot"
        )


def _is_wallet_stale(
    captured_at: datetime | None,
    decided_at: datetime,
    max_wallet_age_days: int,
) -> bool:
    if captured_at is None:
        return False
    if max_wallet_age_days < 0:
        raise ValueError("max_wallet_age_days must be non-negative")
    return decided_at - captured_at > timedelta(days=max_wallet_age_days)


__all__ = [
    "IvaCompensationOverride",
    "IvaCompensationReconciliationDecision",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationReconciliationReport",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
]
