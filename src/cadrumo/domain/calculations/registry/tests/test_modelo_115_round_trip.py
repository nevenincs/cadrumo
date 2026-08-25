"""Input-validation contract test for modelo 115's calculation runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01", surface="modelo 115 test casilla")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02", surface="modelo 115 test casilla")
_M115_RESULTADO_ANTERIOR_CASILLA: CasillaId = validated_casilla_id("04", surface="modelo 115 test casilla")
_M115_UNKNOWN_INPUT_CASILLA: CasillaId = validated_casilla_id("99", surface="modelo 115 unknown test casilla")


def test_modelo_115_rejects_unknown_input_casilla() -> None:
    """The runtime rejects synthetic input keyed by a casilla id the schema does not declare."""

    modelo, catalogues = _committed_modelo("115")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    inputs: dict[CasillaId, Decimal] = {
        _M115_PERCEPTORES_CASILLA: Decimal("1"),
        _M115_BASE_CASILLA: Decimal("1000.00"),
        _M115_RESULTADO_ANTERIOR_CASILLA: Decimal("0.00"),
        _M115_UNKNOWN_INPUT_CASILLA: Decimal("0.00"),  # not declared on modelo 115
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    with pytest.raises(RegistryValidationError, match="unknown registry input casilla"):
        calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)
