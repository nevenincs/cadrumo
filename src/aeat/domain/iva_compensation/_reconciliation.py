"""IVA compensation reconciliation decision data models.

The live AEAT wallet is external state. Local Modelo 303 recurrence is
internal reconstruction. These pure typed records describe the evidence
sources, the explicit taxpayer override, and the effective binding
decision consumed by Modelo 303 calculation. They carry no adapter or
application coupling: the orchestration that produces them from live
wallet observations and prior-filing recurrence stays in the
application layer.

The :class:`IvaCompensationReconciliationDecision` model encodes the
regulatory invariant relating ``selected_authority`` to
``selected_amount`` and the blocked-wallet refusal in its
``model_validator``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.time import now
from ._errors import IvaCompensationReconciliationInputError, IvaWalletReconciliationError

DEFAULT_MAX_WALLET_AGE_DAYS: Final[int] = 31
_FILED_HISTORY_OBSERVATION: Final = "filed_history_observation"
_AEAT_FILED_HISTORY_SOURCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_iva_compensation_history",
        _FILED_HISTORY_OBSERVATION,
    },
)

type IvaCompensationAuthority = Literal[
    "aeat_wallet",
    "taxpayer_override",
    "filed_history",
    "local_recurrence",
    "missing",
]
type IvaCompensationAuthorityKind = Literal[
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
    "first_period_zero",
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

    source_kind: IvaCompensationAuthorityKind
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    source_locator: str = Field(min_length=1, max_length=1024)
    captured_at: datetime | None = None
    source_modelo: str | None = Field(default=None, min_length=1, max_length=8)
    source_filing_year: int | None = Field(default=None, ge=2000, le=2099)
    source_periods: tuple[Period, ...] = ()

    @model_validator(mode="after")
    def _source_period_years_match(self) -> IvaCompensationAuthoritySource:
        if not self.source_periods:
            return self
        if self.source_filing_year is None:
            raise ValueError("source_filing_year is required when source_periods are present")
        if any(period.filing_year != self.source_filing_year for period in self.source_periods):
            raise ValueError("source_periods filing_year values must match source_filing_year")
        return self


class IvaCompensationReconciliationDecision(BaseModel):
    """Effective prior-compensation binding decision for Modelo 303.

    This record is persisted and replayed by calculation. A live wallet
    fetch creates evidence; this decision says whether that evidence can
    safely drive the binding or whether review is required.
    """

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    target_year: int = Field(ge=2000, le=2099)
    target_period: Period
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
        if self.target_period.filing_year != self.target_year:
            raise ValueError("target_period.filing_year must match target_year")
        if self.selected_authority != "missing" and self.selected_amount is None:
            raise ValueError("selected_amount is required unless selected_authority is 'missing'")
        if self.selected_authority == "missing" and self.selected_amount is not None:
            raise ValueError("selected_amount must be absent when selected_authority is 'missing'")
        if self.blocked and self.selected_authority == "aeat_wallet":
            raise ValueError("blocked wallet divergence cannot select aeat_wallet for calculation")
        return self


@runtime_checkable
class IvaCompensationWalletObservationProtocol(Protocol):
    """Structural port for an AEAT IVA-compensation wallet observation.

    Lets the reconciliation decision logic stay in the domain without importing
    the Sede adapter record that produces it; the adapter's
    ``IvaCompensationWalletObservation`` satisfies this protocol structurally.
    Members are read-only (the reconciliation only reads them), which keeps the
    protocol covariant so a record whose attributes are subtypes (e.g. an
    ``AnyHttpUrl`` ``source_url``) still satisfies it.
    """

    @property
    def taxpayer_nif(self) -> str: ...
    @property
    def target_year(self) -> int: ...
    @property
    def target_period(self) -> Period: ...
    @property
    def total_pending(self) -> Decimal: ...
    @property
    def source_url(self) -> object: ...
    @property
    def captured_at(self) -> datetime: ...


@runtime_checkable
class LocalIvaCompensationRecurrenceProtocol(Protocol):
    """Structural port for a local Modelo 303 recurrence record.

    The application's ``LocalIvaCompensationRecurrence`` satisfies this protocol
    structurally; the domain projects it into an authority source without
    importing the application layer. Members are read-only for covariance.
    """

    @property
    def amount(self) -> Decimal: ...
    @property
    def binding_id(self) -> object: ...
    @property
    def source_kind(self) -> str: ...
    @property
    def source_modelo(self) -> object: ...
    @property
    def source_filing_year(self) -> int: ...
    @property
    def source_periods(self) -> tuple[Period, ...]: ...
    @property
    def resolved_at(self) -> datetime: ...


@dataclass(frozen=True)
class _ReconciliationContext:
    taxpayer_nif: str
    target_year: int
    target_period: Period
    wallet_amount: Decimal | None
    local_recurrence_amount: Decimal | None
    override: IvaCompensationOverride | None
    when: datetime
    wallet_captured_at: datetime | None
    stale_wallet: bool
    authority_sources: tuple[IvaCompensationAuthoritySource, ...]


def reconcile_iva_compensation_wallet(
    *,
    taxpayer_nif: str,
    target_year: int,
    target_period: Period,
    wallet: IvaCompensationWalletObservationProtocol | None,
    local_recurrence_amount: Decimal | None,
    local_recurrence_source: IvaCompensationAuthoritySource | None = None,
    override: IvaCompensationOverride | None = None,
    decided_at: datetime | None = None,
    max_wallet_age_days: int = DEFAULT_MAX_WALLET_AGE_DAYS,
    is_first_iva_period: bool = False,
) -> IvaCompensationReconciliationDecision:
    """Return the :class:`IvaCompensationReconciliationDecision` for casilla ``110``."""
    if wallet is not None:
        validate_wallet_matches_snapshot(
            wallet,
            taxpayer_nif=taxpayer_nif,
            target_year=target_year,
            target_period=target_period,
        )
    when = decided_at if decided_at is not None else now()
    ctx = _ReconciliationContext(
        taxpayer_nif=taxpayer_nif,
        target_year=target_year,
        target_period=target_period,
        wallet_amount=wallet.total_pending if wallet is not None else None,
        local_recurrence_amount=local_recurrence_amount,
        override=override,
        when=when,
        wallet_captured_at=wallet.captured_at if wallet is not None else None,
        stale_wallet=_is_wallet_stale(
            wallet.captured_at if wallet is not None else None,
            when,
            max_wallet_age_days,
        ),
        authority_sources=_authority_sources(
            wallet=wallet,
            local_recurrence_amount=local_recurrence_amount,
            local_recurrence_source=local_recurrence_source,
            override=override,
        ),
    )
    if ctx.override is not None:
        return _override_reconciliation_decision(ctx)

    if is_first_iva_period:
        first_period_decision = _first_period_zero_decision(ctx)
        if first_period_decision is not None:
            return first_period_decision

    if ctx.wallet_amount is None:
        return _missing_wallet_decision(ctx, local_recurrence_source=local_recurrence_source)

    if ctx.stale_wallet:
        return _stale_wallet_decision(ctx)

    return _fresh_wallet_decision(ctx)


def _decision(
    ctx: _ReconciliationContext,
    *,
    selected_authority: IvaCompensationAuthority,
    selected_amount: Decimal | None,
    wallet_amount: Decimal | None,
    local_recurrence_amount: Decimal | None,
    override_amount: Decimal | None,
    divergence: IvaCompensationDivergence,
    blocked: bool,
    stale_wallet: bool,
    reason: str,
    wallet_captured_at: datetime | None,
) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=ctx.taxpayer_nif,
        target_year=ctx.target_year,
        target_period=ctx.target_period,
        selected_authority=selected_authority,
        selected_amount=selected_amount,
        wallet_amount=wallet_amount,
        local_recurrence_amount=local_recurrence_amount,
        override_amount=override_amount,
        divergence=divergence,
        blocked=blocked,
        stale_wallet=stale_wallet,
        reason=reason,
        wallet_captured_at=wallet_captured_at,
        authority_sources=ctx.authority_sources,
        decided_at=ctx.when,
    )


def _override_reconciliation_decision(ctx: _ReconciliationContext) -> IvaCompensationReconciliationDecision:
    assert ctx.override is not None
    return _decision(
        ctx,
        selected_authority="taxpayer_override",
        selected_amount=ctx.override.amount,
        wallet_amount=ctx.wallet_amount,
        local_recurrence_amount=ctx.local_recurrence_amount,
        override_amount=ctx.override.amount,
        divergence="override",
        blocked=False,
        stale_wallet=ctx.stale_wallet,
        reason=ctx.override.reason,
        wallet_captured_at=ctx.wallet_captured_at,
    )


def _first_period_zero_decision(ctx: _ReconciliationContext) -> IvaCompensationReconciliationDecision | None:
    effective_zero = Decimal("0")
    if ctx.wallet_amount is not None and ctx.wallet_amount == effective_zero and not ctx.stale_wallet:
        return _decision(
            ctx,
            selected_authority="aeat_wallet",
            selected_amount=effective_zero,
            wallet_amount=effective_zero,
            local_recurrence_amount=ctx.local_recurrence_amount,
            override_amount=None,
            divergence="first_period_zero",
            blocked=False,
            stale_wallet=False,
            reason=(
                "First registered IVA filing period: "
                "iva.compensacion-pendiente-periodos-anteriores is zero per LIVA art. 99.5. "
                "No prior compensation balance exists; zero is legally certain and non-blocking."
            ),
            wallet_captured_at=ctx.wallet_captured_at,
        )
    local_recurrence_is_zero = ctx.local_recurrence_amount is not None and ctx.local_recurrence_amount == effective_zero
    if ctx.wallet_amount is None and local_recurrence_is_zero:
        return _decision(
            ctx,
            selected_authority="local_recurrence",
            selected_amount=effective_zero,
            wallet_amount=None,
            local_recurrence_amount=effective_zero,
            override_amount=None,
            divergence="first_period_zero",
            blocked=False,
            stale_wallet=False,
            reason=(
                "First registered IVA filing period: seeded-zero local record per LIVA art. 99.5. "
                "No prior compensation balance exists; zero is legally certain and non-blocking."
            ),
            wallet_captured_at=None,
        )
    return None


def _missing_wallet_decision(
    ctx: _ReconciliationContext,
    *,
    local_recurrence_source: IvaCompensationAuthoritySource | None,
) -> IvaCompensationReconciliationDecision:
    if ctx.local_recurrence_amount is None:
        return _decision(
            ctx,
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
        )
    if _is_filed_history_source(local_recurrence_source):
        return _decision(
            ctx,
            selected_authority="filed_history",
            selected_amount=ctx.local_recurrence_amount,
            wallet_amount=None,
            local_recurrence_amount=ctx.local_recurrence_amount,
            override_amount=None,
            divergence="filed_history_only",
            blocked=True,
            stale_wallet=False,
            reason=(
                "Direct AEAT wallet/cartera evidence is unavailable; AEAT filed-history-derived recurrence "
                "is recorded as fallback evidence but requires explicit taxpayer override before automatic output."
            ),
            wallet_captured_at=None,
        )
    return _decision(
        ctx,
        selected_authority="local_recurrence",
        selected_amount=ctx.local_recurrence_amount,
        wallet_amount=None,
        local_recurrence_amount=ctx.local_recurrence_amount,
        override_amount=None,
        divergence="wallet_missing",
        blocked=True,
        stale_wallet=False,
        reason=(
            "AEAT wallet is unavailable; local recurrence is lower-confidence fallback evidence and requires "
            "explicit taxpayer override before automatic output."
        ),
        wallet_captured_at=None,
    )


def _stale_wallet_decision(ctx: _ReconciliationContext) -> IvaCompensationReconciliationDecision:
    assert ctx.wallet_amount is not None
    if ctx.local_recurrence_amount is None:
        return _decision(
            ctx,
            selected_authority="missing",
            selected_amount=None,
            wallet_amount=ctx.wallet_amount,
            local_recurrence_amount=None,
            override_amount=None,
            divergence="wallet_stale",
            blocked=True,
            stale_wallet=True,
            reason="AEAT wallet observation is stale and no local recurrence fallback is available.",
            wallet_captured_at=ctx.wallet_captured_at,
        )
    return _decision(
        ctx,
        selected_authority="local_recurrence",
        selected_amount=ctx.local_recurrence_amount,
        wallet_amount=ctx.wallet_amount,
        local_recurrence_amount=ctx.local_recurrence_amount,
        override_amount=None,
        divergence="wallet_stale",
        blocked=True,
        stale_wallet=True,
        reason=(
            "AEAT wallet observation is stale; local recurrence is lower-confidence fallback evidence and "
            "requires explicit taxpayer override before automatic output."
        ),
        wallet_captured_at=ctx.wallet_captured_at,
    )


def _fresh_wallet_decision(ctx: _ReconciliationContext) -> IvaCompensationReconciliationDecision:
    assert ctx.wallet_amount is not None
    if ctx.local_recurrence_amount is not None and ctx.wallet_amount != ctx.local_recurrence_amount:
        divergence: IvaCompensationDivergence = (
            "wallet_higher" if ctx.wallet_amount > ctx.local_recurrence_amount else "wallet_lower"
        )
        return _decision(
            ctx,
            selected_authority="missing",
            selected_amount=None,
            wallet_amount=ctx.wallet_amount,
            local_recurrence_amount=ctx.local_recurrence_amount,
            override_amount=None,
            divergence=divergence,
            blocked=True,
            stale_wallet=False,
            reason="AEAT wallet and local recurrence diverge; review is required before automatic output.",
            wallet_captured_at=ctx.wallet_captured_at,
        )
    reason = "Using latest valid AEAT wallet observation for Modelo 303 prior compensation."
    if ctx.local_recurrence_amount is None:
        reason = (
            "Using latest valid AEAT wallet observation for Modelo 303 prior compensation; "
            "no local prior-filing recurrence was available for cross-check."
        )
    return _decision(
        ctx,
        selected_authority="aeat_wallet",
        selected_amount=ctx.wallet_amount,
        wallet_amount=ctx.wallet_amount,
        local_recurrence_amount=ctx.local_recurrence_amount,
        override_amount=None,
        divergence="wallet_only" if ctx.local_recurrence_amount is None else "match",
        blocked=False,
        stale_wallet=False,
        reason=reason,
        wallet_captured_at=ctx.wallet_captured_at,
    )


def _authority_sources(
    *,
    wallet: IvaCompensationWalletObservationProtocol | None,
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
            ),
        )
    if local_recurrence_amount is not None:
        recurrence_source = local_recurrence_source or IvaCompensationAuthoritySource(
            source_kind="local_recurrence",
            amount=local_recurrence_amount,
            source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
        )
        if recurrence_source.source_kind == _FILED_HISTORY_OBSERVATION:
            sources.append(
                IvaCompensationAuthoritySource(
                    source_kind="local_recurrence",
                    amount=local_recurrence_amount,
                    source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
                    captured_at=recurrence_source.captured_at,
                    source_modelo=recurrence_source.source_modelo,
                    source_filing_year=recurrence_source.source_filing_year,
                    source_periods=recurrence_source.source_periods,
                ),
            )
        sources.append(recurrence_source)
    if override is not None:
        sources.append(
            IvaCompensationAuthoritySource(
                source_kind="taxpayer_override",
                amount=override.amount,
                source_locator=override.evidence_locator,
                captured_at=override.recorded_at,
            ),
        )
    return tuple(sources)


def _is_filed_history_source(source: IvaCompensationAuthoritySource | None) -> bool:
    return source is not None and source.source_kind == _FILED_HISTORY_OBSERVATION


def local_recurrence_authority_source(
    recurrence: LocalIvaCompensationRecurrenceProtocol | None,
) -> IvaCompensationAuthoritySource | None:
    """Project a local Modelo 303 recurrence record into an :class:`IvaCompensationAuthoritySource`."""
    if recurrence is None:
        return None
    amount = Decimal(recurrence.amount)
    binding_id = str(recurrence.binding_id)
    source_modelo = str(recurrence.source_modelo)
    source_filing_year = int(recurrence.source_filing_year)
    source_periods = tuple(recurrence.source_periods)
    resolved_at = recurrence.resolved_at
    source_kind: IvaCompensationAuthorityKind = (
        _FILED_HISTORY_OBSERVATION if recurrence.source_kind in _AEAT_FILED_HISTORY_SOURCE_KINDS else "local_recurrence"
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


def validate_wallet_matches_snapshot(
    wallet: IvaCompensationWalletObservationProtocol,
    *,
    taxpayer_nif: str,
    target_year: int,
    target_period: Period,
) -> None:
    """Refuse a wallet observation that does not match the requested Modelo 303 target."""
    if wallet.taxpayer_nif != taxpayer_nif:
        raise IvaCompensationReconciliationInputError(
            "IVA wallet observation taxpayer does not match the requested taxpayer",
        )
    if wallet.target_year != target_year or wallet.target_period != target_period:
        raise IvaCompensationReconciliationInputError(
            "IVA wallet observation target does not match the Modelo 303 snapshot",
        )


def _is_wallet_stale(
    captured_at: datetime | None,
    decided_at: datetime,
    max_wallet_age_days: int,
) -> bool:
    if captured_at is None:
        return False
    if max_wallet_age_days < 0:
        raise IvaWalletReconciliationError("max_wallet_age_days must be non-negative")
    return decided_at - captured_at > timedelta(days=max_wallet_age_days)


__all__ = [
    "DEFAULT_MAX_WALLET_AGE_DAYS",
    "IvaCompensationAuthority",
    "IvaCompensationAuthorityKind",
    "IvaCompensationAuthoritySource",
    "IvaCompensationDivergence",
    "IvaCompensationOverride",
    "IvaCompensationReconciliationDecision",
    "IvaCompensationWalletObservationProtocol",
    "LocalIvaCompensationRecurrenceProtocol",
    "local_recurrence_authority_source",
    "reconcile_iva_compensation_wallet",
    "validate_wallet_matches_snapshot",
]
