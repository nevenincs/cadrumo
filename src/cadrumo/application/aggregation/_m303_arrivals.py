"""Canonical evidence arrivals for Modelo 303 informational producer facts.

This module deliberately composes the two owned fact stores instead of adding
profile flags: the IVA aggregation's period-stamped observation stream proves
whether the taxpayer received supplier-regime cash-accounting operations, and
the cross-period prorrata register proves an option or revocation transition.
The filing snapshot consumes these immutable arrivals as facts; it does not
re-scan ledger rows or reconstruct register state.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    Period,
    ProrrataEspecialTransitionKind,
    ProrrataRegisterRegime,
    StandardPeriodCode,
)
from ...domain.calculations.registry import IvaLedgerObservation
from ...domain.iva import IvaCashAccountingTreatment
from ...domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
)
from ._errors import AggregationValidationError, t
from ._iva_ledger import IvaLedgerAggregation

# Modelo 303's 2026 record design, DP30301 Note 6: the option and revocation
# fields are blank before the annual final liquidation and carry SI/NO only in
# 4T (quarterly) or 12 (monthly).  An annual ``0A`` is not a Modelo 303 filing
# period, so it deliberately does not belong to this closed set.
_M303_PRORRATA_TRANSITION_FINAL_PERIODS: Final[frozenset[StandardPeriodCode]] = frozenset(
    {StandardPeriodCode.Q4, StandardPeriodCode.DEC}
)


class M303SupplierRegimeArrival(BaseModel):
    """Period-specific evidence that the taxpayer received supplier-regime operations."""

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    recipient_of_cash_accounting_operations: bool
    source_ledger_ids: tuple[str, ...]

    @field_validator("source_ledger_ids")
    @classmethod
    def _source_ledger_ids_are_unique_and_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not ledger_id.strip() for ledger_id in value):
            raise AggregationValidationError(t("supplier-regime arrival contains a blank ledger identity"))
        if len(value) != len(set(value)):
            raise AggregationValidationError(t("supplier-regime arrival contains duplicate ledger evidence"))
        return value

    @model_validator(mode="after")
    def _recipient_fact_matches_its_evidence(self) -> M303SupplierRegimeArrival:
        if self.recipient_of_cash_accounting_operations != bool(self.source_ledger_ids):
            raise AggregationValidationError(
                t("recipient-of-cash-accounting fact must agree with its supplier-regime ledger evidence")
            )
        return self


class M303ProrrataTransitionArrival(BaseModel):
    """Period-specific prorrata-especial option or revocation evidence.

    ``transition`` is absent only when the register records no transition for
    the filing year.  When present, every entry in ``register_evidence`` names
    that one transition, so the two Modelo 303 choices can never arrive true
    together.
    """

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    transition: ProrrataEspecialTransitionKind | None
    register_evidence: tuple[ProrrataRegisterEntry, ...]

    @property
    def is_applicable(self) -> bool:
        """Whether DP30301's option/revocation slots apply to this filing period."""
        return self.period.standard_code in _M303_PRORRATA_TRANSITION_FINAL_PERIODS

    @model_validator(mode="after")
    def _transition_matches_register_evidence(self) -> M303ProrrataTransitionArrival:
        if not self.is_applicable:
            if self.transition is not None or self.register_evidence:
                raise AggregationValidationError(
                    t("prorrata transition evidence is applicable only in Modelo 303 final periods 4T or 12")
                )
            return self
        if self.transition is None:
            if self.register_evidence:
                raise AggregationValidationError(t("prorrata transition evidence requires a declared transition"))
            return self
        if not self.register_evidence:
            raise AggregationValidationError(t("prorrata transition arrival is missing register evidence"))
        for entry in self.register_evidence:
            if entry.ejercicio != self.period.filing_year:
                raise AggregationValidationError(
                    t("prorrata transition register evidence belongs to another filing year")
                )
            if entry.especial_transition is None:
                raise AggregationValidationError(
                    t("prorrata transition arrival contains an entry without transition evidence")
                )
            if entry.especial_transition.kind != self.transition:
                raise AggregationValidationError(
                    t("prorrata transition arrival contains contradictory transition evidence")
                )
        return self


