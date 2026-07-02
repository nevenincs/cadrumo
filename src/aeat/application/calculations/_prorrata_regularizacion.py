"""Advisory projection for the annual prorrata-general regularización (LIVA arts. 104-105).

Builds the non-blocking source diagnostic the calculate path would surface for
Modelo 303 casilla 44 (Regularización prorrata por porcentaje definitivo - Cuota)
and the Modelo 390 annual regularización field when a taxpayer under prorrata
general has exempt-without-right operations in the year and a provisional
percentage was applied. In the first slice the ``prorrata_regularizacion`` source
kind is DEFERRED (the automatic feed is blocked on the provisional-carry store),
so this projection produces an advisory — never a silent zero — carrying the
proposed casilla-44 value the operator confirms.

This is a pure function over the two prorrata percentages and the year's
deductible input IVA; it is not yet wired into the live calculate mesh (that is
the promotion step gated on the provisional-carry store, per ADR
``2026-07-01-iva-complexity-hardening-scope``). The definitive percentage itself
comes from the full-year volume rollup fed to
:func:`~domain.iva.compute_prorrata_definitiva_anual`; deriving it from a
single quarter is a correctness defect (the silent-zero-base ADR).
"""

from __future__ import annotations

from decimal import Decimal

from ...core import BindingSourceKind
from ...domain.iva import (
    RegularizacionProrrataDireccion,
    RegularizacionProrrataResult,
    compute_regularizacion_prorrata_anual,
)
from ..aggregation import CalculationSourceDiagnostic

#: The Modelo 303 casilla the annual prorrata regularización feeds. Deducciones
#: block, "Regularización prorrata por porcentaje definitivo - Cuota"
#: (LIVA art. 105.Cuatro).
CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA = "44"


def build_prorrata_regularizacion_advisory(
    *,
    cuotas_soportadas_deducibles: Decimal,
    prorrata_provisional_pct: Decimal,
    prorrata_definitiva_pct: Decimal,
    operaciones_sin_derecho_deduccion: Decimal,
    regularizacion_year: int,
) -> tuple[RegularizacionProrrataResult, CalculationSourceDiagnostic | None]:
    """Compute the annual regularización and build the deferred-source advisory.

    Returns the pure :class:`RegularizacionProrrataResult` plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the taxpayer
    has exempt-without-right operations in the year (``operaciones_sin_derecho_
    deduccion > 0`` — prorrata applies) and the definitive percentage differs from
    the provisional one applied across the quarters (a regularización is due). In
    that case a taxpayer who leaves casilla 44 blank is alerted rather than
    silently under- or over-declaring. When prorrata does not apply, or the two
    percentages coincide, the diagnostic is ``None`` (nothing to regularise, no
    noise).

    The diagnostic ``message`` names the provisional and definitive percentages,
    the direction (deducción complementaria vs ingreso), and the proposed
    casilla-44 value.

    Args:
        cuotas_soportadas_deducibles: The year's total deductible input IVA
            (LIVA art. 105.Seis).
        prorrata_provisional_pct: Provisional deduction percentage applied during
            the year (LIVA art. 105.Uno — the prior-year definitive).
        prorrata_definitiva_pct: Definitive deduction percentage for the year
            (LIVA art. 104, computed from full-year volumes).
        operaciones_sin_derecho_deduccion: The year's exempt-without-right
            operation volume. When zero, prorrata does not apply and no
            regularización is proposed.
        regularizacion_year: The year being calculated (for the message).

    Returns:
        ``(result, diagnostic)`` where ``result`` is the
        :class:`RegularizacionProrrataResult`; the diagnostic is ``None`` when
        there is nothing to regularise.
    """
    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
    )
    if operaciones_sin_derecho_deduccion <= Decimal("0") or result.direccion is RegularizacionProrrataDireccion.NINGUNA:
        return result, None

    sentido = "deducción complementaria" if result.direccion is RegularizacionProrrataDireccion.DEDUCCION else "ingreso"
    message = (
        f"Regularización de prorrata por porcentaje definitivo (LIVA arts. 104-105) "
        f"para {regularizacion_year}: prorrata provisional {prorrata_provisional_pct}% "
        f"→ definitiva {prorrata_definitiva_pct}% ({sentido}). "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA}: "
        f"{result.importe}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
    )
    return result, diagnostic


__all__ = [
    "CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA",
    "build_prorrata_regularizacion_advisory",
]
