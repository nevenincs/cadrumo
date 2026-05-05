"""Tests for committed AEAT registry definitions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import (
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
    parse_export_payload,
    resolve_export_layout,
    resolve_relation_values,
)

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


@pytest.mark.parametrize(
    ("filing_year", "revision_id", "filing_period", "source_ref", "legal_ref"),
    [
        (2019, "2019-2023", date(2019, 3, 31), "aeat-dr-131-2019-2023-v101", "orden-hac-1264-2018:art-4"),
        (2023, "2019-2023", date(2023, 3, 31), "aeat-dr-131-2019-2023-v101", "orden-hfp-1172-2022:art-4"),
        (2024, "2024", date(2024, 3, 31), "aeat-dr-131-2024", "orden-hfp-1359-2023:art-4"),
        (2025, "2025", date(2025, 3, 31), "aeat-dr-131-2025", "orden-hac-1347-2024:art-4"),
        (2026, "2026", date(2026, 3, 31), "aeat-dr-131-2026", "orden-hac-1425-2025:art-4"),
    ],
)
def test_committed_modelo_131_registry_snapshot_calculates_objective_estimation_totals(
    filing_year: int,
    revision_id: str,
    filing_period: date,
    source_ref: str,
    legal_ref: str,
) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "131")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
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
        date_context={"filing_period": filing_period},
    )

    assert snapshot.revision.id == revision_id
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
    assert source_ref in snapshot.sources
    assert legal_ref in snapshot.legal


def test_committed_modelo_180_registry_snapshot_calculates_annual_summary_from_modelo_115_relations() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "180")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="0A",
    )
    relation_values = resolve_relation_values(
        snapshot.revision,
        {
            "modelo-180-rel-115-perceptores-anual": (
                Decimal("1"),
                Decimal("1"),
                Decimal("2"),
                Decimal("1"),
            ),
            "modelo-180-rel-115-base-anual": (
                Decimal("250.10"),
                Decimal("749.90"),
                Decimal("1200.00"),
                Decimal("-50.25"),
            ),
            "modelo-180-rel-115-retenciones-anual": (
                Decimal("47.52"),
                Decimal("142.48"),
                Decimal("228.00"),
                Decimal("0.00"),
            ),
        },
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 12, 31)},
        relation_values=relation_values,
    )

    assert result.values["decl.total-perceptores"] == Decimal("5")
    assert result.values["decl.base-total"] == Decimal("2149.75")
    assert result.values["decl.retenciones-total"] == Decimal("418.00")
    entries = {entry.target: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-180-rel-115-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


def test_committed_modelo_180_record_design_parses_declarante_and_perceptor_records() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(modelo for modelo in modelos if modelo.id == "180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="0A",
    )
    layout = resolve_export_layout(snapshot).layout
    declarante = _fixed_width_record(
        500,
        {
            (1, 1): "1",
            (2, 4): "180",
            (5, 8): "2026",
            (9, 17): "B12345678",
            (136, 144): "000000002",
            (145, 160): " " + "100050".zfill(15),
            (161, 175): "19010".zfill(15),
        },
    )
    perceptor = _fixed_width_record(
        500,
        {
            (1, 1): "2",
            (2, 4): "180",
            (5, 8): "2026",
            (9, 17): "B12345678",
            (18, 26): "12345678Z",
            (36, 75): "ARRENDADOR EJEMPLO".ljust(40),
            (76, 77): "28",
            (78, 78): "1",
            (79, 92): "N" + "2500".zfill(13),
            (97, 109): "475".zfill(13),
            (110, 113): "2025",
            (114, 114): "1",
            (115, 134): "1234567VK4713C0001XY",
            (321, 322): "28",
            (323, 327): "28013",
        },
    )

    parsed = parse_export_payload(layout, (declarante + perceptor).encode("latin-1"))
    casillas = {field.casilla_id: field.value for field in parsed.casillas}

    assert casillas["decl.total-perceptores"] == Decimal("2")
    assert casillas["decl.base-total"] == Decimal("1000.50")
    assert casillas["decl.retenciones-total"] == Decimal("190.10")
    assert casillas["perc.base"] == Decimal("-25.00")
    assert casillas["perc.retenciones"] == Decimal("4.75")


def _fixed_width_record(length: int, fields: dict[tuple[int, int], str]) -> str:
    record = [" "] * length
    for (start, end), value in fields.items():
        if len(value) != end - start + 1:
            raise AssertionError(f"field {start}-{end} has length {len(value)}")
        record[start - 1 : end] = value
    return "".join(record)
