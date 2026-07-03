"""Tests for the committed Modelo 117 registry foundation."""

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
_C08: CasillaId = validated_casilla_id("08", surface="_C08")
_C09: CasillaId = validated_casilla_id("09", surface="_C09")
_C10: CasillaId = validated_casilla_id("10", surface="_C10")
_C11: CasillaId = validated_casilla_id("11", surface="_C11")


def _load_modelo_117():
    return _committed_modelo("117")


def test_modelo_117_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_117()
    assert modelo.id == "117"
    assert modelo.revisions, "117 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_117_formulas_owned_by_construct() -> None:
    modelo, _ = _load_modelo_117()
    revision = modelo.revisions["2019-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert {"modelo-117-total-liquidacion", "modelo-117-resultado-ingresar"} <= owned


def test_modelo_117_total_liquidacion_and_resultado_ingresar_match_official_form_arithmetic() -> None:
    """09 = [03] + [06] + [08]; 11 = [09] - [10], per the AEAT form's own printed text."""
    modelo, catalogues = _load_modelo_117()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _C03: Decimal("1000.00"),
            _C06: Decimal("300.00"),
            _C08: Decimal("200.00"),
            _C10: Decimal("100.00"),
        },
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_C09] == Decimal("1500.00")
    assert result.values[_C11] == Decimal("1400.00")
