"""Modelo 303 refund (devolución) disposition eligibility.

A negative Modelo 303 result may be elected as a refund — fichero "Tipo de
declaración" code ``D`` (solicitud de devolución) — only when the taxpayer is
inscribed in the Registro de devolución mensual (REDEME, art. 30 RD 1624/1992),
which makes a monthly refund available *every* period, OR when the period is the
last filing period of the year (the annual liquidación). Outside those two cases
the only lawful negative disposition is compensación — code ``C``, a credit
carried forward. The operator may always carry forward; the refund is the gated
election.

This module is the ONE owner of the question "does this Modelo 303 period allow
a refund". :func:`resolve_refund_eligibility` answers it; the served form
header, the export's refund choice and the cross-period carry all consume that
answer and none of them re-derives the last period or re-reads REDEME.

It is pure: a predicate over the registry's own declaration of which periods are
final (:class:`RefundEligibilityPolicy`, which the caller passes in from the
pinned authority) and over the typed REDEME state. It raises no error, resolves
no locale and touches no adapter, so it has no dependency on the
result-disposition serialization framework or on operator message catalogues; a
consumer layers the operator-facing election, wording and refusal on top. The
``basis`` it returns is a machine code, not operator-facing prose.

Legal basis: Ley 37/1992 (LIVA) art. 115.Uno — the refund of the balance
standing at 31 December is requested "en la autoliquidación correspondiente al
último período de liquidación de dicho año"; art. 115.Dos extends it to the end
of every period for the taxpayers of art. 116, who opt into the monthly
procedure whose "período de liquidación [...] coincidirá con el mes natural";
RD 1624/1992 (RIVA) art. 30 governs the Registro de devolución mensual. The
legal refs each outcome rests on are read from the registry's own declaration,
never held here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.period import Period
from ..calculations.registry.refund_eligibility import (
    RefundEligibilityPolicy,
    resolve_refund_eligibility_policy_for_period,
)

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

#: The filing cadence whose declared final period the registry couples to the
#: REDEME regime. Fact ``iva-refund-eligibility-policy`` declares it: the
#: monthly final period's description states that "monthly refund eligibility is
#: governed by the REDEME regime under RIVA article 30", so a REDEME-based
#: outcome rests on the legal refs that definition carries.
_MONTHLY_CADENCE = "monthly"


class RedemeEnrolmentState(StrEnum):
    """The taxpayer's answer about inscription in the Registro de devolución mensual.

    ``UNSTATED`` is kept apart from ``NOT_ENROLLED`` because a taxpayer who has
    not answered is not a taxpayer who has answered no: reading an unanswered
    inscription as a no would rule them out of a refund they are entitled to
    under LIVA art. 115.Dos without their ever having been asked.
    """

    ENROLLED = "enrolled"
    NOT_ENROLLED = "not_enrolled"
    UNSTATED = "unstated"


def redeme_enrolment_state(declared: bool | None) -> RedemeEnrolmentState:
    """Project a profile's three-state REDEME answer onto the typed state."""
    if declared is None:
        return RedemeEnrolmentState.UNSTATED
    return RedemeEnrolmentState.ENROLLED if declared else RedemeEnrolmentState.NOT_ENROLLED


class RefundEligibilityOutcome(StrEnum):
    """What may be done with a negative Modelo 303 result in one period."""

    #: The refund election is lawful, so devolución and compensación are both open.
    REFUND_ALLOWED = "refund_allowed"
    #: Only compensación is lawful: the credit is carried into later periods.
    CARRY_FORWARD_ONLY = "carry_forward_only"
    #: Nothing but compensación is certain, because the REDEME inscription is unstated.
    #: The refund is neither offered nor ruled out; the missing fact is named instead.
    UNDETERMINED_REDEME_UNSTATED = "undetermined_redeme_unstated"


class RefundEligibilityBasis(StrEnum):
    """Which fact settled the outcome."""

    #: The period is the year's last filing period, so the annual refund is open to anyone.
    FINAL_PERIOD = "final_period"
    #: The taxpayer's REDEME inscription settled it, whether it opened the refund or not.
    REDEME = "redeme"
    #: The period is not the year's last, which is what leaves only the carry-forward.
    NON_FINAL_PERIOD = "non_final_period"


