"""Tests for the committed Modelo 128 registry foundation."""

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

_C03: CasillaId = validated_casilla_id("03", surface="_C03")
_C06: CasillaId = validated_casilla_id("06", surface="_C06")
_C07: CasillaId = validated_casilla_id("07", surface="_C07")


def _load_modelo_128():
    return _committed_modelo("128")


def test_modelo_128_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_128()
    assert modelo.id == "128"
    assert modelo.revisions, "128 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_128_formula_owned_by_construct() -> None:
    modelo, _ = _load_modelo_128()
    revision = modelo.revisions["2019-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert "modelo-128-resultado-ingresar" in owned


def test_modelo_128_resultado_ingresar_matches_official_form_arithmetic() -> None:
    """07 = [03] - [06], per the AEAT form's own printed text."""
    modelo, catalogues = _load_modelo_128()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _C03: Decimal("900.00"),
            _C06: Decimal("100.00"),
        },
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_C07] == Decimal("800.00")
