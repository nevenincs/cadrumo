"""Deferred-source advisory projection for the annual prorrata regularización."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import BindingSourceKind, Period
from ....domain.calculations.registry import IvaLedgerObservation
from ....domain.iva import (
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaRateKind,
    RegularizacionProrrataDireccion,
)
from .._prorrata_regularizacion import (
    CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA,
    build_prorrata_declared_volume_divergence_advisory,
    build_prorrata_regularizacion_advisory,
    project_prorrata_regularizacion_feed,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _periods_2026() -> tuple[Period, ...]:
    return tuple(Period.from_year_and_code(2026, code) for code in ("1T", "2T", "3T", "4T"))


def _ledger_observation(
    ledger_id: str,
    *,
    transaction_date: date,
    category: IvaCategory,
    base: str,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    exemption_article: IvaExemptionArticle | None = None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=category,
        exemption_article=exemption_article,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal(base),
        iva_amount=Decimal("0.00"),
    )


def test_advisory_fires_for_casilla_44_when_prorrata_applies_and_percentages_differ() -> None:
    """A trader with sin-derecho volumes and a percentage delta is alerted, not silent."""
    result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("10000"),
        regularizacion_year=2025,
    )
    assert result.direccion is RegularizacionProrrataDireccion.DEDUCCION
    assert result.importe == Decimal("2000.00")
    assert diagnostic is not None
    assert diagnostic.source_kind == BindingSourceKind.PRORRATA_REGULARIZACION.value
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA == "44"
    assert "casilla 44" in diagnostic.message
    assert "2000.00" in diagnostic.message


def test_projection_feeds_m303_casilla_44_and_m390_from_single_result() -> None:
    """The proposed M303 and M390 values are one projection of the same result."""
    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("10000"),
    )

    assert projection.modelo_303_casilla_44_id == CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA
    assert projection.modelo_303_casilla_44_value == projection.result.importe
    assert projection.modelo_390_regularizacion_anual_value == projection.result.importe


def test_declared_volume_divergence_advisory_preserves_declared_authority() -> None:
    """Ledger contradiction warns, but declared annual volume casillas stay authoritative."""
    observations = (
        _ledger_observation(
            "taxable-sale",
            transaction_date=date(2026, 1, 20),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            base="1000.00",
        ),
        _ledger_observation(
            "art20-8-exempt-sale",
            transaction_date=date(2026, 5, 3),
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_8,
            base="500.00",
        ),
        _ledger_observation(
            "art20-26-exempt-with-right",
            transaction_date=date(2026, 8, 10),
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_26,
            base="300.00",
        ),
        _ledger_observation(
            "input-purchase-ignored",
            transaction_date=date(2026, 2, 15),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            flow=IvaFlowDirection.SOPORTADO,
            base="700.00",
        ),
        _ledger_observation(
            "outside-ejercicio-ignored",
            transaction_date=date(2025, 12, 31),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            base="999.00",
        ),
    )

    rollup, diagnostic = build_prorrata_declared_volume_divergence_advisory(
        declared_volume_total=Decimal("2000.00"),
        declared_volume_con_derecho=Decimal("1500.00"),
        ledger_observations=observations,
        ejercicio_periods=_periods_2026(),
        regularizacion_year=2026,
    )

    assert rollup.ledger_volume_con_derecho == Decimal("1300.00")
    assert rollup.ledger_volume_sin_derecho == Decimal("500.00")
    assert rollup.ledger_volume_total == Decimal("1800.00")
    assert rollup.declared_volume_con_derecho == Decimal("1500.00")
    assert rollup.declared_volume_sin_derecho == Decimal("500.00")
    assert rollup.included_ledger_ids == ("art20-26-exempt-with-right", "art20-8-exempt-sale", "taxable-sale")
    assert diagnostic is not None
    assert diagnostic.reason == "source_issue"
    assert "conservan la autoridad" in diagnostic.message


def test_declared_volume_rollup_is_silent_when_ledger_matches_declared_values() -> None:
    """No advisory fires when the ledger projection matches the declared volumes."""
    observations = (
        _ledger_observation(
            "taxable-sale",
            transaction_date=date(2026, 1, 20),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            base="1000.00",
        ),
        _ledger_observation(
            "art20-8-exempt-sale",
            transaction_date=date(2026, 5, 3),
            category=IvaCategory.DOMESTIC_EXEMPT,
            exemption_article=IvaExemptionArticle.ART_20_UNO_8,
            base="500.00",
        ),
    )

    rollup, diagnostic = build_prorrata_declared_volume_divergence_advisory(
        declared_volume_total=Decimal("1500.00"),
        declared_volume_con_derecho=Decimal("1000.00"),
        ledger_observations=observations,
        ejercicio_periods=_periods_2026(),
        regularizacion_year=2026,
    )

    assert rollup.diverges is False
    assert diagnostic is None


def test_advisory_is_silent_when_no_sin_derecho_operations() -> None:
    """No exempt-without-right volume ⇒ prorrata does not apply ⇒ no advisory noise."""
    result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
        regularizacion_year=2025,
    )
    assert diagnostic is None
    assert result.importe == Decimal("2000.00")


def test_advisory_is_silent_when_percentages_coincide() -> None:
    """No regularización is due when provisional equals definitive."""
    _result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("90"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("10000"),
        regularizacion_year=2025,
    )
    assert diagnostic is None


def test_advisory_reports_ingreso_direction_when_definitiva_below_provisional() -> None:
    """A downward regularización is surfaced as an ingreso in the message."""
    result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("12000.00"),
        prorrata_provisional_pct=Decimal("85"),
        prorrata_definitiva_pct=Decimal("70"),
        operaciones_sin_derecho_deduccion=Decimal("30000"),
        regularizacion_year=2025,
    )
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO
    assert diagnostic is not None
    assert "ingreso" in diagnostic.message
