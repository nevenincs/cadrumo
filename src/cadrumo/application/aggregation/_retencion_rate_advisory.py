"""Statutory-rate advisory for administrador/consejero retención observations.

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
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...core.aggregation import RetencionScheme, work_income_retencion_treatment
from ._retenciones import RetencionObservation
from ._source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for an administrador/consejero retención whose
#: withheld amount matches neither statutory art. 101.2 fixed rate.
ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND = "administrador_retencion_rate"

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


__all__ = [
    "ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND",
    "administrador_retencion_rate_advisory_observations",
]
