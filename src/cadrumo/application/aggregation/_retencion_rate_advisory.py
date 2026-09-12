"""Statutory-rate advisories for retención figures the engine did not compute.

Two surfaces live here, one per side of the retención relationship, because
both ask the same question — does this withheld figure correspond to a rate the
law actually fixes? — and answering it in one place keeps the comparison, its
cent tolerance, and its grounding from being restated twice.

The RECEIVED side (:func:`administrador_retencion_rate_advisory_observations`)
screens operator-entered per-perceptor rows. The ISSUED side
(:func:`inferred_actividad_retencion_rate_advisory_observations`) screens an
activity-ledger withholding inferred from a cash shortfall.

Administrador/consejero rows (RECEIVED side)
--------------------------------------------

The received surface aggregates operator-supplied per-perceptor rows: each
:class:`~.retenciones.RetencionObservation` carries both the ``taxable_base``
and the withheld ``retencion_amount``. For ordinary work-income rows the
withholding is a personalised progressive computation, so no single rate can be
asserted. Fixed-rate administrator rows
(:attr:`~core.aggregation.RetencionScheme.WORK_INCOME_DIRECTOR`) the law
uses a fixed rate selected by the governing registry when the paying entity's
turnover condition requires it.

The engine does not compute the withheld amount (the operator enters it from their
payroll), so the fixed rate could previously go unverified: an administrador row
carrying, say, the ordinary empleado rate would fold into the trabajo block and
file silently. This module surfaces that as a non-blocking
:class:`~.source_mesh.CalculationSourceDiagnostic` on the calculate path,
grounded in the registry-backed
:func:`~domain.transactions.load_administrador_retencion_rates` rate set
(``no-silent-under-declaration``). :class:`~core.aggregation.WorkIncomeRetencionTreatment`
carries only the STRUCTURAL fact that this scheme follows a fixed procedure;
the rate figures themselves are regulatory data read from the registry, never a
literal in this or the core layer (``aeat-registry-authority-flow``). Because
the engine cannot always know the paying entity's INCN, a row whose effective
rate matches either authority-selected figure is treated as conforming; only a
row consistent with neither raises the advisory.

Inferred actividad-económica retención (ISSUED side)
----------------------------------------------------

The activity income ledger derives retención practicada as the declared invoice
gross minus the cash actually received, bounded ABOVE by the governed activity
rate. Nothing bounds it BELOW, and nothing can: a shortfall is a shortfall
whatever caused it. So a cash gap arising from something that is not a retención at
all — a correspondent-bank fee on a foreign transfer, a rounding short-pay, a
pronto-pago discount agreed after invoicing, a line the client disputed and deducted
— lands in the same subtraction and becomes a pago-a-cuenta credit for tax nobody
withheld and AEAT never received. It then settles against a payer record that
reports nothing.

The inference itself is not the defect and is deliberately left alone: requiring a
declared retención was considered and rejected, because the declared-first branch is
not always reachable and dropping the inference would under-declare a credit the
taxpayer is genuinely owed. What was missing is that the inference was invisible —
the ``withheld_derivation`` marker recording that a figure was *inferred* rather than
declared reached no operator surface at all.

The discriminator is that a real retención is a ``base × governed rate``.
Screening on the rate
rather than on the derivation marker is what keeps this advisory off the correct
domestic-B2B majority, where the shortfall genuinely IS the retención — a blanket
advisory on every inference would fire on those and train operators to ignore the
channel, the failure mode ``aeat-ledger-contract``
exists to prevent.

The comparison reads the complete governed rate set and its classifications
from registry facts, never a literal restated here. This keeps additional
sectoral pairings visible to the advisory instead of treating them as unmatched.

A match is not one verdict, because the authority classifications differ in how
easily an accidental shortfall can reach them. A sectoral-only match therefore
raises the separate ``inferred_retencion_sectoral_rate_unconfirmed`` reason code;
"matches nothing" and "matches a weaker classification" are distinct machine
states and must not be collapsed.

The active profile only words the sectoral advisory and never gates it. A weak
signal may set how confidently we speak; it may never decide whether we speak.

The separate sectoral reason code keeps weaker classification matches visible
instead of allowing them to pass silently.

The residual limit remains: a strong authority-rate match is indistinguishable
from a real withholding without a declared source, so it passes silently.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from enum import Enum, auto
from functools import cache
from typing import TYPE_CHECKING, Final

from ...core.aggregation import (
    LedgerWithholdingDerivation,
    RetencionScheme,
    work_income_retencion_treatment,
)
from ...core.money.rounding import CENT
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.transactions.retencion_facts import (
    administrador_retencion_legal_refs,
    load_administrador_retencion_rates,
    professional_activity_retencion_rates,
    rirpf_art95_retencion_legal_refs,
    statutory_activity_retencion_rates,
)
from .renta_income_ledger import RentaIncomeObservation
from .retenciones import RetencionObservation
from .source_mesh import CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile

#: Diagnostic ``source_kind`` for a fixed-rate administrator withholding whose
#: amount matches neither authority-selected rate.
ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND = "administrador_retencion_rate"

#: Diagnostic ``source_kind`` for an inferred activity withholding whose figure
#: matches no authority-selected rate.
INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND = "inferred_actividad_retencion_rate"

#: Diagnostic ``source_kind`` for an INFERRED retención matching ONLY a sectoral
#: rate — a weaker claim than the unmatched one, carried on its own kind so an
#: automated operator routes on the field rather than on the prose.
INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND = "inferred_sectoral_actividad_retencion_rate"

#: The derivation markers that assert a figure this application INFERRED from a cash
#: shortfall, as opposed to one a document declared.
#:
#: :attr:`~core.aggregation.LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE`
#: is deliberately absent: that figure is the invoice's own statement, not a
#: reconstruction, so screening it would second-guess the document rather than
#: disclose an inference. The zero-carrying markers are absent because they assert
#: no retención to check.
_INFERRED_WITHHOLDING_MARKERS: frozenset[LedgerWithholdingDerivation] = frozenset(
    {
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA,
        LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA,
    },
)


#: Sentinel for "the profile hint has not been read yet", distinct from the
#: ``None`` the probe itself returns for "read, but the profile is silent". The
#: probe touches storage, so it is resolved lazily on the first sectoral match
#: and reused: a calculation with no sectoral match must not pay for a profile
#: load, and one with many must not repeat it.
class _UnresolvedHint(Enum):
    """Single-member sentinel for a sectoral hint not yet read.

    An ``object()`` sentinel cannot be narrowed by an identity test, so every
    consumer downstream saw the hint widened to include it. An enum member
    narrows, which lets the declared ``bool | None`` boundary hold at the call
    sites without changing what the sentinel does.
    """

    TOKEN = auto()


_UNRESOLVED_HINT: Final = _UnresolvedHint.TOKEN


def _conforms_to_fixed_rate(base: Decimal, amount: Decimal, rate: Decimal) -> bool:
    """Return whether ``amount`` is ``base * rate`` within the cent quantum.

    The statutory withholding is a single ``base * rate`` product rounded once
    to cents (money-2), so the largest honest gap between the operator's amount
    and the recomputed expectation is half a cent. Bounding at :data:`CENT`
    accepts that gap while still catching a genuinely divergent rate.
    """
    expected = base * rate
    return abs(amount - expected) <= CENT


@cache
def _art95_refs(*, effective_date: date) -> tuple[LegalRefId, ...]:
    """Return the governed activity-rate grounding, resolved once per process.

    Cached because every diagnostic in this module cites the same set, and the
    grounding is read from the registry: re-resolving it per observation would
    make a disclosure cost a registry load on a path that runs per row.
    """
    return tuple(rirpf_art95_retencion_legal_refs(effective_date=effective_date))


def _administrador_refs(*, effective_date: date) -> tuple[LegalRefId, ...]:
    """Return the administrator-rate grounding, resolved once per process.

    Same rationale as :func:`_art95_refs`: every administrador diagnostic in
    this module cites the same set, so resolving it once per process keeps a
    disclosure from costing a registry load per row.
    """
    return tuple(administrador_retencion_legal_refs(effective_date=effective_date))


def administrador_retencion_rate_advisory_observations(
    observations: Iterable[RetencionObservation],
    *,
    effective_date: date,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for administrator rows inconsistent with authority rates.

    A :class:`~.source_mesh.CalculationSourceDiagnostic` (reason
    ``administrador_retencion_rate_mismatch``) is emitted for each
    :attr:`~core.aggregation.RetencionScheme.WORK_INCOME_DIRECTOR`
    observation with a strictly-positive ``taxable_base`` whose withheld
    ``retencion_amount`` matches neither authority-selected fixed rate. Rows on
    any other scheme and administrator rows with a non-positive base are out of
    scope and never fire.

    Args:
        observations: The per-perceptor retención rows feeding the calculation.
        effective_date: Endpoint of the actual filing period whose legal rates apply.

    Returns:
        A tuple of non-blocking rate-mismatch diagnostics, in input order.
    """
    treatment = work_income_retencion_treatment(RetencionScheme.WORK_INCOME_DIRECTOR)
    if treatment is None or not treatment.is_fixed_rate:
        return ()
    rates = load_administrador_retencion_rates(effective_date=effective_date)
    general_rate = rates.general_rate
    reduced_rate = rates.reduced_rate
    diagnostics: list[CalculationSourceDiagnostic] = []
    for observation in observations:
        if observation.scheme is not RetencionScheme.WORK_INCOME_DIRECTOR:
            continue
        base = observation.taxable_base
        if base <= Decimal("0"):
            continue
        amount = observation.retencion_amount
        if _conforms_to_fixed_rate(base, amount, general_rate) or _conforms_to_fixed_rate(
            base,
            amount,
            reduced_rate,
        ):
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="administrador_retencion_rate_mismatch",
                source_kind=ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND,
                message=(
                    f"Administrator withholding for perceptor {observation.perceptor_nif!r} "
                    f"(base {base}, withheld {amount}) matches neither authority-selected "
                    f"rate ({general_rate} or {reduced_rate}) for the applicable turnover "
                    f"condition below {rates.reduced_incn_threshold_eur} EUR; confirm the applied "
                    f"withholding rate before filing."
                ),
                # Read off the registry-backed rate set this advisory already
                # resolved rather than restating it here. The machine consumer
                # routes on this field, while legal provenance moves with the
                # selected registry revision instead of living in this layer.
                legal_refs=_administrador_refs(effective_date=effective_date),
            ),
        )
    return tuple(diagnostics)


