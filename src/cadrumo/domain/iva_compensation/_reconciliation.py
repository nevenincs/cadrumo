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
from enum import StrEnum
from typing import Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.filing_year import FilingYear
from ...core.time import UtcInstant, now
from .errors import IvaCompensationReconciliationInputError, IvaWalletReconciliationError

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
    "filed_history_zero",
    "local_recurrence_zero",
    "missing",
]


class IvaCompensationDecisionReason(StrEnum):
    """Locale-neutral identity explaining an IVA compensation decision."""

    TAXPAYER_OVERRIDE = "taxpayer_override"
    FIRST_PERIOD_ZERO_AEAT_WALLET = "first_period_zero_aeat_wallet"
    FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED = "first_period_zero_activity_start_uncontrasted"
    FIRST_PERIOD_ZERO_LOCAL_RECURRENCE = "first_period_zero_local_recurrence"
    LOCAL_EVIDENCE_UNREADABLE = "local_evidence_unreadable"
    NO_USABLE_AUTHORITY = "no_usable_authority"
    FILED_HISTORY_ZERO = "filed_history_zero"
    FILED_HISTORY_REQUIRES_OVERRIDE = "filed_history_requires_override"
    LOCAL_RECURRENCE_ZERO = "local_recurrence_zero"
    LOCAL_RECURRENCE_REQUIRES_OVERRIDE = "local_recurrence_requires_override"
    STALE_WALLET_NO_LOCAL_RECURRENCE = "stale_wallet_no_local_recurrence"
    STALE_WALLET_LOCAL_RECURRENCE_REQUIRES_OVERRIDE = "stale_wallet_local_recurrence_requires_override"
    WALLET_LOCAL_RECURRENCE_DIVERGENCE = "wallet_local_recurrence_divergence"
    AEAT_WALLET_VALIDATED = "aeat_wallet_validated"
    AEAT_WALLET_UNCROSSCHECKED = "aeat_wallet_uncrosschecked"
    CALLER_ZERO_MATCHES_LOCAL_AUTHORITY = "caller_zero_matches_local_authority"


class IvaCompensationOverride(BaseModel):
    """Explicit taxpayer override for Modelo 303 prior compensation."""

    model_config = _STRICT_FROZEN

    amount: Decimal = Field(ge=Decimal("0"))
    operator_explanation: str = Field(min_length=1, max_length=1024)
    evidence_locator: str = Field(min_length=1, max_length=1024)
    recorded_at: UtcInstant


class IvaCompensationAuthoritySource(BaseModel):
    """One evidence source considered by an IVA compensation decision."""

    model_config = _STRICT_FROZEN

    source_kind: IvaCompensationAuthorityKind
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    source_locator: str = Field(min_length=1, max_length=1024)
    captured_at: UtcInstant | None = None
    source_modelo: str | None = Field(default=None, min_length=1, max_length=8)
    source_filing_year: FilingYear | None = None
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
    target_year: FilingYear
    target_period: Period
    selected_authority: IvaCompensationAuthority
    selected_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    wallet_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    local_recurrence_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    override_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    divergence: IvaCompensationDivergence
    blocked: bool
    stale_wallet: bool
    reason_identity: IvaCompensationDecisionReason
    operator_explanation: str | None = Field(default=None, min_length=1, max_length=1024)
    #: Whether the caller found a prior local record and could not read it as
    #: prior-compensation evidence. Both that situation and a genuinely absent
    #: record leave every other field on this model identical -- same
    #: divergence, same absent amounts, same blocked -- so without this the
    #: difference exists only inside ``reason``'s free text and no consumer can
    #: key on it. A refusal that wants to tell an operator which one happened
    #: has nothing else to read.
    local_evidence_found_but_unusable: bool = False
    wallet_captured_at: UtcInstant | None = None
    authority_sources: tuple[IvaCompensationAuthoritySource, ...] = ()
    decided_at: UtcInstant

    @field_validator("reason_identity", mode="before")
    @classmethod
    def _parse_reason_identity(cls, value: object) -> IvaCompensationDecisionReason:
        """Parse encrypted JSON and direct construction into the closed identity."""
        return IvaCompensationDecisionReason(value)

    @model_validator(mode="after")
    def _validate_selected_amount(self) -> IvaCompensationReconciliationDecision:
        _validate_reconciliation_target_and_amount(self)
        _validate_reconciliation_blocked_authority(self)
        _validate_reconciliation_operator_explanation(self)
        return self


def _validate_reconciliation_target_and_amount(decision: IvaCompensationReconciliationDecision) -> None:
    if decision.target_period.filing_year != decision.target_year:
        raise ValueError("target_period.filing_year must match target_year")
    if decision.selected_authority != "missing" and decision.selected_amount is None:
        raise ValueError("selected_amount is required unless selected_authority is 'missing'")
    if decision.selected_authority == "missing" and decision.selected_amount is not None:
        raise ValueError("selected_amount must be absent when selected_authority is 'missing'")


def _validate_reconciliation_blocked_authority(decision: IvaCompensationReconciliationDecision) -> None:
    if decision.blocked and decision.selected_authority == "aeat_wallet":
        raise ValueError("blocked wallet divergence cannot select aeat_wallet for calculation")


