"""Modelo 210 IRNR España-Francia convenio ceiling resolution.

Grounds the Spain-France double-taxation treaty (CDI firmado 10-10-1995, en vigor
01-07-1997, BOE-A-1997-12729) dividend and interest source-state ceilings against
the real registry engine (no mocks). The treaty caps source-state taxation:

* Art 10.2.a dividendos — "el impuesto así exigido no podrá exceder del 15 por
  100 del importe bruto de los dividendos" → ceiling 0.15.
* Art 11.2 intereses — "el impuesto así exigido no puede exceder del 10 por 100
  del importe bruto de los intereses" → ceiling 0.10.

The override kind is CEILING, so the resolver applies min(domestic, treaty): a
FR-resident dividend resolves to min(0.19, 0.15) = 0.15 and interest to
min(0.19, 0.10) = 0.10. These are grounded treaty figures (read verbatim from the
bundled BOE corpus), so the assertions are non-tautological — a regression that
dropped either treaty row, or mis-typed the ceiling as flat, would change the
resolved rate and fail the test.
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
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface="es_fr_convenio_test")
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface="es_fr_convenio_test")


def _resolve_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    """Drive the REAL engine and return (tipo_gravamen, cuota_integra)."""
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface="es_fr_convenio_test"): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface="es_fr_convenio_test"): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface="es_fr_convenio_test"): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface="es_fr_convenio_test"): Decimal("0"),
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


def test_fr_dividend_resolves_treaty_ceiling_of_15_percent(tmp_path: Path) -> None:
    """FR-resident dividend: min(domestic 0.19, treaty 0.15) = 0.15 (art 10.2.a)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="dividend", country_code="FR", base="1000.00")

    assert tipo == Decimal("0.15")
    assert cuota == Decimal("150.00")  # 1000 × 0.15


def test_fr_interest_resolves_treaty_ceiling_of_10_percent(tmp_path: Path) -> None:
    """FR-resident interest: min(domestic 0.19, treaty 0.10) = 0.10 (art 11.2)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        tipo, cuota = _resolve_rate(tipo_renta="interest", country_code="FR", base="1000.00")

    assert tipo == Decimal("0.10")
    assert cuota == Decimal("100.00")  # 1000 × 0.10


def test_fr_treaty_and_legal_entries_are_grounded() -> None:
    """The FR treaty rows and their BOE-grounded legal entries are registered."""
    authority = resources().modelos.authority
    catalogues = authority.catalogues
    assert "convenio-es-fr-1995:art-10" in catalogues.legal
    assert "convenio-es-fr-1995:art-11" in catalogues.legal
    art10 = catalogues.legal["convenio-es-fr-1995:art-10"]
    art11 = catalogues.legal["convenio-es-fr-1995:art-11"]
    assert art10.document_id == "BOE-A-1997-12729"
    assert art11.document_id == "BOE-A-1997-12729"
    assert "no podrá exceder del 15 por 100" in art10.required_text
    assert "no puede exceder del 10 por 100" in art11.required_text
