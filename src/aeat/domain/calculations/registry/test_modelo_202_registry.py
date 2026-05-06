"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryValidator, build_snapshot, calculate_registry_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_202():
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "202")
    return modelo, catalogues


def test_committed_modelo_202_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_202()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2019-2022", "2023-2024", "2025-y-siguientes"}


@pytest.mark.parametrize(
    (
        "filing_year",
        "period",
        "filing_period",
        "expected_revision",
        "extra_inputs",
        "expected_38",
        "expected_13",
        "expected_18",
        "expected_32",
    ),
    [
        (
            2024,
            "3P",
            date(2024, 12, 20),
            "2023-2024",
            {},
            Decimal("13.00"),
            Decimal("998.00"),
            Decimal("249.50"),
            Decimal("89.60"),
        ),
        (
            2025,
            "1P",
            date(2025, 4, 20),
            "2025-y-siguientes",
            {"67": Decimal("2.00")},
            Decimal("15.00"),
            Decimal("1000.00"),
            Decimal("250.00"),
            Decimal("90.00"),
        ),
    ],
)
def test_committed_modelo_202_calculates_foundation_formula_chain(
    filing_year: int,
    period: str,
    filing_period: date,
    expected_revision: str,
    extra_inputs: dict[str, Decimal],
    expected_38: Decimal,
    expected_13: Decimal,
    expected_18: Decimal,
    expected_32: Decimal,
) -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period=period,
    )
    assert snapshot.revision.id == expected_revision

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("100.00"),
            "04": Decimal("1000.00"),
            "05": Decimal("10.00"),
            "06": Decimal("4.00"),
            "07": Decimal("3.00"),
            "08": Decimal("6.00"),
            "16": Decimal("2000.00"),
            "17": Decimal("25.00"),
            "27": Decimal("50.00"),
            "28": Decimal("25.00"),
            "29": Decimal("80.00"),
            "30": Decimal("40.00"),
            "31": Decimal("10.00"),
            "33": Decimal("300.00"),
            "37": Decimal("5.00"),
            "40": Decimal("12.00"),
            "47": Decimal("10.00"),
            "48": Decimal("5.00"),
            "49": Decimal("3.00"),
            **extra_inputs,
        },
        date_context={"filing_period": filing_period},
    )

    assert result.values["03"] == Decimal("1700.00")
    assert result.values["38"] == expected_38
    assert result.values["39"] == Decimal("15.00")
    assert result.values["13"] == expected_13
    assert result.values["18"] == expected_18
    assert result.values["32"] == expected_32
    assert result.values["34"] == Decimal("300.00")


def test_committed_modelo_202_static_cross_reference_and_construct_are_declared() -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="2P",
    )
    decision = snapshot.live_cross_references["modelo-202-static-documentation"]
    construct = snapshot.constructs["modelo-202-foundation"]

    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "presentation" in decision.forbidden_actions
    assert "modelo-202-portal" in construct.application_links
    assert set(construct.live_cross_references) == {"modelo-202-static-documentation"}
    assert set(construct.workbook_parity_refs) == {"modelo-202-dr-xlsx-2025"}
