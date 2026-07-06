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

from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, CasillaId, Period, validated_casilla_id
from ...domain.calculations.registry import IvaLedgerObservation
from ...domain.iva import (
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    RegularizacionProrrataDireccion,
    RegularizacionProrrataResult,
    compute_regularizacion_prorrata_anual,
)
from ..aggregation import CalculationSourceDiagnostic

#: The Modelo 303 casilla the annual prorrata regularización feeds. Deducciones
#: block, "Regularización prorrata por porcentaje definitivo - Cuota"
#: (LIVA art. 105.Cuatro).
CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA: CasillaId = validated_casilla_id(
    "44",
    surface="annual prorrata regularizacion Modelo 303 casilla",
)

_LEDGER_VOLUME_DIVERGENCE_SOURCE_KIND = "prorrata_regularizacion_ledger_volume_divergence"
_CON_DERECHO_OUTPUT_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.DOMESTIC_GENERAL_21,
        IvaCategory.DOMESTIC_REDUCED_10,
        IvaCategory.DOMESTIC_SUPER_REDUCED_4,
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    },
)
_CON_DERECHO_EXEMPTION_ARTICLES: frozenset[IvaExemptionArticle] = frozenset({IvaExemptionArticle.ART_20_UNO_26})


class ProrrataRegularizacionFeedProjection(BaseModel):
    """Structured proposed feeds for annual prorrata-general regularización.

    The first slice keeps ``prorrata_regularizacion`` deferred, so these values
    are proposed feeds for the operator-confirmed Modelo 303 casilla 44 and the
    Modelo 390 annual regularización field. Both come from the same
    :class:`RegularizacionProrrataResult`, preserving the registry's declared
    annual-volume authority for the definitive percentage.
    """

    model_config = STRICT_FROZEN_CONFIG

    result: RegularizacionProrrataResult
    operaciones_sin_derecho_deduccion: Decimal
    modelo_303_casilla_44_id: CasillaId = CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA
    modelo_303_casilla_44_value: Decimal | None = None
    modelo_390_regularizacion_anual_value: Decimal | None = None


class ProrrataDeclaredVolumeLedgerRollup(BaseModel):
    """Ledger-side annual volume rollup used only as a divergence advisory.

    Declared annual volume casillas remain the filing authority. This projection
    records the currently classifiable ledger output-volume view so settlement
    can warn when it contradicts those declared values.
    """

    model_config = STRICT_FROZEN_CONFIG

    declared_volume_total: Decimal
    declared_volume_con_derecho: Decimal
    declared_volume_sin_derecho: Decimal
    ledger_volume_total: Decimal
    ledger_volume_con_derecho: Decimal
    ledger_volume_sin_derecho: Decimal
    included_ledger_ids: tuple[str, ...] = ()

    @property
    def diverges(self) -> bool:
        return (
            self.declared_volume_total != self.ledger_volume_total
            or self.declared_volume_con_derecho != self.ledger_volume_con_derecho
            or self.declared_volume_sin_derecho != self.ledger_volume_sin_derecho
        )


