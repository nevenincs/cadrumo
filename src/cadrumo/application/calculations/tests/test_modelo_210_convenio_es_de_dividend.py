"""Modelo 210 IRNR España-Alemania dividend ceiling resolution.

Grounds the Spain-Germany double-taxation treaty (CDI firmado 03-02-2011, en
vigor 18-10-2012, BOE-A-2012-10212) dividend source-state ceiling against the
real registry engine (no mocks). Art 10.2.b caps the general source-state rate:
"el impuesto así exigido no podrá exceder del: ... b) 15 por ciento del importe
bruto de los dividendos en todos los demás casos" → ceiling 0.15.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
DE-resident dividend resolves to min(0.19, 0.15) = 0.15. This is a grounded
treaty figure (read verbatim from the bundled BOE corpus), so the assertion is
non-tautological — a regression that dropped the dividend row, or mis-typed the
ceiling as flat, would change the resolved rate and fail the test. The pre-existing
DE interest override (exempt, art 11) is left intact and re-asserted here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "210"
_YEAR = 2025
_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_de_dividend_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_de_dividend_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    """Drive the REAL engine and return (tipo_gravamen, cuota_integra)."""
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_de_dividend_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_de_dividend_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_de_dividend_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_de_dividend_test"): Decimal("0"),
    }
    bound = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**bound, **casilla_inputs},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        text_inputs=text_inputs,
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )
    return result.values[_TIPO_GRAVAMEN], result.values[_CUOTA_INTEGRA]


def test_de_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """DE-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.b)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="dividend", country_code="DE", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")  # 1000 × 0.15


def test_de_dividend_legal_entry_is_grounded() -> None:
    """The DE dividend treaty row and its BOE-grounded art-10 legal entry exist."""
    catalogues = resources().modelos.authority.catalogues
    assert "convenio-es-de-2011:art-10" in catalogues.legal
    art10 = catalogues.legal["convenio-es-de-2011:art-10"]
    assert art10.document_id == "BOE-A-2012-10212"
    assert "15 por ciento del importe bruto de los dividendos" in art10.required_text


def test_de_interest_exempt_override_is_preserved(tmp_path: Path) -> None:
    """The pre-existing DE interest exemption (art 11) is untouched by #216."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, _cuota = _resolve_rate(tipo_renta="interest", country_code="DE", base="1000.00")

    assert tipo == Decimal("0")  # art 11 source-state exemption
