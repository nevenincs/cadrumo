"""Single determined-fact resolution of a modelo's fichero result disposition.

The AEAT fichero "Tipo de declaración" encodes the *result disposition* of an
autoliquidación (a ingresar / a compensar / a devolver / negativa). For Modelo
303 a negative result is, by default, a credit carried forward (compensación,
``C``); a taxpayer inscribed in the Registro de devolución mensual (REDEME) — or
filing the last period of the year — may instead request the credit back
(devolución, ``D``).

This module is the ONE place that determination is made. The export header
composer and the cross-period carry persistence both read the disposition from
:func:`resolve_modelo_result_disposition`, so the fichero ``D`` the operator
submits and the cross-period carry the next period reads can never disagree (a
refunded period requests the money back AND carries nothing — never both). It
reuses the codified per-modelo result→code derivation
(:func:`~aeat.core.derive_result_disposition`) and the REDEME/last-period
eligibility gate (:func:`~aeat.domain.iva.refund_disposition_available`); it does
not duplicate either.

Legal basis (Modelo 303 refund election): RD 1624/1992 (RIVA) art. 30 (Registro
de devolución mensual); Ley 37/1992 (LIVA) art. 116 (the monthly-refund right).
"""

from __future__ import annotations

from ...core import (
    Modelo,
    Period,
    ResultDisposition,
    derive_result_disposition,
    result_disposition_is_refund,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.iva import refund_disposition_available
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit

#: Provisional fallback "Tipo de declaración" disposition for a modelo that
#: declares the header but has no codified, diseño-grounded result-disposition
#: spec. ``INGRESO`` ("I") is wrong for a credit/zero result, so a new modelo
#: MUST be added to the spec rather than relying on it. Mirrors the export
#: fallback constant — kept here because the resolver is the disposition authority.
DECLARATION_TYPE_FALLBACK: ResultDisposition = ResultDisposition.INGRESO


def resolve_modelo_result_disposition(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
) -> ResultDisposition:
    """Resolve the single fichero "Tipo de declaración" result disposition.

    Computes the modelo's base disposition from its final-result casilla via the
    codified :func:`~aeat.core.derive_result_disposition`, then — for a Modelo 303
    credit (``C``) — applies the REDEME monthly-refund election: a taxpayer
    inscribed in the Registro de devolución mensual (or filing the last period of
    the year) files the negative period as a refund (``D``) rather than carrying
    it forward. The eligibility gate
    (:func:`~aeat.domain.iva.refund_disposition_available`) confirms the refund is
    lawful for the period. Every other disposition is returned unchanged.

    Returns the one :class:`~aeat.core.ResultDisposition` both the export header
    composer and the cross-period carry persistence read, so the fichero
    disposition and the carry can never disagree.
    """
    base = derive_result_disposition(work_unit.modelo, revision.casilla_values)
    if base is None:
        return DECLARATION_TYPE_FALLBACK
    return _apply_modelo_303_refund_election(
        base,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        period=period,
    )


def revision_is_refund_disposition(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
) -> bool:
    """Return whether the revision's resolved disposition is a refund (devolución).

    Convenience wrapper used by the cross-period carry path: a refunded Modelo 303
    period generates zero compensación carry-forward. Reads the SAME resolved
    disposition the export emits via :func:`resolve_modelo_result_disposition`.
    """
    disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
    )
    return result_disposition_is_refund(disposition)


def _apply_modelo_303_refund_election(
    declaration_type: ResultDisposition,
    *,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    period: Period,
) -> ResultDisposition:
    """Upgrade a Modelo 303 carry-forward (``C``) to a refund (``D``) for a REDEME taxpayer.

    A taxpayer inscribed in the Registro de devolución mensual (REDEME, art. 30
    RD 1624/1992) files a negative Modelo 303 period as a monthly refund
    (solicitud de devolución, Tipo de declaración ``D``; Ley 37/1992 art. 116)
    rather than carrying the credit forward (``C``). The inscription is the
    standing refund election; the eligibility gate confirms it is lawful for the
    period. A non-REDEME taxpayer keeps the carry-forward ``C``; every other
    disposition is untouched.
    """
    redeme = workflow_profile.iva.redeme_enrolled
    if (
        work_unit.modelo == Modelo.M303.value
        and declaration_type is ResultDisposition.COMPENSACION
        and redeme
        and refund_disposition_available(redeme_enrolled=redeme, period=period)
    ):
        return ResultDisposition.DEVOLUCION
    return declaration_type


__all__ = [
    "DECLARATION_TYPE_FALLBACK",
    "resolve_modelo_result_disposition",
    "revision_is_refund_disposition",
]