def build_prorrata_declared_volume_divergence_advisory(
    *,
    declared_volume_total: Decimal,
    declared_volume_con_derecho: Decimal,
    ledger_observations: Iterable[IvaLedgerObservation],
    ejercicio_periods: Iterable[Period],
    regularizacion_year: int,
) -> tuple[ProrrataDeclaredVolumeLedgerRollup, CalculationSourceDiagnostic | None]:
    """Compare declared annual prorrata volumes with the ledger rollup.

    The rollup is deliberately advisory-only: it uses the existing IVA ledger
    observation stream and the supplied ejercicio periods'
    :meth:`Period.contains` boundary, but it does not replace the operator's
    declared annual volume casillas because some art-104 exclusions still need
    explicit classification.
    """
    periods = tuple(ejercicio_periods)
    if not periods:
        raise ValueError("ejercicio_periods must contain at least one Period")

    ledger_volume_con_derecho = Decimal("0")
    ledger_volume_sin_derecho = Decimal("0")
    included_ledger_ids: list[str] = []
    for observation in ledger_observations:
        if not any(period.contains(observation.transaction_date) for period in periods):
            continue
        volume_side = _prorrata_volume_side(observation)
        if volume_side is None:
            continue
        included_ledger_ids.append(observation.ledger_id)
        if volume_side == "con_derecho":
            ledger_volume_con_derecho += observation.base_amount
        else:
            ledger_volume_sin_derecho += observation.base_amount

    declared_volume_sin_derecho = declared_volume_total - declared_volume_con_derecho
    rollup = ProrrataDeclaredVolumeLedgerRollup(
        declared_volume_total=declared_volume_total,
        declared_volume_con_derecho=declared_volume_con_derecho,
        declared_volume_sin_derecho=declared_volume_sin_derecho,
        ledger_volume_total=ledger_volume_con_derecho + ledger_volume_sin_derecho,
        ledger_volume_con_derecho=ledger_volume_con_derecho,
        ledger_volume_sin_derecho=ledger_volume_sin_derecho,
        included_ledger_ids=tuple(sorted(included_ledger_ids)),
    )
    if not rollup.diverges:
        return rollup, None

    diagnostic = CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_LEDGER_VOLUME_DIVERGENCE_SOURCE_KIND,
        message=(
            f"Volúmenes anuales de prorrata declarados para {regularizacion_year} difieren del rollup "
            f"IVA de libro: declarado con derecho {declared_volume_con_derecho}, sin derecho "
            f"{declared_volume_sin_derecho}; libro con derecho {ledger_volume_con_derecho}, "
            f"sin derecho {ledger_volume_sin_derecho}. Las casillas declaradas conservan la autoridad."
        ),
    )
    return rollup, diagnostic


def _prorrata_volume_side(observation: IvaLedgerObservation) -> str | None:
    if observation.flow_direction is not IvaFlowDirection.REPERCUTIDO:
        return None
    if observation.category is IvaCategory.DOMESTIC_EXEMPT:
        if observation.exemption_article in _CON_DERECHO_EXEMPTION_ARTICLES:
            return "con_derecho"
        return "sin_derecho"
    if observation.category in _CON_DERECHO_OUTPUT_CATEGORIES:
        return "con_derecho"
    return None


def project_prorrata_regularizacion_feed(
    *,
    cuotas_soportadas_deducibles: Decimal,
    prorrata_provisional_pct: Decimal,
    prorrata_definitiva_pct: Decimal,
    operaciones_sin_derecho_deduccion: Decimal,
) -> ProrrataRegularizacionFeedProjection:
    """Project the annual regularización onto the M303 and M390 filing targets.

    ``prorrata_definitiva_pct`` is supplied by the registry-computed annual
    volume casillas. This helper deliberately does not recompute that percentage
    and does not promote the deferred source kind; it only turns the pure
    art-105 result into the two proposed filing values that later mesh promotion
    can consume.
    """
    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
    )
    proposed_value = (
        result.importe
        if operaciones_sin_derecho_deduccion > Decimal("0")
        and result.direccion is not RegularizacionProrrataDireccion.NINGUNA
        else None
    )
    return ProrrataRegularizacionFeedProjection(
        result=result,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
        modelo_303_casilla_44_value=proposed_value,
        modelo_390_regularizacion_anual_value=proposed_value,
    )


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
    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
    )
    result = projection.result
    if projection.modelo_303_casilla_44_value is None:
        return result, None

    sentido = "deducción complementaria" if result.direccion is RegularizacionProrrataDireccion.DEDUCCION else "ingreso"
    message = (
        f"Regularización de prorrata por porcentaje definitivo (LIVA arts. 104-105) "
        f"para {regularizacion_year}: prorrata provisional {prorrata_provisional_pct}% "
        f"→ definitiva {prorrata_definitiva_pct}% ({sentido}). "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA}: "
        f"{projection.modelo_303_casilla_44_value}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
    )
    return result, diagnostic


__all__ = [
    "CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA",
    "ProrrataDeclaredVolumeLedgerRollup",
    "ProrrataRegularizacionFeedProjection",
    "build_prorrata_declared_volume_divergence_advisory",
    "build_prorrata_regularizacion_advisory",
    "project_prorrata_regularizacion_feed",
]
