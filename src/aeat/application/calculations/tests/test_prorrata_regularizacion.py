"""Deferred-source advisory projection for the annual prorrata regularización."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import BindingSourceKind
from ....domain.iva import RegularizacionProrrataDireccion
from .._prorrata_regularizacion import (
    CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA,
    build_prorrata_regularizacion_advisory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
