"""Modelo 210 IRNR España-Países Bajos convenio cánones ceiling resolution.

Grounds the Spain-Netherlands double-taxation treaty (CDI 16-06-1971, en vigor
20-09-1972, BOE-A-1972-1469) cánones source-state ceiling against the real
registry engine (no mocks):

* Art 12.2 cánones — "el impuesto así exigido no puede exceder del 6 por 100 del
  importe bruto de los cánones" → ceiling 0.06 (the PERMANENT rate; Protocol
  clause XIV's 5% was a transitional 1972-1977 rate, long expired).

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
NL-resident cánones item resolves to min(0.24, 0.06) = 0.06 (domestic cánones is
the Art 25.1.a general 24% rate). Grounded verbatim from the bundled BOE corpus
(non-tautological).
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
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_nl_canones_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_nl_canones_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    """Drive the REAL engine and return (tipo_gravamen, cuota_integra)."""
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_nl_canones_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_nl_canones_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_nl_canones_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_nl_canones_test"): Decimal("0"),
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
    )
    return result.values[_TIPO_GRAVAMEN], result.values[_CUOTA_INTEGRA]


def test_nl_canones_resolves_treaty_ceiling_of_6_percent(tmp_path: Path) -> None:
    """NL-resident cánones: min(domestic 0.24, treaty 0.06) = 0.06 (art 12.2, permanent)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="canones", country_code="NL", base="1000.00")

    assert tipo == Decimal("0.06")
    assert cuota == Decimal("60.00")  # 1000 × 0.06


def test_nl_canones_treaty_and_legal_entry_are_grounded() -> None:
    """The NL cánones treaty row and its BOE-grounded legal entry are registered."""
    catalogues = resources().modelos.authority.catalogues
    assert "convenio-es-nl-1971:art-12" in catalogues.legal
    art12 = catalogues.legal["convenio-es-nl-1971:art-12"]
    assert art12.document_id == "BOE-A-1972-1469"
    assert "no puede exceder del 6 por 100" in art12.required_text
