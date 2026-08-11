"""Modelo 210 IRNR España-Estados Unidos convenio resolution (tranche).

Grounds the Spain-US double-taxation treaty (CDI 22-02-1990, redacción vigente
tras el Protocolo de 2013 en vigor 27-11-2019, BOE-A-1990-30940) against the real
registry engine (no mocks). The two-regime split is resolved by grounding the
CURRENTLY-in-force (post-protocol) rates:

* Art 10.2.b dividendos — "15 por ciento del importe bruto de los dividendos en
  los demás casos" → dividend ceiling 0.15 (min(0.19, 0.15) = 0.15).
* Art 11.1 intereses — "sólo pueden someterse a imposición en ese otro Estado" →
  interest exempt at source (0), mirroring the DE art-11 exemption.

Grounded verbatim from the bundled BOE consolidated corpus (non-tautological).
The 5%/0% dividend tiers and the art 11.2 interest exceptions are not modelled.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
)
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "210"
_YEAR = 2025
_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_us_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_us_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_us_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_us_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_us_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_us_test"): Decimal("0"),
    }
    bound = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**bound, **casilla_inputs},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        text_inputs=text_inputs,
        date_context={"filing_period": date(_YEAR, 12, 31)},
        m303_regimen_simplificado_scope=None,
        m303_annual_orden=None,
    )
    return result.values[_TIPO_GRAVAMEN], result.values[_CUOTA_INTEGRA]


def test_us_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """US-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.b)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="dividend", country_code="US", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")


def test_us_interest_is_source_state_exempt(tmp_path: Path) -> None:
    """US-resident interest: source-state exemption (art 11.1) → 0."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="interest", country_code="US", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_us_treaty_legal_entries_are_grounded() -> None:
    """The US treaty rows and their BOE-grounded legal entries are registered."""
    catalogues = resources().modelos.authority.catalogues
    assert "convenio-es-us-1990:art-10" in catalogues.legal
    assert "convenio-es-us-1990:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-us-1990:art-10"]
    art11 = catalogues.legal["convenio-es-us-1990:art-11"]
    assert art10.document_id == "BOE-A-1990-30940"
    assert art11.document_id == "BOE-A-1990-30940"
    assert "15 por ciento del importe bruto de los dividendos" in art10.required_text
    assert "sólo pueden someterse a imposición en ese otro Estado" in art11.required_text