def _load_profile_for_bucket(bucket_id: str) -> TaxpayerProfile | None:
    """Load and project the active profile, treating unavailable state as unknown."""
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import projection_for_taxpayer

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    except (OSError, ValueError):
        # A degraded profile read must not take down a calculation that has
        # already produced its figures; the advisory simply loses its hint.
        return None
    # The repository raises on every failure path and never returns None, so the
    # former ``else {}`` fallback was unreachable. Failures arrive through the
    # except clause above, which is where the degraded-read handling lives.
    return projection_for_taxpayer(record)


def _declared_activity_hint(profile: TaxpayerProfile) -> bool | None:
    """Resolve the explicit activity axis before considering weaker surrogates."""
    from ...domain.deadlines.models import IrpfActivityKind

    if profile.irpf_activity_kind is IrpfActivityKind.SECTORIAL:
        return True
    if profile.irpf_activity_kind is IrpfActivityKind.PROFESIONAL:
        return False
    return None


def _profile_regime_hint(profile: TaxpayerProfile) -> bool | None:
    """Resolve the profile's weaker regime and prior-year activity signals."""
    from ...domain.deadlines.models import IrpfEstimationRegime, IVARegime

    if profile.iva_regime is IVARegime.REAGP:
        return True
    if profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA:
        return True
    agri_gross = profile.objective_estimation_prior_year_agri_livestock_forest_gross_eur
    if agri_gross is not None and agri_gross > Decimal("0"):
        return True
    if profile.irpf_estimation_regime in {
        IrpfEstimationRegime.DIRECTA_NORMAL,
        IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
    }:
        return False
    return None


