"""Modelo 210 IRNR España-Bélgica convenio ceiling resolution (tranche).

Grounds the Spain-Belgium double-taxation treaty (CDI hecho en Bruselas el
14-06-1995, en vigor 25-06-2003, BOE-A-2003-13375) dividend and interest
source-state ceilings against the real registry engine (no mocks):

* Art 10.2.a dividendos — "no podrá exceder del 15 por 100 del importe bruto de
  los dividendos" → ceiling 0.15.
* Art 11.2 intereses — "no podrá exceder del 10 por 100 del importe bruto de los
  intereses" → ceiling 0.10.

Both CEILING overrides resolve to min(domestic 0.19, treaty): dividend 0.15,
interest 0.10. Grounded verbatim from the bundled BOE corpus (non-tautological).
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
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_be_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_be_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_be_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_be_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_be_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_be_test"): Decimal("0"),
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


def test_be_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """BE-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.a)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="dividend", country_code="BE", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_be_interest_resolves_treaty_ceiling_of_10_percent(tmp_path: Path) -> None:
    """BE-resident interest: min(domestic 0.19, treaty 0.10) = 0.10 (art 11.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="interest", country_code="BE", base="1000.00")

    assert tipo == Decimal("0.10")
    assert cuota == Decimal("100.00")


def test_be_treaty_legal_entries_are_grounded() -> None:
    """The BE treaty rows and their BOE-grounded legal entries are registered."""
    catalogues = resources().modelos.authority.catalogues
    assert "convenio-es-be-1995:art-10" in catalogues.legal
    assert "convenio-es-be-1995:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-be-1995:art-10"]
    art11 = catalogues.legal["convenio-es-be-1995:art-11"]
    assert art10.document_id == "BOE-A-2003-13375"
    assert art11.document_id == "BOE-A-2003-13375"
    assert "no podrá exceder del 15 por 100" in art10.required_text
    assert "no podrá exceder del 10 por 100" in art11.required_text
