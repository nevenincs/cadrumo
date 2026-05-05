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
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("13000")},
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
    assert {entry.target for entry in result.entries} == {"03", "04", "07", "09", "11", "12", "13", "14", "17", "19"}
    assert "rd-439-2007:art-110" in snapshot.legal
    assert "aeat-dr-130-2019-v12" in snapshot.sources


def test_committed_modelo_111_registry_snapshot_calculates_liquidacion_from_retentions() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "111")

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
            "03": Decimal("180.25"),
            "06": Decimal("12.10"),
            "09": Decimal("300.00"),
            "12": Decimal("14.40"),
            "15": Decimal("25.00"),
            "18": Decimal("0.50"),
            "21": Decimal("7.00"),
            "24": Decimal("8.00"),
            "27": Decimal("9.00"),
            "29": Decimal("40.00"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    assert result.values["28"] == Decimal("556.25")
    assert result.values["30"] == Decimal("516.25")
    assert {entry.target for entry in result.entries} == {"28", "30"}
    entries = {entry.target: entry for entry in result.entries}
    assert entries["28"].operand_refs == ("03", "06", "09", "12", "15", "18", "21", "24", "27")
    assert entries["28"].legal_refs == ("ley-35-2006:art-99", "rd-439-2007:art-109")
    assert entries["28"].source_refs == ("aeat-dr-111-2019-v18", "aeat-modelo-111-instructions")
    assert entries["30"].operand_refs == ("28", "29")
    assert entries["30"].legal_refs == ("ley-35-2006:art-99", "rd-439-2007:art-109")
    assert entries["30"].source_refs == ("aeat-dr-111-2019-v18", "aeat-modelo-111-instructions")
    assert "ley-35-2006:art-99" in snapshot.legal
    assert "aeat-modelo-111-instructions" in snapshot.sources


def test_committed_modelo_115_registry_snapshot_calculates_rental_withholding() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "115")

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
            "01": Decimal("1"),
            "02": Decimal("1250.50"),
            "04": Decimal("10.00"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    assert result.values["03"] == Decimal("237.60")
    assert result.values["05"] == Decimal("227.60")
    entries = {entry.target: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("02", "irpf.urban_rental_withholding_rate")
    assert entries["03"].legal_refs == ("rd-439-2007:art-100",)
    assert entries["03"].source_refs == ("aeat-modelo-115-180-folleto-actividades",)
    assert entries["05"].operand_refs == ("03", "04")
    assert entries["05"].legal_refs == ("ley-35-2006:art-99", "rd-439-2007:art-100", "rd-439-2007:art-109")
    assert entries["05"].source_refs == ("aeat-dr-115-2019-v13", "aeat-modelo-115-guia-censal")


def test_committed_modelo_123_registry_snapshot_calculates_current_totals() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "123")

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
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("1000.25"),
            "05": Decimal("200.75"),
            "07": Decimal("190.05"),
            "08": Decimal("38.14"),
            "10": Decimal("0"),
            "11": Decimal("7.50"),
            "13": Decimal("12.25"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    assert result.values["03"] == Decimal("5")
    assert result.values["06"] == Decimal("1201.00")
    assert result.values["09"] == Decimal("228.19")
    assert result.values["12"] == Decimal("235.69")
    assert result.values["14"] == Decimal("223.44")
    entries = {entry.target: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("01", "02")
    assert entries["06"].operand_refs == ("04", "05")
    assert entries["09"].operand_refs == ("07", "08")
    assert entries["12"].operand_refs == ("09", "11")
    assert entries["14"].operand_refs == ("12", "13")


def test_committed_modelo_123_registry_snapshot_uses_2019_2023_shape() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "123")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2023,
        period="4T",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("2"),
            "02": Decimal("1201.00"),
            "03": Decimal("228.19"),
            "04": Decimal("0"),
            "05": Decimal("7.50"),
            "07": Decimal("12.25"),
        },
        date_context={"filing_period": date(2023, 12, 31)},
    )

    assert snapshot.revision.id == "2019-2023"
    assert tuple(casilla.id for casilla in snapshot.revision.casillas) == (
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
    )
    assert result.values["06"] == Decimal("235.69")
    assert result.values["08"] == Decimal("223.44")


def test_committed_modelo_131_registry_snapshot_calculates_objective_estimation_totals() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "131")

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
            "02": Decimal("300"),
            "03": Decimal("2000"),
            "05": Decimal("4000"),
            "08": Decimal("50"),
            "09": Decimal("25"),
            "11": Decimal("10"),
            "12": Decimal("15"),
            "14": Decimal("20"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    assert result.values["04"] == Decimal("40.00")
    assert result.values["06"] == Decimal("80.00")
    assert result.values["07"] == Decimal("420.00")
    assert result.values["10"] == Decimal("345.00")
    assert result.values["13"] == Decimal("320.00")
    assert result.values["15"] == Decimal("300.00")
    entries = {entry.target: entry for entry in result.entries}
    assert set(entries) == {"04", "06", "07", "10", "13", "15"}
    assert entries["04"].operand_refs == ("03", "irpf.objective_no_base_fractional_payment_rate")
    assert entries["06"].operand_refs == ("05", "irpf.objective_agriculture_fractional_payment_rate")
    assert entries["07"].operand_refs == ("02", "04", "06")
    assert entries["10"].operand_refs == ("07", "08", "09")
    assert entries["13"].operand_refs == ("10", "11", "12")
    assert entries["15"].operand_refs == ("13", "14")