def _profile_suggests_sectoral_activity(bucket_id: str | None) -> bool | None:
    """Return whether the active profile hints at a sectoral activity.

    A HINT, and everything below the first check is deliberately weak. The
    profile's activity axis and estimation regime are independent, so the
    regime is only a surrogate when the direct activity signal is silent.

    :attr:`~domain.deadlines.TaxpayerProfile.irpf_activity_kind` is the one
    signal here that is not a surrogate: it is the activity axis itself,
    operator-declared, so it answers the question asked rather than one
    correlated with it. It is therefore consulted FIRST and its answer is
    final. A direct activity declaration takes precedence over weaker regime
    surrogates, which remain only as fallbacks for a profile that is silent.

    So this answers only "is there a POSITIVE indication of sectoral activity?":
    ``True`` on an explicit indicator, ``False`` when the profile declares a
    régimen that is present and non-sectoral, and ``None`` when the profile is
    absent, unreadable, or silent on the question.

    Because the signal is weak it may only shape the WORDING of an advisory. It
    must never decide whether one fires -- see
    :func:`inferred_actividad_retencion_rate_advisory_observations`.
    """
    if bucket_id is None:
        return None
    profile = _load_profile_for_bucket(bucket_id)
    if profile is None:
        return None
    declared_hint = _declared_activity_hint(profile)
    if declared_hint is not None:
        return declared_hint
    return _profile_regime_hint(profile)


