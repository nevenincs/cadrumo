"""IVA compensation wallet reconciliation decisions.

The live AEAT wallet is external state. Local Modelo 303 recurrence is
internal reconstruction. This module is the boundary that turns those
evidence sources, plus an explicit taxpayer override when present, into
the effective binding decision consumed by Modelo 303 calculation.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.outbound.aeat.sede import IvaCompensationWalletObservation
from ...core.errors import AeatError
from ...domain.calculations.registry._schema import RegistrySnapshot
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

if TYPE_CHECKING:
    from ._binding_prefill import LocalIvaCompensationRecurrence

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
_DEFAULT_MAX_WALLET_AGE_DAYS: Final[int] = 31
_AEAT_FILED_HISTORY_SOURCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_iva_compensation_history",
        "filed_history_observation",
    }
)

type IvaCompensationAuthority = Literal[
    "aeat_wallet",
    "taxpayer_override",
    "filed_history",
    "local_recurrence",
    "missing",
]
type IvaCompensationAuthoritySourceKind = Literal[
    "aeat_wallet",
    "local_recurrence",
    "filed_history_observation",
    "taxpayer_override",
]
type IvaCompensationDivergence = Literal[
    "match",
    "wallet_only",
    "wallet_higher",
    "wallet_lower",
    "wallet_missing",
    "filed_history_only",
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


class IvaCompensationAuthoritySource(BaseModel):
    """One evidence source considered by an IVA compensation decision."""

    model_config = _STRICT_FROZEN

    source_kind: IvaCompensationAuthoritySourceKind
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    source_locator: str = Field(min_length=1, max_length=1024)
    captured_at: datetime | None = None
    source_modelo: str | None = Field(default=None, min_length=1, max_length=8)
    source_filing_year: int | None = Field(default=None, ge=2000, le=2099)
    source_periods: tuple[str, ...] = ()


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
    authority_sources: tuple[IvaCompensationAuthoritySource, ...] = ()
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


class IvaCompensationReconciliationInputError(AeatError, ValueError):
    """Raised when wallet evidence does not match the target Modelo 303 snapshot."""


class IvaWalletDecisionSourceResolver:
    """Source mesh adapter for persisted Modelo 303 IVA wallet decisions."""

    resolver_id = "iva_wallet_decision"
    owned_sources = ("iva_wallet_decision",)
    binding_id = "modelo-303-compensacion-pendiente-anteriores"

    def __init__(self, decision: IvaCompensationReconciliationDecision | None) -> None:
        self._decision = decision

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if context.modelo != "303" or self._decision is None:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
            )
        decision = self._decision
        if decision.target_year != context.filing_year or decision.target_period != context.period:
            raise IvaCompensationReconciliationInputError(
                "IVA wallet reconciliation decision target does not match the Modelo 303 work unit"
            )
        if decision.blocked:
            raise IvaCompensationReconciliationInputError(
                f"IVA wallet reconciliation blocks automatic Modelo 303 calculation: {decision.divergence}"
            )
        if decision.selected_amount is None:
            raise IvaCompensationReconciliationInputError(
                "IVA wallet reconciliation decision has no selected amount"
            )
        fingerprint = f"sha256:{hashlib.sha256(decision.model_dump_json().encode('utf-8')).hexdigest()}"
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={self.binding_id: Decimal(decision.selected_amount)},
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind=source.source_kind,
                    source_ref=source.source_locator,
                    fingerprint=fingerprint,
                )
                for source in decision.authority_sources
            ),
        )


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

    from ._binding_prefill import extract_modelo_303_local_iva_compensation_recurrence
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository

    repo = repository if repository is not None else CalculationObservationRepository()
    recurrence, prefill_report = extract_modelo_303_local_iva_compensation_recurrence(
        snapshot,
        repository=repo,
        captured_at=decided_at,
    )
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=taxpayer_nif,
        target_year=snapshot.filing_year,
        target_period=snapshot.period,
        wallet=wallet,
        local_recurrence_amount=recurrence.amount if recurrence is not None else None,
        local_recurrence_source=_local_recurrence_authority_source(recurrence),
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
    local_recurrence_source: IvaCompensationAuthoritySource | None = None,
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

    if wallet is not None:
        _validate_wallet_matches_snapshot(
            wallet,
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
        )
    when = decided_at if decided_at is not None else datetime.now(UTC)
    wallet_amount = wallet.total_pending if wallet is not None else None
    wallet_captured_at = wallet.captured_at if wallet is not None else None
    stale_wallet = _is_wallet_stale(wallet_captured_at, when, max_wallet_age_days)
    authority_sources = _authority_sources(
        wallet=wallet,
        local_recurrence_amount=local_recurrence_amount,
        local_recurrence_source=local_recurrence_source,
        override=override,
    )

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
            authority_sources=authority_sources,
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
                authority_sources=authority_sources,
                decided_at=when,
            )
        if _is_filed_history_source(local_recurrence_source):
            return IvaCompensationReconciliationDecision(
                taxpayer_nif=taxpayer_nif,
                target_year=target_year,
                target_period=target_period,
                selected_authority="filed_history",
                selected_amount=local_recurrence_amount,
                wallet_amount=None,
                local_recurrence_amount=local_recurrence_amount,
                override_amount=None,
                divergence="filed_history_only",
                blocked=True,
                stale_wallet=False,
                reason=(
                    "Direct AEAT wallet/cartera evidence is unavailable; AEAT filed-history-derived recurrence "
                    "is recorded as fallback evidence but requires explicit taxpayer override before automatic output."
                ),
                wallet_captured_at=None,
                authority_sources=authority_sources,
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
            blocked=True,
            stale_wallet=False,
            reason=(
                "AEAT wallet is unavailable; local recurrence is lower-confidence fallback evidence and requires "
                "explicit taxpayer override before automatic output."
            ),
            wallet_captured_at=None,
            authority_sources=authority_sources,
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
                authority_sources=authority_sources,
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
            blocked=True,
            stale_wallet=True,
            reason=(
                "AEAT wallet observation is stale; local recurrence is lower-confidence fallback evidence and "
                "requires explicit taxpayer override before automatic output."
            ),
            wallet_captured_at=wallet_captured_at,
            authority_sources=authority_sources,
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
            authority_sources=authority_sources,
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
            authority_sources=authority_sources,
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
        authority_sources=authority_sources,
        decided_at=when,
    )


def _authority_sources(
    *,
    wallet: IvaCompensationWalletObservation | None,
    local_recurrence_amount: Decimal | None,
    local_recurrence_source: IvaCompensationAuthoritySource | None,
    override: IvaCompensationOverride | None,
) -> tuple[IvaCompensationAuthoritySource, ...]:
    sources: list[IvaCompensationAuthoritySource] = []
    if wallet is not None:
        sources.append(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=wallet.total_pending,
                source_locator=str(wallet.source_url),
                captured_at=wallet.captured_at,
            )
        )
    if local_recurrence_amount is not None:
        recurrence_source = local_recurrence_source or IvaCompensationAuthoritySource(
            source_kind="local_recurrence",
            amount=local_recurrence_amount,
            source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
        )
        if recurrence_source.source_kind == "filed_history_observation":
            sources.append(
                IvaCompensationAuthoritySource(
                    source_kind="local_recurrence",
                    amount=local_recurrence_amount,
                    source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
                    captured_at=recurrence_source.captured_at,
                    source_modelo=recurrence_source.source_modelo,
                    source_filing_year=recurrence_source.source_filing_year,
                    source_periods=recurrence_source.source_periods,
                )
        )
        sources.append(recurrence_source)
    if override is not None:
        sources.append(
            IvaCompensationAuthoritySource(
                source_kind="taxpayer_override",
                amount=override.amount,
                source_locator=override.evidence_locator,
                captured_at=override.recorded_at,
            )
        )
    return tuple(sources)


def _is_filed_history_source(source: IvaCompensationAuthoritySource | None) -> bool:
    return source is not None and source.source_kind == "filed_history_observation"


def _local_recurrence_authority_source(
    recurrence: LocalIvaCompensationRecurrence | None,
) -> IvaCompensationAuthoritySource | None:
    if recurrence is None:
        return None
    amount = Decimal(recurrence.amount)
    binding_id = str(recurrence.binding_id)
    source_modelo = str(recurrence.source_modelo)
    source_filing_year = int(recurrence.source_filing_year)
    source_periods = tuple(str(item) for item in recurrence.source_periods)
    resolved_at = recurrence.resolved_at
    source_kind: IvaCompensationAuthoritySourceKind = (
        "filed_history_observation"
        if recurrence.source_kind in _AEAT_FILED_HISTORY_SOURCE_KINDS
        else "local_recurrence"
    )
    return IvaCompensationAuthoritySource(
        source_kind=source_kind,
        amount=amount,
        source_locator=f"binding:{binding_id}",
        captured_at=resolved_at,
        source_modelo=source_modelo,
        source_filing_year=source_filing_year,
        source_periods=source_periods,
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
    "IvaCompensationAuthoritySource",
    "IvaCompensationOverride",
    "IvaCompensationReconciliationDecision",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationReconciliationReport",
    "IvaWalletDecisionSourceResolver",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
]
