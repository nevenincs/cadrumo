"""Contract tests for Modelo 296 withholding row materialisation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..withholding296_bindings import Withholding296Observation, _build_withholding296_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _observation(
    *,
    source_id: str,
    perceptor_tax_id: str,
    codigo_pais: str,
    base_retenciones: str,
    porcentaje_retencion: str,
    retencion_practicada: str,
    perceptor_legal_name: str,
) -> Withholding296Observation:
    """Build a valid observation with the fields relevant to row folding."""
    return Withholding296Observation(
        source_id=source_id,
        perceptor_tax_id=perceptor_tax_id,
        perceptor_legal_name=perceptor_legal_name,
        codigo_pais=codigo_pais,
        base_retenciones=Decimal(base_retenciones),
        porcentaje_retencion=Decimal(porcentaje_retencion),
        retencion_practicada=Decimal(retencion_practicada),
        transaction_date=date(2025, 12, 31),
    )


def test_build_withholding296_rows_folds_amounts_and_orders_groups() -> None:
    rows = _build_withholding296_rows(
        (
            _observation(
                source_id="es-1",
                perceptor_tax_id="ES-payee",
                codigo_pais="ES",
                base_retenciones="100",
                porcentaje_retencion="19",
                retencion_practicada="19",
                perceptor_legal_name="Payee",
            ),
            _observation(
                source_id="de-1",
                perceptor_tax_id="DE-payee",
                codigo_pais="DE",
                base_retenciones="50",
                porcentaje_retencion="15",
                retencion_practicada="7.5",
                perceptor_legal_name="Other payee",
            ),
            _observation(
                source_id="es-2",
                perceptor_tax_id="ES-payee",
                codigo_pais="ES",
                base_retenciones="25",
                porcentaje_retencion="4",
                retencion_practicada="5",
                perceptor_legal_name="Payee",
            ),
        ),
    )

    assert [row["registro_orden"] for row in rows] == ["1", "2"]
    assert [row["codigo_pais"] for row in rows] == ["DE", "ES"]
    es_row = rows[1]
    assert es_row["base_retenciones"] == Decimal("125")
    assert es_row["porcentaje_retencion"] == Decimal("23")
    assert es_row["retencion_practicada"] == Decimal("24")


def test_build_withholding296_rows_completes_design_blank_slots() -> None:
    row = _build_withholding296_rows(
        (
            _observation(
                source_id="one",
                perceptor_tax_id="DE-payee",
                codigo_pais="DE",
                base_retenciones="1",
                porcentaje_retencion="0",
                retencion_practicada="0",
                perceptor_legal_name="Payee",
            ),
        ),
    )[0]

    assert row["representative_tax_id"] == " " * 9
    assert row["codigo_emisor"] == " " * 12
    assert row["codigo_cuenta"] == " " * 20
    assert row["codigo_lei"] == " " * 20
    assert row["nif_pais_residencia"] == " " * 20
    assert row["direccion_perceptor"] == " " * 162
    assert row["accrual_year"] == "0000"
    assert row["fecha_devengo"] == "0" * 8
    assert row["fecha_inicio_prestamo"] == "0" * 8
    assert row["fecha_vencimiento_prestamo"] == "0" * 8
    assert row["fecha_nacimiento"] == "0" * 8
