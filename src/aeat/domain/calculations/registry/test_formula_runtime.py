"""Tests for registry-backed formula runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._schema import RegistrySnapshot
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _committed_modelo_130_snapshot() -> RegistrySnapshot:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )


def test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order() -> None:
    snapshot = _committed_modelo_130_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "13": Decimal("0"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    order = {entry.target: index for index, entry in enumerate(result.entries)}
    assert order["03"] < order["04"] < order["07"] < order["12"] < order["14"] < order["17"] < order["19"]
    assert order["09"] < order["11"] < order["12"]
    assert result.values["19"] == Decimal("880.00")
    assert result.entries[0].legal_refs == ("rd-439-2007:art-110",)


def test_registry_formula_runtime_rejects_non_decimal_input() -> None:
    snapshot = _committed_modelo_130_snapshot()

    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            snapshot,
            inputs=cast("dict[str, Decimal]", {"01": 100}),
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_missing_parameter_axis() -> None:
    snapshot = _committed_modelo_130_snapshot()

    with pytest.raises(Exception, match="requires date axis"):
        calculate_registry_snapshot(
            snapshot,
            inputs={
                "01": Decimal("100"),
                "02": Decimal("0"),
                "05": Decimal("0"),
                "06": Decimal("0"),
                "08": Decimal("0"),
                "10": Decimal("0"),
                "13": Decimal("0"),
                "15": Decimal("0"),
                "16": Decimal("0"),
                "18": Decimal("0"),
            },
            date_context={},
        )
