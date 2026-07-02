"""Tests for the committed Modelo 136 registry foundation.

Modelo 136 is the autoliquidación of the *gravamen especial sobre los premios
de determinadas loterías y apuestas* (LIRPF disposición adicional 33ª). The
levy is a flat 20 % on the prize amount exceeding the exempt threshold, so the
form arithmetic is fully printed on the official model:

    base imponible [04] = premio [02] - cuantía exenta [03]
    cuota [05]          = 20 % of base imponible [04]
    resultado [07]      = cuota [05] - autoliquidaciones anteriores [06]

The rate (20 %) and the wiring are grounded on the AEAT form's own printed text
and LIRPF DA 33ª; the test would fail if the registry formulas summed the wrong
casillas or applied a different rate, so it is not tautological.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .._formula_runtime import calculate_registry_snapshot
from .._ids import CasillaId, validated_casilla_id
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_C02: CasillaId = validated_casilla_id("02", surface="_C02")
_C03: CasillaId = validated_casilla_id("03", surface="_C03")
_C04: CasillaId = validated_casilla_id("04", surface="_C04")
_C05: CasillaId = validated_casilla_id("05", surface="_C05")
_C06: CasillaId = validated_casilla_id("06", surface="_C06")
_C07: CasillaId = validated_casilla_id("07", surface="_C07")


def _load_modelo_136():
    return _committed_modelo("136")


def test_modelo_136_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_136()
    assert modelo.id == "136"
    assert modelo.revisions, "136 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_136_formulas_owned_by_construct() -> None:
    modelo, _ = _load_modelo_136()
    revision = modelo.revisions["2026"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert {
        "modelo-136-base-imponible",
        "modelo-136-cuota-gravamen-especial",
        "modelo-136-resultado-ingresar",
    } <= owned


def test_modelo_136_base_cuota_resultado_match_official_form_arithmetic() -> None:
    """[04] = [02]-[03]; [05] = 20 % of [04]; [07] = [05]-[06], per the AEAT form.

    A prize of 100.000 € with the 40.000 € exempt threshold yields a 60.000 €
    base, a 12.000 € cuota (20 %), and — with no prior autoliquidación for the
    same prize — a 12.000 € resultado a ingresar.
    """
    modelo, catalogues = _load_modelo_136()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _C02: Decimal("100000.00"),
            _C03: Decimal("40000.00"),
            _C06: Decimal("0.00"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )
    assert result.values[_C04] == Decimal("60000.00")
    assert result.values[_C05] == Decimal("12000.00")
    assert result.values[_C07] == Decimal("12000.00")