@dataclass(frozen=True, slots=True)
class RefundEligibility:
    """Whether a negative Modelo 303 result may be elected as a refund, and on what basis.

    ``legal_refs`` are the registry's declared references for the provisions the
    outcome rests on, in the registry's order. They are read from the resolved
    :class:`RefundEligibilityPolicy` so this module holds no legal reference of
    its own.
    """

    outcome: RefundEligibilityOutcome
    basis: RefundEligibilityBasis
    legal_refs: tuple[str, ...]

    @property
    def refund_allowed(self) -> bool:
        """Whether devolución may be elected. False while the REDEME fact is unstated."""
        return self.outcome is RefundEligibilityOutcome.REFUND_ALLOWED


def _final_period_legal_refs(policy: RefundEligibilityPolicy, period: Period) -> tuple[str, ...]:
    """The refs the registry declares for the final period ``period`` is."""
    return next(
        (definition.legal_refs for definition in policy.definitions if definition.token == period.registry_token),
        (),
    )


def _monthly_regime_legal_refs(policy: RefundEligibilityPolicy) -> tuple[str, ...]:
    """The refs the registry declares for the monthly cadence the REDEME regime governs."""
    return next(
        (definition.legal_refs for definition in policy.definitions if definition.cadence == _MONTHLY_CADENCE),
        (),
    )


def _all_final_period_legal_refs(policy: RefundEligibilityPolicy) -> tuple[str, ...]:
    """The refs of every declared final period: the provisions whose conditions are unmet."""
    seen: dict[str, None] = {}
    for definition in policy.definitions:
        for ref in definition.legal_refs:
            seen.setdefault(ref, None)
    return tuple(seen)


def resolve_refund_eligibility(
    *,
    period: Period,
    period_scheme: RefundEligibilityPolicy,
    redeme: RedemeEnrolmentState,
) -> RefundEligibility:
    """Resolve whether a negative IVA result may be elected as a refund in ``period``.

    ``period_scheme`` is the registry's declaration of which filing periods are
    the year's last, resolved from the pinned authority by the caller. Quarterly,
    monthly and annual cadences are therefore answered by one declaration, never
    by a per-code branch here.

    The year's last period opens the refund to every taxpayer (LIVA art.
    115.Uno) whatever ``redeme`` says, so it is tested first; outside it the
    inscription decides (art. 115.Dos with art. 116), and an unstated
    inscription resolves to
    :attr:`RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED` rather than to
    a refusal.
    """
    if period_scheme.is_final_period(period):
        return RefundEligibility(
            outcome=RefundEligibilityOutcome.REFUND_ALLOWED,
            basis=RefundEligibilityBasis.FINAL_PERIOD,
            legal_refs=_final_period_legal_refs(period_scheme, period),
        )
    if redeme is RedemeEnrolmentState.UNSTATED:
        return RefundEligibility(
            outcome=RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED,
            basis=RefundEligibilityBasis.REDEME,
            legal_refs=_monthly_regime_legal_refs(period_scheme),
        )
    if redeme is RedemeEnrolmentState.ENROLLED:
        return RefundEligibility(
            outcome=RefundEligibilityOutcome.REFUND_ALLOWED,
            basis=RefundEligibilityBasis.REDEME,
            legal_refs=_monthly_regime_legal_refs(period_scheme),
        )
    return RefundEligibility(
        outcome=RefundEligibilityOutcome.CARRY_FORWARD_ONLY,
        basis=RefundEligibilityBasis.NON_FINAL_PERIOD,
        legal_refs=_all_final_period_legal_refs(period_scheme),
    )


def refund_eligibility_for_period(
    *,
    period: Period,
    redeme: RedemeEnrolmentState,
    authority: ValidatedRegistryAuthority | None = None,
) -> RefundEligibility:
    """Resolve the period scheme from the pinned authority, then answer :func:`resolve_refund_eligibility`.

    The convenience entry point for a caller that holds no resolved scheme. A
    caller that already has one calls :func:`resolve_refund_eligibility`
    directly rather than resolving the fact twice.
    """
    scheme = resolve_refund_eligibility_policy_for_period(period, authority=authority)
    return resolve_refund_eligibility(period=period, period_scheme=scheme, redeme=redeme)


def is_last_filing_period_of_year(period: Period) -> bool:
    """Return whether ``period`` is the last Modelo 303 filing period of its year."""
    return resolve_refund_eligibility_policy_for_period(period).is_final_period(period)


__all__ = [
    "RedemeEnrolmentState",
    "RefundEligibility",
    "RefundEligibilityBasis",
    "RefundEligibilityOutcome",
    "is_last_filing_period_of_year",
    "redeme_enrolment_state",
    "refund_eligibility_for_period",
    "resolve_refund_eligibility",
]
