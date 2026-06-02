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

from datetime import datetime
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")

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


__all__ = [
    "IvaCompensationAuthority",
    "IvaCompensationAuthoritySource",
    "IvaCompensationAuthoritySourceKind",
    "IvaCompensationDivergence",
    "IvaCompensationOverride",
    "IvaCompensationReconciliationDecision",
]
