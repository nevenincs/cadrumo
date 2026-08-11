"""Modelo 210 IRNR España-Estados Unidos convenio cánones exemption resolution.

Grounds the Spain-US double-taxation treaty (CDI 22-02-1990, BOE-A-1990-30940)
cánones source-state exemption in its redacción VIGENTE tras el Protocolo de 2013
(Artículo VI, BOE-A-2019-15166, en vigor 27-11-2019), which replaced the original
tiered 5/8/10% article 12 in full:

* Art 12 cánones — "sólo pueden someterse a imposición en ese otro Estado" →
  source-state exempt (0), mirroring the US art-11 interest exemption.

The override kind is EXEMPT, so the resolver drives the source-state rate to zero
regardless of the domestic 24% cánones rate. Grounded verbatim from the bundled
BOE consolidated (post-Protocol) corpus (non-tautological).
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
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_us_canones_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_us_canones_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    """Drive the REAL engine and return (tipo_gravamen, cuota_integra)."""
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_us_canones_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_us_canones_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_us_canones_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_us_canones_test"): Decimal("0"),
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


def test_us_canones_is_source_state_exempt(tmp_path: Path) -> None:
    """US-resident cánones: source-state exemption (art 12, Protocolo 2019) → 0."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="canones", country_code="US", base="1000.00")

    assert tipo == Decimal("0")
    assert cuota == Decimal("0.00")


def test_us_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The US cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = resources().modelos.authority.catalogues
    assert "convenio-es-us-1990:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-us-1990:art-12"]
    assert art12.document_id == "BOE-A-1990-30940"
    assert "sólo pueden someterse a imposición en ese otro Estado" in art12.required_text
