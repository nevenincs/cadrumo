"""Tests for the committed Modelo 296 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._formula_runtime import calculate_registry_snapshot
from .._snapshot import build_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


def _load_modelo_296():
    return _committed_modelo("296")


def test_modelo_296_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_296()
    assert modelo.id == "296"
    assert modelo.revisions, "296 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_296_formula_owned_by_construct() -> None:
    modelo, _ = _load_modelo_296()
    revision = modelo.revisions["2024-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert "modelo-296-total" in owned


def test_modelo_296_total_copies_source_casilla() -> None:
    """Casilla 05 equals casilla 04 per the AEAT form's own printed total row."""
    modelo, catalogues = _load_modelo_296()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_SOURCE_CASILLA: Decimal("500.00")},
        date_context={"filing_period": date(2024, 12, 31)},
        m303_regimen_simplificado_scope=None,
    )
    assert result.values[_TARGET_CASILLA] == Decimal("500.00")
