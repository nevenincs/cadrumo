"""Advisory projection for the capital-goods IVA regularización (LIVA arts. 107-110).

Builds the non-blocking source diagnostic the calculate path would surface for
Modelo 303 casilla 43 / the Modelo 390 regularización field when the profile
register holds in-window capital goods. In the first slice the
``bienes_inversion_regularizacion`` source kind is DEFERRED (the automatic feed is
blocked on the separately-deferred prorrata-definitiva source), so this projection
produces an advisory — never a silent zero — carrying the proposed casilla-43
value the operator confirms.

This is a pure function over the register and the supplied definitive percentages;
it is not yet wired into the live calculate mesh (that is the promotion step gated
on the prorrata-definitiva source, per ADR
``2026-07-01-iva-bienes-inversion-regularizacion``).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import BindingSourceKind
from ...domain.bienes_inversion import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ..aggregation import CalculationSourceDiagnostic

#: The Modelo 303 casilla the register feeds. Deducciones block, "Regularización
#: de bienes de inversión" (LIVA arts. 107-110).
CASILLA_REGULARIZACION_BIENES_INVERSION = "43"


def build_bienes_inversion_regularizacion_advisory(
    register: BienesInversionIvaRegister,
    *,
    regularizacion_year: int,
    prorrata_definitiva_by_identifier: Mapping[str, Decimal],
) -> tuple[RegistroRegularizacionResult, CalculationSourceDiagnostic | None]:
    """Project the register and build the deferred-source advisory diagnostic.

    Returns the register projection plus a non-blocking
    :class:`~aeat.core.aggregation.CalculationSourceDiagnostic` when the register
    holds in-window, art-108-eligible goods for ``regularizacion_year`` — so a
    taxpayer who owns capital goods in their regularisation window is alerted that
    casilla 43 may be due, rather than silently filing zero. When no in-window
    goods exist the diagnostic is ``None`` (nothing to regularise, no noise).

    The diagnostic ``message`` names the in-window count, the number of goods whose
    regularización could be computed (a definitive percentage was supplied), the
    number still pending the deferred percentage, and the proposed casilla-43 value.

    Args:
        register: The persisted :class:`BienesInversionIvaRegister`.
        regularizacion_year: The year being calculated.
        prorrata_definitiva_by_identifier: Current-year definitive deduction
            percentages keyed by record identifier (absent keys are pending).

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroRegularizacionResult`; the diagnostic is ``None`` when
        there is nothing to regularise.
    """
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=regularizacion_year,
        prorrata_definitiva_by_identifier=prorrata_definitiva_by_identifier,
    )
    in_window = len(projection.rows)
    if in_window == 0:
        return projection, None

    message = (
        f"{in_window} bien(es) de inversión en periodo de regularización "
        f"(LIVA arts. 107-110) para {regularizacion_year}: "
        f"{projection.computed_count} computado(s), "
        f"{projection.pending_percentage_count} pendiente(s) de prorrata definitiva. "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_BIENES_INVERSION}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value,
        message=message,
    )
    return projection, diagnostic


__all__ = [
    "CASILLA_REGULARIZACION_BIENES_INVERSION",
    "build_bienes_inversion_regularizacion_advisory",
]