def _sectoral_match_message(
    *,
    transaction_id: str,
    amount: Decimal,
    base: Decimal,
    matched: str,
    sectoral_hint: bool | None,
) -> str:
    """Build the sectoral-match text, its confidence set by the profile hint."""
    opening = (
        f"Transaction {transaction_id!r} was paid {amount} EUR short of its invoice total, "
        f"which was credited as retención practicada on a base of {base}. That is exactly "
        f"{matched} of the base — an authority-selected sectoral rate, but also a common "
        f"bank-fee or discount amount. "
    )
    if sectoral_hint is True:
        return opening + (
            "Your profile declares a sectoral activity, so a withholding at this rate is consistent with it."
        )
    if sectoral_hint is False:
        # Deliberately does not name the mechanism: a False now arrives either
        # from a declared professional activity or from a non-sectoral
        # estimación directa régimen, and naming one would misdescribe the other.
        return opening + (
            "Your profile declares a non-sectoral activity, which is not normally subject "
            "to this authority-selected rate, so the shortfall may not be tax withheld at all."
        )
    return opening + (
        "Your profile does not identify whether the sectoral classification applies, "
        "so whether this rate can apply could not be checked."
    )


def _inferred_rate_matches(
    observation: RentaIncomeObservation,
    *,
    rates: frozenset[Decimal],
    professional: frozenset[Decimal],
) -> tuple[Decimal, frozenset[Decimal]] | None:
    """Classify one inferred row by its grounded rate products.

    ``None`` means the row is outside the advisory or already matches a strong
    professional rate. An empty set is meaningful: it is the unmatched-rate
    finding and must remain distinct from a skipped row.
    """
    if observation.withheld_derivation not in _INFERRED_WITHHOLDING_MARKERS:
        return None
    base = observation.taxable_base_amount
    if base is None or base <= Decimal("0"):
        return None
    matched = frozenset(rate for rate in rates if _conforms_to_fixed_rate(base, observation.withheld_amount, rate))
    if matched & professional:
        # A professional-rate match is a strong claim under the registry's
        # classification. Nothing to say.
        return None
    return base, matched


def _sectoral_rate_diagnostic(
    observation: RentaIncomeObservation,
    *,
    base: Decimal,
    matched: frozenset[Decimal],
    sectoral_hint: bool | None,
    resolver_id: str | None,
    effective_date: date,
) -> CalculationSourceDiagnostic:
    """Build the weaker advisory for a sectoral-only rate product."""
    return CalculationSourceDiagnostic(
        reason="inferred_retencion_sectoral_rate_unconfirmed",
        resolver_id=resolver_id,
        source_kind=INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND,
        message=_sectoral_match_message(
            transaction_id=observation.transaction_id,
            amount=observation.withheld_amount,
            base=base,
            matched=", ".join(str(rate) for rate in sorted(matched)),
            sectoral_hint=sectoral_hint,
        ),
        legal_refs=_art95_refs(effective_date=effective_date),
        remedy=(
            "Confirm with the payer whether this was retención or a fee, then record "
            "the true figure by classifying that transaction in the ledger."
        ),
    )


def _unmatched_rate_diagnostic(
    observation: RentaIncomeObservation,
    *,
    base: Decimal,
    rendered_rates: str,
    resolver_id: str | None,
    effective_date: date,
) -> CalculationSourceDiagnostic:
    """Build the strong advisory for a shortfall matching no grounded rate."""
    amount = observation.withheld_amount
    return CalculationSourceDiagnostic(
        reason="inferred_retencion_rate_unmatched",
        resolver_id=resolver_id,
        source_kind=INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND,
        message=(
            f"Transaction {observation.transaction_id!r} was paid {amount} EUR short of its "
            f"invoice total, which was credited as retención practicada on a base of {base}. "
            f"That figure matches no authority-selected activity withholding rate ({rendered_rates}), so the "
            f"shortfall may be a bank fee, a discount, or a disputed amount rather than tax "
            f"withheld on your behalf."
        ),
        legal_refs=_art95_refs(effective_date=effective_date),
        remedy=(
            "Claiming a pago a cuenta nobody withheld over-declares it. Confirm the shortfall "
            "with the payer, then record the true figure by classifying that transaction in "
            "the ledger."
        ),
    )


