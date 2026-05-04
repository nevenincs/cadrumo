"""Tests for committed AEAT registry definitions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryValidator, build_snapshot, calculate_registry_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_committed_modelo_130_registry_snapshot_is_calculable() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "130")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )
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

    assert snapshot.revision.id == "2019-y-siguientes"
    assert snapshot.revision.period_selector.year_from == 2019
    assert result.values["03"] == Decimal("6000.00")
    assert result.values["04"] == Decimal("1200.00")
    assert result.values["07"] == Decimal("850.00")
    assert result.values["09"] == Decimal("40.00")
    assert result.values["11"] == Decimal("30.00")
    assert result.values["12"] == Decimal("880.00")
    assert result.values["19"] == Decimal("880.00")
    assert {entry.target for entry in result.entries} == {"03", "04", "07", "09", "11", "12", "14", "17", "19"}
    assert "rd-439-2007:art-110" in snapshot.legal
    assert "aeat-dr-130-2019-v12" in snapshot.sources
