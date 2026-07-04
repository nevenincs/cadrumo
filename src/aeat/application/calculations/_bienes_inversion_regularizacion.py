"""Advisory projection for the capital-goods IVA regularización (LIVA arts. 107-110).

Builds the non-blocking source diagnostics the calculate path surfaces for
Modelo 303 casilla 43 / the Modelo 390 regularización field: the ordinary annual
art-109 comparison for in-window, non-disposed goods
(:func:`build_bienes_inversion_regularizacion_advisory`), and the art-110 single
("única") disposal regularización for a good disposed of during the filing year
(:func:`build_bienes_inversion_transmision_advisory`). In the first slice the
``bienes_inversion_regularizacion`` source kind is DEFERRED (the automatic annual
feed is blocked on the separately-deferred prorrata-definitiva source), so the
annual projection produces an advisory — never a silent zero — carrying the
proposed casilla-43 value the operator confirms. The art-110 disposal projection
carries no such pending state (every disposal fact is already on the register), so
its advisory always names a concrete proposed figure.

Both are pure functions over the register; neither is yet wired into the live
calculate MESH BINDING (that promotion is gated on the prorrata-definitiva source,
per ADR ``2026-07-01-iva-bienes-inversion-regularizacion``) — they are wired into
the calculate-path ADVISORY collector
(:mod:`application.modelo._bienes_inversion_advisory`).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import BindingSourceKind
from ...domain.bienes_inversion import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    RegistroTransmisionesResult,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
)
from ..aggregation import CalculationSourceDiagnostic

#: The Modelo 303 casilla the register feeds. Deducciones block, "Regularización
#: de bienes de inversión" (LIVA arts. 107-110).
CASILLA_REGULARIZACION_BIENES_INVERSION = "43"

#: Distinct advisory source-kind label for the art-110 disposal path, so an
#: operator (and a future mesh-binding promotion) can tell the annual comparison
#: apart from the single-disposal regularización on the same casilla.
_TRANSMISION_SOURCE_KIND = f"{BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value}_transmision"


def build_bienes_inversion_regularizacion_advisory(
    register: BienesInversionIvaRegister,
    *,
    regularizacion_year: int,
    prorrata_definitiva_by_identifier: Mapping[str, Decimal],
) -> tuple[RegistroRegularizacionResult, CalculationSourceDiagnostic | None]:
    """Project the register and build the deferred-source advisory diagnostic.

    Returns the register projection plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the register
    holds in-window, art-108-eligible, non-disposed goods for
    ``regularizacion_year`` — so a taxpayer who owns capital goods in their
    regularisation window is alerted that casilla 43 may be due, rather than
    silently filing zero. When no in-window goods exist the diagnostic is
    ``None`` (nothing to regularise, no noise). A good disposed of at or before
    ``regularizacion_year`` is excluded here and routed instead through
    :func:`build_bienes_inversion_transmision_advisory`.

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


def build_bienes_inversion_transmision_advisory(
    register: BienesInversionIvaRegister,
    *,
    disposal_year: int,
    cuota_devengada_entrega_by_identifier: Mapping[str, Decimal] | None = None,
) -> tuple[RegistroTransmisionesResult, CalculationSourceDiagnostic | None]:
    """Project the register's art-110 disposals and build the advisory diagnostic.

    Returns the register-wide transmisión projection plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the register
    holds a good disposed of in ``disposal_year`` with window time remaining — so
    a taxpayer who sold, transmitted, or otherwise disposed of a tracked capital
    good is alerted that the art-110 single regularización is due on casilla 43,
    rather than silently filing zero. Unlike the annual advisory, this projection
    carries no pending state: every fact art-110 needs (acquisition-year
    percentage, cuota soportada, disposal regime) is already on the record, so the
    diagnostic always names a concrete proposed figure (the regla-1ª cap is
    applied only when the caller supplies the disposal's own cuota devengada).

    Args:
        register: The persisted :class:`BienesInversionIvaRegister`.
        disposal_year: The filing year being calculated.
        cuota_devengada_entrega_by_identifier: Optional per-good cuota devengada on
            the disposal itself, applied as the regla-1ª cap. Absent keys leave
            regla 1ª uncapped for that good.

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroTransmisionesResult`; the diagnostic is ``None`` when no
        disposal falls in ``disposal_year``.
    """
    projection = compute_registro_transmisiones(
        register,
        disposal_year=disposal_year,
        cuota_devengada_entrega_by_identifier=cuota_devengada_entrega_by_identifier,
    )
    if projection.computed_count == 0:
        return projection, None

    message = (
        f"{projection.computed_count} bien(es) de inversión transmitido(s) en {disposal_year} "
        "requieren la regularización única de entregas (LIVA art. 110). "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_BIENES_INVERSION}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=_TRANSMISION_SOURCE_KIND,
        message=message,
    )
    return projection, diagnostic


__all__ = [
    "CASILLA_REGULARIZACION_BIENES_INVERSION",
    "build_bienes_inversion_regularizacion_advisory",
    "build_bienes_inversion_transmision_advisory",
]