def inferred_actividad_retencion_rate_advisory_observations(
    observations: Iterable[RentaIncomeObservation],
    *,
    bucket_id: str | None = None,
    resolver_id: str | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for inferred retención against governed activity rates.

    Three outcomes, decided by arithmetic alone against the governed rate set,
    for each row whose ``withheld_derivation`` says the figure was
    INFERRED from a cash shortfall and whose ``taxable_base_amount`` is
    positive. Rows carrying a retención DECLARED on a linked invoice, rows
    carrying no retención, and rows with no positive base never fire.

    * A professional-rate match is silent when the authority classifies it as a
      strong claim.
    * A sectoral-only match raises an
      ``inferred_retencion_sectoral_rate_unconfirmed`` advisory because its
      evidential strength is weaker.
    * The amount matches nothing — a ``inferred_retencion_rate_unmatched``
      advisory, the strong finding.

    ``bucket_id`` is read only to word the sectoral message, never to decide
    whether it fires. A weak profile signal may shape confidence but cannot gate
    the diagnostic.

    The rate set is read from governed facts via
    :func:`~domain.transactions.statutory_activity_retencion_rates`, so the
    comparison tracks the grounded legal figures rather than a literal restated
    here, and a newly-grounded rate widens the conforming band automatically.

    Args:
        observations: The actividad-económica income rows feeding the calculation.
        bucket_id: Bucket whose active profile words the sectoral advisory.
        resolver_id: Identifier of the resolver emitting these diagnostics,
            stamped onto each one so the operator can attribute an advisory to
            the source that raised it. Every sibling diagnostic builder in the
            calculate mesh carries it; omitting it here delivered these two
            advisories with a null attribution while their neighbours were
            attributed.
            ``None`` (or an absent/unreadable profile) simply yields the
            could-not-be-checked wording; it never suppresses a diagnostic.

    Per row rather than aggregated, unlike the ungrounded-substrate advisory: the
    firing set is meant to be small and the actionable unit is one transaction
    whose cash gap needs explaining, so the transaction id is the payload.

    Returns:
        A tuple of non-blocking rate diagnostics, in input order.
    """
    sectoral_hint = _UNRESOLVED_HINT
    diagnostics: list[CalculationSourceDiagnostic] = []
    for observation in observations:
        effective_date = observation.filing_date
        rates = statutory_activity_retencion_rates(effective_date=effective_date)
        professional = professional_activity_retencion_rates(effective_date=effective_date)
        rendered_rates = ", ".join(str(rate) for rate in sorted(rates))
        assessment = _inferred_rate_matches(observation, rates=rates, professional=professional)
        if assessment is None:
            continue
        base, matched = assessment
        if matched:
            # Sectoral-only. The FIRE is decided here, by arithmetic alone --
            # the profile is read below purely to word the message, never to
            # suppress it, because the profile cannot establish the fact that
            # would justify suppression (see _profile_suggests_sectoral_activity).
            if sectoral_hint is _UNRESOLVED_HINT:
                sectoral_hint = _profile_suggests_sectoral_activity(bucket_id)
            diagnostics.append(
                _sectoral_rate_diagnostic(
                    observation,
                    base=base,
                    matched=matched,
                    sectoral_hint=sectoral_hint,
                    resolver_id=resolver_id,
                    effective_date=effective_date,
                ),
            )
            continue
        diagnostics.append(
            _unmatched_rate_diagnostic(
                observation,
                base=base,
                rendered_rates=rendered_rates,
                resolver_id=resolver_id,
                effective_date=effective_date,
            ),
        )
    return tuple(diagnostics)


__all__ = [
    "ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND",
    "INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND",
    "INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND",
    "administrador_retencion_rate_advisory_observations",
    "inferred_actividad_retencion_rate_advisory_observations",
]
