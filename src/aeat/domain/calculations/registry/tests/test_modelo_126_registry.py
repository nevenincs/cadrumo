"""Tests for the committed Modelo 126 registry foundation."""

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
_C06: CasillaId = validated_casilla_id("06", surface="_C06")
_C10: CasillaId = validated_casilla_id("10", surface="_C10")
_C11: CasillaId = validated_casilla_id("11", surface="_C11")
_C12: CasillaId = validated_casilla_id("12", surface="_C12")


def _load_modelo_126():
    return _committed_modelo("126")


def test_modelo_126_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_126()
    assert modelo.id == "126"
    assert modelo.revisions, "126 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_126_formulas_owned_by_construct() -> None:
    modelo, _ = _load_modelo_126()
    revision = modelo.revisions["2019-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert {"modelo-126-total-liquidacion", "modelo-126-resultado-ingresar"} <= owned


def test_modelo_126_total_liquidacion_and_resultado_ingresar_match_official_form_arithmetic() -> None:
    """10 = [02] + [06]; 12 = [10] - [11], per the AEAT form's own printed text."""
    modelo, catalogues = _load_modelo_126()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _C02: Decimal("800.00"),
            _C06: Decimal("200.00"),
            _C11: Decimal("150.00"),
        },
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_C10] == Decimal("1000.00")
    assert result.values[_C12] == Decimal("850.00")
