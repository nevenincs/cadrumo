"""Tests for the committed Modelo 194 registry foundation."""

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

_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


def _load_modelo_194():
    return _committed_modelo("194")


def test_modelo_194_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_194()
    assert modelo.id == "194"
    assert modelo.revisions, "194 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_194_formula_owned_by_construct() -> None:
    modelo, _ = _load_modelo_194()
    revision = modelo.revisions["2019-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert "modelo-194-total" in owned


def test_modelo_194_total_copies_source_casilla() -> None:
    """Casilla 05 equals casilla 04 per the AEAT form's own printed total row."""
    modelo, catalogues = _load_modelo_194()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2019, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_SOURCE_CASILLA: Decimal("500.00")},
        date_context={"filing_period": date(2019, 12, 31)},
    )
    assert result.values[_TARGET_CASILLA] == Decimal("500.00")
