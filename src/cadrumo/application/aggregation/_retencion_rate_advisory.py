"""Statutory-rate advisories for retención figures the engine did not compute.

Two surfaces live here, one per side of the retención relationship, because
both ask the same question — does this withheld figure correspond to a rate the
law actually fixes? — and answering it in one place keeps the comparison, its
cent tolerance, and its grounding from being restated twice.

The RECEIVED side (:func:`administrador_retencion_rate_advisory_observations`)
screens operator-entered Modelo 111 per-perceptor rows. The ISSUED side
(:func:`inferred_actividad_retencion_rate_advisory_observations`) screens the
Modelo 130 actividad-económica retención the ledger *inferred* from a cash
shortfall.

Administrador/consejero rows (RECEIVED side)
--------------------------------------------

Modelo 111 aggregates operator-supplied per-perceptor retención rows: each
:class:`~._retenciones.RetencionObservation` carries both the ``taxable_base``
and the withheld ``retencion_amount``. For ordinary empleados
(:attr:`~core.aggregation.RetencionScheme.WORK_INCOME`) the withholding is a
personalised progressive computation (LIRPF art. 101.1), so no single rate can be
asserted. For administradores y miembros de consejos de administración
(:attr:`~core.aggregation.RetencionScheme.WORK_INCOME_DIRECTOR`) the law
fixes the rate: LIRPF art. 101.2 (Ley 35/2006, BOE-A-2006-20764), developed by
RIRPF art. 80.1.3.º (RD 439/2007), sets a general 35 % that drops to 19 % when the
paying entity's importe neto de la cifra de negocios is below 100.000 euros.

The engine does not compute the withheld amount (the operator enters it from their
payroll), so the fixed rate could previously go unverified: an administrador row
carrying, say, the ordinary empleado rate would fold into the trabajo block and
file silently. This module surfaces that as a non-blocking
:class:`~._source_mesh.CalculationSourceDiagnostic` on the calculate path,
grounded in the statutory :class:`~core.aggregation.WorkIncomeRetencionTreatment`
descriptor (``no-silent-under-declaration``). Because the engine cannot always
know the paying entity's INCN, a row whose effective rate matches EITHER statutory
figure (35 % or 19 %) is treated as conforming; only a row consistent with neither
raises the advisory, so a legitimate reduced-rate filing never false-fires.

Inferred actividad-económica retención (ISSUED side)
----------------------------------------------------

The Modelo 130 income ledger derives retención practicada as the declared invoice
gross minus the cash actually received, bounded ABOVE by the RIRPF art. 95.1
general rate. Nothing bounds it BELOW, and nothing can: a shortfall is a shortfall
whatever caused it. So a cash gap arising from something that is not a retención at
all — a correspondent-bank fee on a foreign transfer, a rounding short-pay, a
pronto-pago discount agreed after invoicing, a line the client disputed and deducted
— lands in the same subtraction and becomes a pago-a-cuenta credit for tax nobody
withheld and AEAT never received. It then settles against a payer Modelo 111 that
reports nothing.

The inference itself is not the defect and is deliberately left alone: requiring a
declared retención was considered and rejected, because the declared-first branch is
not always reachable and dropping the inference would under-declare a credit the
taxpayer is genuinely owed. What was missing is that the inference was invisible —
the ``withheld_derivation`` marker recording that a figure was *inferred* rather than
declared reached no operator surface at all.

The discriminator is that a real retención is always ``base × a statutory rate``.
A genuine 15 % withholding on a 2.000 EUR base is exactly 300,00; a bank fee, a
rounding gap, or a disputed line lands on no such product. Screening on the rate
rather than on the derivation marker is what keeps this advisory off the correct
domestic-B2B majority, where the shortfall genuinely IS the retención — a blanket
advisory on every inference would fire on those and train operators to ignore the
channel, the failure mode ``ledger-iva-advisory-only-on-cuota-bearing-categories``
exists to prevent.

The comparison reads the whole grounded art. 95 rate set — 15 %, 7 %, 2 % and 1 %
— from the registry parameter catalogue, never a literal restated here. The
sectoral rates (art. 95.4 agrícola/ganadera, with its 1 % engorde de porcino y
avicultura carve-out from the 2 % general figure; art. 95.5 forestal; art. 95.6.1.º
estimación objetiva) were grounded precisely because screening against the art. 95.1
pair alone made every genuine sectoral withholding look like a phantom credit.

A match is not one verdict, because the rates differ in how easily an accident
reaches them. 15 % and 7 % are large: a fee or rounding gap does not land on
2.000 × 0,15 = 300,00 by coincidence, so a match there is a strong claim and the
screen stays silent. 1 % and 2 % are small enough that a routine bank fee lands on
them exactly — a 20,00 EUR correspondent fee on a 2.000,00 base is precisely 1 % —
so a sectoral-only match is a WEAKER claim and raises its own advisory under a
separate reason code, ``inferred_retencion_sectoral_rate_unconfirmed``. Separate
rather than reworded, because the operator driving this CLI is an autonomous agent
that routes on fields: "matches nothing" and "matches a small rate that may be a
coincidence" are different epistemic states and must not be collapsed into one.

The active profile words that sectoral advisory and never gates it. The
distinction is load-bearing and easy to erode: it is tempting to read a
non-agricultural profile and suppress the diagnostic entirely, but nothing in the
profile can establish that a taxpayer is NOT agrícola, ganadero or forestal —
that is an ACTIVITY TYPE and the profile records an estimation REGIME, which is
independent of it. Suppressing on such a signal would hide a real finding behind
a fact nothing verified. A weak signal may set how confidently we speak; it may
never decide whether we speak at all.

The grading matters most for a shortfall quoted as a PERCENTAGE, and that case is
worth stating precisely because the flat-fee example above understates it. A
20,00 EUR fee colliding with 1 % of a 2.000,00 base is arithmetic luck at one
invoice size. A pronto-pago descuento is conventionally quoted as a percentage,
and 1 % and 2 % are its standard values — so a base-quoted discount collides with
the sectoral rates at EVERY base, by construction rather than by coincidence.
Screening on the rate set alone would therefore have made one of the four phantom
causes this advisory exists to catch invisible at its two commonest values, at
every invoice size. It is the sectoral reason code that keeps it visible: those
rows raise the weaker advisory rather than passing silently. A discount quoted on
the invoice TOTAL instead of the base lands at 1,21 × the rate and collides with
nothing, so it raises the strong unmatched advisory.

The residual limit, stated rather than left to be discovered: a shortfall landing
on 15 % or 7 % is still indistinguishable from a real withholding and still passes
silently. Closing that needs a declared retención, which the ADR rejected.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Final

from ...core.aggregation import (
    LedgerWithholdingDerivation,
    RetencionScheme,
    work_income_retencion_treatment,
)
from ...domain.transactions import (
    professional_activity_retencion_rates,
    statutory_activity_retencion_rates,
)
from ._renta_income_ledger import RentaIncomeObservation
from ._retenciones import RetencionObservation
from ._source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for an administrador/consejero retención whose
#: withheld amount matches neither statutory art. 101.2 fixed rate.
ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND = "administrador_retencion_rate"

#: Diagnostic ``source_kind`` for an INFERRED actividad-económica retención whose
#: figure matches no RIRPF art. 95 rate at all.
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
_UNRESOLVED_HINT: Final = object()

#: Cent tolerance for the amount comparison: the statutory withholding is a single
#: ``base * rate`` product rounded once to cents (money-2), so the maximum honest
#: rounding gap between the operator amount and the recomputed expected amount is
#: half a cent. A one-cent tolerance accepts that gap while still catching a
#: genuinely divergent rate.
_RATE_MATCH_TOLERANCE_EUR = Decimal("0.01")


def _conforms_to_fixed_rate(base: Decimal, amount: Decimal, rate: Decimal) -> bool:
    """Return whether ``amount`` is ``base * rate`` within the cent tolerance."""
    expected = base * rate
    return abs(amount - expected) <= _RATE_MATCH_TOLERANCE_EUR


def administrador_retencion_rate_advisory_observations(
    observations: Iterable[RetencionObservation],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for administrador rows inconsistent with art. 101.2.

    A :class:`~._source_mesh.CalculationSourceDiagnostic` (reason
    ``administrador_retencion_rate_mismatch``) is emitted for each
    :attr:`~core.aggregation.RetencionScheme.WORK_INCOME_DIRECTOR`
    observation with a strictly-positive ``taxable_base`` whose withheld
    ``retencion_amount`` matches neither the general 35 % nor the reduced 19 %
    fixed rate of LIRPF art. 101.2. Rows on any other scheme (empleados follow
    the progressive art. 101.1 procedure, so no single rate applies; actividades,
    premios, capital, and arrendamiento are not art. 101 trabajo), and
    administrador rows with a non-positive base, are out of scope and never fire.

    Args:
        observations: The per-perceptor retención rows feeding the calculation.

    Returns:
        A tuple of non-blocking rate-mismatch diagnostics, in input order.
    """
    treatment = work_income_retencion_treatment(RetencionScheme.WORK_INCOME_DIRECTOR)
    if treatment is None or treatment.fixed_rate is None or treatment.fixed_reduced_rate is None:
        return ()
    general_rate = treatment.fixed_rate
    reduced_rate = treatment.fixed_reduced_rate
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
                    f"Administrador/consejero retención for perceptor {observation.perceptor_nif!r} "
                    f"(base {base}, withheld {amount}) matches neither the LIRPF art. 101.2 fixed "
                    f"rate of {general_rate} nor the reduced {reduced_rate} for entities with net "
                    f"turnover below 100.000 EUR; confirm the applied withholding rate before filing."
                ),
            ),
        )
    return tuple(diagnostics)


