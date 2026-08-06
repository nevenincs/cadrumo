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

One limit remains and is worth stating rather than leaving to be discovered: a
shortfall that lands exactly on a statutory rate is indistinguishable from a real
withholding and passes silently. Grounding the sectoral rates *widened* that band
rather than narrowing it, and deliberately so — 1 % and 2 % are small figures a
routine bank fee can hit exactly (a 20,00 EUR correspondent fee on a 2.000,00 base
is precisely 1 %), so those rows now pass where the art. 95.1-only screen caught
them. That is the cost of not false-firing on the agricultural, forestry and
módulos filers whose withholding genuinely is 1 % or 2 %, and it is the right
trade: a false positive on a correct filing trains operators to ignore the channel,
which forfeits every true positive too. The screen narrows the exposure; it has
never closed it, and closing it needs a declared retención, which the ADR rejected.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...core.aggregation import (
    LedgerWithholdingDerivation,
    RetencionScheme,
    work_income_retencion_treatment,
)
from ...domain.transactions import statutory_activity_retencion_rates
from ._renta_income_ledger import RentaIncomeObservation
from ._retenciones import RetencionObservation
from ._source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for an administrador/consejero retención whose
#: withheld amount matches neither statutory art. 101.2 fixed rate.
ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND = "administrador_retencion_rate"

#: Diagnostic ``source_kind`` for an INFERRED actividad-económica retención whose
#: figure matches neither RIRPF art. 95.1 rate.
INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND = "inferred_actividad_retencion_rate"

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


def inferred_actividad_retencion_rate_advisory_observations(
    observations: Iterable[RentaIncomeObservation],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for inferred retención matching no RIRPF art. 95.1 rate.

    A :class:`~._source_mesh.CalculationSourceDiagnostic` (reason
    ``inferred_retencion_rate_unmatched``) is emitted for each income observation
    whose ``withheld_derivation`` says the figure was INFERRED from a cash
    shortfall and whose ``withheld_amount`` is no statutory-rate product of its
    own ``taxable_base_amount``. Rows carrying a retención DECLARED on a linked
    invoice, rows carrying no retención, and rows with no positive base are out
    of scope and never fire.

    The rate set is read from the registry parameter catalogue via
    :func:`~domain.transactions.statutory_activity_retencion_rates`, so the
    comparison tracks the grounded legal figures rather than a literal restated
    here, and a newly-grounded rate widens the conforming band automatically.

    Per row rather than aggregated, unlike the ungrounded-substrate advisory: the
    firing set is meant to be small and the actionable unit is one transaction
    whose cash gap needs explaining, so the transaction id is the payload.

    Args:
        observations: The actividad-económica income rows feeding the calculation.

    Returns:
        A tuple of non-blocking rate-mismatch diagnostics, in input order.
    """
    rates = statutory_activity_retencion_rates()
    rendered_rates = ", ".join(str(rate) for rate in sorted(rates))
    diagnostics: list[CalculationSourceDiagnostic] = []
    for observation in observations:
        if observation.withheld_derivation not in _INFERRED_WITHHOLDING_MARKERS:
            continue
        base = observation.taxable_base_amount
        if base is None or base <= Decimal("0"):
            continue
        amount = observation.withheld_amount
        if any(_conforms_to_fixed_rate(base, amount, rate) for rate in rates):
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
    "administrador_retencion_rate_advisory_observations",
    "inferred_actividad_retencion_rate_advisory_observations",
]