def _validate_reconciliation_operator_explanation(decision: IvaCompensationReconciliationDecision) -> None:
    if decision.reason_identity is IvaCompensationDecisionReason.TAXPAYER_OVERRIDE:
        if decision.operator_explanation is None:
            raise ValueError("taxpayer_override decisions require operator_explanation")
    elif decision.operator_explanation is not None:
        raise ValueError("operator_explanation is allowed only for taxpayer_override decisions")


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
    when: UtcInstant
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
    local_evidence_found_but_unusable: bool = False,
) -> IvaCompensationReconciliationDecision:
    """Return the :class:`IvaCompensationReconciliationDecision` for casilla ``110``.

    ``local_evidence_found_but_unusable`` is a caller-asserted fact, in the same
    shape as ``is_first_iva_period``: the caller knows whether it FOUND a prior
    record and failed to interpret it, and this function cannot derive that from
    an absent amount. Without it the no-authority outcome states that nothing is
    available, which is false for that caller and sends an operator looking for
    evidence they already hold.
    """
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
        return _missing_wallet_decision(
            ctx,
            local_recurrence_source=local_recurrence_source,
            local_evidence_found_but_unusable=local_evidence_found_but_unusable,
        )

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
    reason_identity: IvaCompensationDecisionReason,
    operator_explanation: str | None = None,
    wallet_captured_at: datetime | None,
    local_evidence_found_but_unusable: bool = False,
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
        reason_identity=reason_identity,
        operator_explanation=operator_explanation,
        local_evidence_found_but_unusable=local_evidence_found_but_unusable,
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
        reason_identity=IvaCompensationDecisionReason.TAXPAYER_OVERRIDE,
        operator_explanation=ctx.override.operator_explanation,
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
            reason_identity=IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_AEAT_WALLET,
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
            reason_identity=IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_LOCAL_RECURRENCE,
            wallet_captured_at=None,
        )
    return None


def _missing_wallet_decision(
    ctx: _ReconciliationContext,
    *,
    local_recurrence_source: IvaCompensationAuthoritySource | None,
    local_evidence_found_but_unusable: bool = False,
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
            reason_identity=(
                IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE
                if local_evidence_found_but_unusable
                else IvaCompensationDecisionReason.NO_USABLE_AUTHORITY
            ),
            local_evidence_found_but_unusable=local_evidence_found_but_unusable,
            wallet_captured_at=None,
        )
    if _is_filed_history_source(local_recurrence_source):
        if ctx.local_recurrence_amount == Decimal("0"):
            return _decision(
                ctx,
                selected_authority="filed_history",
                selected_amount=Decimal("0"),
                wallet_amount=None,
                local_recurrence_amount=Decimal("0"),
                override_amount=None,
                divergence="filed_history_zero",
                blocked=False,
                stale_wallet=False,
                reason_identity=IvaCompensationDecisionReason.FILED_HISTORY_ZERO,
                wallet_captured_at=None,
            )
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
            reason_identity=IvaCompensationDecisionReason.FILED_HISTORY_REQUIRES_OVERRIDE,
            wallet_captured_at=None,
        )
    if ctx.local_recurrence_amount == Decimal("0"):
        return _decision(
            ctx,
            selected_authority="local_recurrence",
            selected_amount=Decimal("0"),
            wallet_amount=None,
            local_recurrence_amount=Decimal("0"),
            override_amount=None,
            divergence="local_recurrence_zero",
            blocked=False,
            stale_wallet=False,
            reason_identity=IvaCompensationDecisionReason.LOCAL_RECURRENCE_ZERO,
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
        reason_identity=IvaCompensationDecisionReason.LOCAL_RECURRENCE_REQUIRES_OVERRIDE,
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
            reason_identity=IvaCompensationDecisionReason.STALE_WALLET_NO_LOCAL_RECURRENCE,
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
        reason_identity=IvaCompensationDecisionReason.STALE_WALLET_LOCAL_RECURRENCE_REQUIRES_OVERRIDE,
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
            reason_identity=IvaCompensationDecisionReason.WALLET_LOCAL_RECURRENCE_DIVERGENCE,
            wallet_captured_at=ctx.wallet_captured_at,
        )
    reason = IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED
    if ctx.local_recurrence_amount is None:
        reason = IvaCompensationDecisionReason.AEAT_WALLET_UNCROSSCHECKED
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
        reason_identity=reason,
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
    source_locator = str(
        getattr(recurrence, "source_locator", None) or f"binding:{binding_id}",
    )
    source_kind: IvaCompensationAuthorityKind = (
        _FILED_HISTORY_OBSERVATION if recurrence.source_kind in _AEAT_FILED_HISTORY_SOURCE_KINDS else "local_recurrence"
    )
    return IvaCompensationAuthoritySource(
        source_kind=source_kind,
        amount=amount,
        source_locator=source_locator,
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
            translated_message="errors.refused.reconciliation_evidence_invalid",
            context={"taxpayer_matches_request": False},
        )
    if wallet.target_year != target_year or wallet.target_period != target_period:
        raise IvaCompensationReconciliationInputError(
            translated_message="errors.refused.reconciliation_evidence_invalid",
            context={
                "wallet_target_year": str(wallet.target_year),
                "wallet_target_period": str(wallet.target_period),
                "snapshot_target_year": str(target_year),
                "snapshot_target_period": str(target_period),
            },
        )


def _is_wallet_stale(
    captured_at: datetime | None,
    decided_at: datetime,
    max_wallet_age_days: int,
) -> bool:
    if captured_at is None:
        return False
    if max_wallet_age_days < 0:
        raise IvaWalletReconciliationError(
            translated_message="errors.refused.refused_iva_wallet_reconciliation_invariant",
            context={"max_wallet_age_days": str(max_wallet_age_days), "non_negative": False},
        )
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
