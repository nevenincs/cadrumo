"""Input-validation contract test for modelo 115's calculation runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_modelo_115_rejects_unknown_input_casilla() -> None:
    """The runtime rejects synthetic input keyed by a casilla id the schema does not declare."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "115")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("1"),
        "02": Decimal("1000.00"),
        "04": Decimal("0.00"),
        "99": Decimal("0.00"),  # not declared on modelo 115
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    with pytest.raises(Exception, match="unknown registry input casilla"):
        calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)