def resolve_m303_supplier_regime_arrival(
    *,
    period: Period,
    iva_aggregation: IvaLedgerAggregation,
) -> M303SupplierRegimeArrival:
    """Derive the recipient fact solely from the canonical IVA observation set.

    This fact records supplier-regime participation in the filing period, not a
    monetary box contribution.  It therefore deliberately spans both the
    operation-information and settlement projection roles, while retaining a
    stable one-ledger-id evidence set when one operation has several partial
    settlements in the same period.
    """
    if iva_aggregation.period != period:
        raise AggregationValidationError(t("supplier-regime IVA observations do not match the requested filing period"))
    observations: Sequence[IvaLedgerObservation] = iva_aggregation.observations
    wrong_period_ledger_ids = tuple(
        observation.ledger_id for observation in observations if not period.contains(observation.transaction_date)
    )
    if wrong_period_ledger_ids:
        raise AggregationValidationError(
            t(
                "supplier-regime IVA aggregation contains observations outside the requested filing period: "
                f"{wrong_period_ledger_ids}"
            )
        )
    source_ledger_ids = tuple(
        dict.fromkeys(
            observation.ledger_id
            for observation in observations
            if observation.cash_accounting_treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME
        )
    )
    return M303SupplierRegimeArrival(
        period=period,
        recipient_of_cash_accounting_operations=bool(source_ledger_ids),
        source_ledger_ids=source_ledger_ids,
    )


def _m303_prorrata_transition_evidence(
    *,
    period: Period,
    prorrata_register: ProrrataRegister,
) -> tuple[ProrrataRegisterEntry, ...]:
    entries = prorrata_register.entries_for_ejercicio(period.filing_year)
    return tuple(entry for entry in entries if entry.especial_transition is not None)


def _m303_prorrata_transition_kind(
    evidence: tuple[ProrrataRegisterEntry, ...],
) -> ProrrataEspecialTransitionKind | None:
    transition_kinds: set[ProrrataEspecialTransitionKind] = {
        entry.especial_transition.kind for entry in evidence if entry.especial_transition is not None
    }
    if len(transition_kinds) > 1:
        raise AggregationValidationError(t("prorrata register carries contradictory option and revocation evidence"))
    return next(iter(transition_kinds), None)


def _validate_m303_prorrata_revocation_evidence(
    *,
    period: Period,
    prorrata_register: ProrrataRegister,
    evidence: tuple[ProrrataRegisterEntry, ...],
) -> None:
    invalid_revocation_sectors: list[str | None] = []
    for entry in evidence:
        prior_entry = prorrata_register.entry_for(period.filing_year - 1, sector_id=entry.sector_id)
        if prior_entry is None or prior_entry.regime is not ProrrataRegisterRegime.ESPECIAL:
            invalid_revocation_sectors.append(entry.sector_id)
    if invalid_revocation_sectors:
        raise AggregationValidationError(
            t(
                "prorrata especial revocation evidence has no prior-year especial register state for sector(s) "
                f"{tuple(invalid_revocation_sectors)}"
            )
        )


def resolve_m303_prorrata_transition_arrival(
    *,
    period: Period,
    prorrata_register: ProrrataRegister,
) -> M303ProrrataTransitionArrival:
    """Resolve the final-period special-prorrata transition from the register.

    The current registro records the year-level legal transition. DP30301 Note
    6 makes the two filing slots inapplicable before the year's final Modelo
    303 period, so those periods preserve ``None`` rather than manufacturing a
    false ``NO`` answer from the absence of evidence.
    """
    if period.standard_code not in _M303_PRORRATA_TRANSITION_FINAL_PERIODS:
        return M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=())
    if not prorrata_register.has_complete_current_entry_coverage(period.filing_year):
        raise AggregationValidationError(
            t("prorrata register lacks a complete explicit current-year declaration for Modelo 303")
        )
    evidence = _m303_prorrata_transition_evidence(period=period, prorrata_register=prorrata_register)
    transition = _m303_prorrata_transition_kind(evidence)
    if transition is ProrrataEspecialTransitionKind.REVOCACION:
        _validate_m303_prorrata_revocation_evidence(
            period=period,
            prorrata_register=prorrata_register,
            evidence=evidence,
        )
    return M303ProrrataTransitionArrival(
        period=period,
        transition=transition,
        register_evidence=evidence,
    )


__all__ = [
    "M303ProrrataTransitionArrival",
    "M303SupplierRegimeArrival",
    "resolve_m303_prorrata_transition_arrival",
    "resolve_m303_supplier_regime_arrival",
]
