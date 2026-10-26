"""Modelo 341's printed compensation rows require explicit rates and add their amounts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


@pytest.mark.parametrize("year", (2022, 2025))
def test_compensation_total_adds_the_three_independently_stated_rates(year: int) -> None:
    modelo, catalogues = committed_modelo("341")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=year,
        period="1T",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    result = calculate_registry_snapshot(
        snapshot,
        date_context={},
        inputs={
            "01": Decimal("1000"),
            "02": Decimal("500"),
            "03": Decimal("200"),
            "04": Decimal("12"),
            "05": Decimal("10.5"),
            "06": Decimal("12"),
        },
    )
    assert {str(key): result.values[key] for key in ("07", "08", "09", "10")} == {
        "07": Decimal("120.00"),
        "08": Decimal("52.50"),
        "09": Decimal("24.00"),
        "10": Decimal("196.50"),
    }