def _profile_suggests_sectoral_activity(bucket_id: str | None) -> bool | None:
    """Return whether the active profile hints at a sectoral activity.

    A HINT, deliberately weak, and the weakness is the point: nothing in
    :class:`~domain.deadlines.TaxpayerProfile` positively establishes that a
    taxpayer is NOT agrícola, ganadero or forestal. Agrícola/forestal is an
    ACTIVITY TYPE while the profile records an estimation REGIME, and the two
    are independent -- a farmer may file estimación directa and may sit in IVA
    general. ``iae_epigraph`` cannot close the gap either, because agricultural
    activities are largely IAE-exempt, so the field is emptiest for exactly the
    filers it would need to identify.

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
    # Function-local for the cycle reason the sibling profile-backed advisories
    # document: the profile package reaches back into this layer.
    from ...domain.deadlines import IrpfEstimationRegime, IVARegime
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import UserProfileLifecycleRepository, projection_for_taxpayer

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    except (OSError, ValueError):
        # A degraded profile read must not take down a calculation that has
        # already produced its figures; the advisory simply loses its hint.
        return None
    profile = projection_for_taxpayer(record if record is not None else {})
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
        f"{matched} of the base — a statutory RIRPF art. 95 sectoral rate, but also a common "
        f"bank-fee or discount amount. "
    )
    if sectoral_hint is True:
        return opening + (
            "Your profile declares an agricultural, forestry or módulos activity, so a "
            "withholding at this rate is consistent with it."
        )
    if sectoral_hint is False:
        return opening + (
            "Your profile declares a non-sectoral estimación directa activity, which is not "
            "normally subject to this rate, so the shortfall may not be tax withheld at all."
        )
    return opening + (
        "Your profile does not say whether you carry on an agricultural, forestry or módulos "
        "activity, so whether this rate can apply to you could not be checked."
    )


def inferred_actividad_retencion_rate_advisory_observations(
    observations: Iterable[RentaIncomeObservation],
    *,
    bucket_id: str | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for inferred retención matching no RIRPF art. 95.1 rate.

    Three outcomes, decided by ARITHMETIC alone against the grounded art. 95
    rates, for each row whose ``withheld_derivation`` says the figure was
    INFERRED from a cash shortfall and whose ``taxable_base_amount`` is
    positive. Rows carrying a retención DECLARED on a linked invoice, rows
    carrying no retención, and rows with no positive base never fire.

    * The amount matches an art. 95.1 PROFESSIONAL rate (15 % or 7 %) — silent.
      Those figures are too large for a fee or rounding gap to reach by
      accident, so the match is a strong claim.
    * The amount matches ONLY a sectoral rate (2 % or 1 %) — a
      ``inferred_retencion_sectoral_rate_unconfirmed`` advisory. The figure is a
      real statutory rate, but small enough that a bank fee or discount lands on
      it by coincidence, so the claim is weaker and carries its own reason code.
    * The amount matches nothing — a ``inferred_retencion_rate_unmatched``
      advisory, the strong finding.

    ``bucket_id`` is read ONLY to word the sectoral message, never to decide
    whether it fires. That separation is the point: the profile cannot establish
    that a taxpayer is not agrícola/ganadero/forestal (an activity type it does
    not record), so promoting the hint into a gate would suppress a real finding
    on a fact nothing verified. A weak signal may set how confidently we speak;
    it may not decide whether we speak. Do not "improve" this into a filter.

    The rate set is read from the registry parameter catalogue via
    :func:`~domain.transactions.statutory_activity_retencion_rates`, so the
    comparison tracks the grounded legal figures rather than a literal restated
    here, and a newly-grounded rate widens the conforming band automatically.

    Args:
        observations: The actividad-económica income rows feeding the calculation.
        bucket_id: Bucket whose active profile words the sectoral advisory.
            ``None`` (or an absent/unreadable profile) simply yields the
            could-not-be-checked wording; it never suppresses a diagnostic.

    Per row rather than aggregated, unlike the ungrounded-substrate advisory: the
    firing set is meant to be small and the actionable unit is one transaction
    whose cash gap needs explaining, so the transaction id is the payload.

    Returns:
        A tuple of non-blocking rate diagnostics, in input order.
    """
    rates = statutory_activity_retencion_rates()
    professional = professional_activity_retencion_rates()
    rendered_rates = ", ".join(str(rate) for rate in sorted(rates))
    sectoral_hint = _UNRESOLVED_HINT
    diagnostics: list[CalculationSourceDiagnostic] = []
    for observation in observations:
        if observation.withheld_derivation not in _INFERRED_WITHHOLDING_MARKERS:
            continue
        base = observation.taxable_base_amount
        if base is None or base <= Decimal("0"):
            continue
        amount = observation.withheld_amount
        matched = frozenset(rate for rate in rates if _conforms_to_fixed_rate(base, amount, rate))
        if matched & professional:
            # A 15 % or 7 % match is a strong claim: those figures are too large
            # for a fee or rounding gap to reach by accident. Nothing to say.
            continue
        if matched:
            # Sectoral-only. The FIRE is decided here, by arithmetic alone --
            # the profile is read below purely to word the message, never to
            # suppress it, because the profile cannot establish the fact that
            # would justify suppression (see _profile_suggests_sectoral_activity).
            if sectoral_hint is _UNRESOLVED_HINT:
                sectoral_hint = _profile_suggests_sectoral_activity(bucket_id)
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="inferred_retencion_sectoral_rate_unconfirmed",
                    source_kind=INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND,
                    message=_sectoral_match_message(
                        transaction_id=observation.transaction_id,
                        amount=amount,
                        base=base,
                        matched=", ".join(str(rate) for rate in sorted(matched)),
                        sectoral_hint=sectoral_hint,
                    ),
                    remedy=(
                        "Confirm with the payer whether this was retención or a fee, then record "
                        "the true figure with 'aeat app ledger classify <transaction-id>'."
                    ),
                ),
            )
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="inferred_retencion_rate_unmatched",
                source_kind=INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND,
                message=(
                    f"Transaction {observation.transaction_id!r} was paid {amount} EUR short of its "
                    f"invoice total, which was credited as retención practicada on a base of {base}. "
                    f"That figure matches no RIRPF art. 95 retención rate ({rendered_rates}), so the "
                    f"shortfall may be a bank fee, a discount, or a disputed amount rather than tax "
                    f"withheld on your behalf."
                ),
                remedy=(
                    "Claiming a pago a cuenta nobody withheld over-declares it. Confirm the shortfall "
                    "with the payer, then record the true figure with 'aeat app ledger classify "
                    "<transaction-id>'."
                ),
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
