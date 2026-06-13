"""Tests for committed AEAT registry definitions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .. import (
    calculate_registry_snapshot,
    parse_export_payload,
    resolve_export_layout,
    resolve_relation_values,
)
from .._authority import ValidatedRegistryAuthority
from .._schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_modelo_130_registry_snapshot_is_calculable(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("130", 2026, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("6000"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    assert snapshot.revision.id == "2019-y-siguientes"
    assert snapshot.revision.period_selector.year_from == 2019
    assert {entry.target for entry in result.entries} == {
        "03",
        "04",
        "07",
        "09",
        "11",
        "12",
        "13",
        "14",
        "17",
        "19",
        "saldo-negativo-fin-periodo",
    }
    assert "rd-439-2007:art-110" in snapshot.legal
    assert "aeat-dr-130-2019-v12" in snapshot.sources


def test_committed_modelo_111_registry_snapshot_calculates_liquidacion_from_retentions(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("111", 2026, "1T")
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

    assert {entry.target for entry in result.entries} == {"28", "30"}
    entries = {entry.target: entry for entry in result.entries}
    assert entries["28"].operand_refs == ("03", "06", "09", "12", "15", "18", "21", "24", "27")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-109"} <= set(entries["28"].legal_refs)
    assert {"aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"} <= set(entries["28"].source_refs)
    assert entries["30"].operand_refs == ("28", "29")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-109"} <= set(entries["30"].legal_refs)
    assert {"aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"} <= set(entries["30"].source_refs)
    assert "ley-35-2006:art-99" in snapshot.legal
    assert "aeat-modelo-111-instructions" in snapshot.sources


def test_committed_modelo_115_registry_snapshot_calculates_rental_withholding(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("115", 2026, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("1"),
            "02": Decimal("1250.50"),
            "04": Decimal("10.00"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
    )

    entries = {entry.target: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("02", "irpf.urban_rental_withholding_rate")
    assert {"rd-439-2007:art-100"} <= set(entries["03"].legal_refs)
    assert {"aeat-modelo-115-180-folleto-actividades"} <= set(entries["03"].source_refs)
    assert entries["05"].operand_refs == ("03", "04")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-100", "rd-439-2007:art-109"} <= set(entries["05"].legal_refs)
    assert {"aeat-dr-115-2019-v13", "aeat-modelo-115-guia-censal"} <= set(entries["05"].source_refs)


def test_committed_modelo_123_registry_snapshot_calculates_current_totals(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("123", 2026, "1T")
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

    entries = {entry.target: entry for entry in result.entries}
    assert set(entries) == {"03", "06", "09", "12", "14"}
    assert entries["03"].operand_refs == ("01", "02")
    assert entries["06"].operand_refs == ("04", "05")
    assert entries["09"].operand_refs == ("07", "08")
    assert entries["12"].operand_refs == ("09", "11")
    assert entries["14"].operand_refs == ("12", "13")


def test_committed_modelo_123_registry_snapshot_uses_2019_2023_shape(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("123", 2023, "4T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01-legacy": Decimal("2"),
            "02-legacy": Decimal("1201.00"),
            "03-legacy": Decimal("228.19"),
            "04-legacy": Decimal("0"),
            "05-legacy": Decimal("7.50"),
            "07-legacy": Decimal("12.25"),
        },
        date_context={"filing_period": date(2023, 12, 31)},
    )

    assert snapshot.revision.id == "2019-2023"
    assert tuple(casilla.id for casilla in snapshot.revision.casillas) == (
        "01-legacy",
        "02-legacy",
        "03-legacy",
        "04-legacy",
        "05-legacy",
        "06-legacy",
        "07-legacy",
        "08-legacy",
    )
    assert {entry.target for entry in result.entries} == {"06-legacy", "08-legacy"}


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
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("131", filing_year, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("300"),
            "03": Decimal("2000"),
            "05": Decimal("4000"),
            "08": Decimal("50"),
            "09": Decimal("25"),
            "12": Decimal("15"),
            "14": Decimal("20"),
        },
        date_context={"filing_period": filing_period},
        binding_values={f"modelo-131-{revision_id}-resultados-negativos-anteriores": Decimal("10")},
    )

    assert snapshot.revision.id == revision_id
    entries = {entry.target: entry for entry in result.entries}
    assert set(entries) == {
        "04",
        "06",
        "07",
        "10",
        "13",
        "15",
        "saldo-negativo-fin-periodo",
    }
    assert entries["04"].operand_refs == ("03", "irpf.objective_no_base_fractional_payment_rate")
    assert entries["06"].operand_refs == ("05", "irpf.objective_agriculture_fractional_payment_rate")
    assert entries["07"].operand_refs == ("02", "04", "06")
    assert entries["10"].operand_refs == ("07", "08", "09")
    assert entries["13"].operand_refs == ("10", "11", "12")
    assert entries["15"].operand_refs == ("13", "14")
    assert source_ref in snapshot.sources
    assert legal_ref in snapshot.legal


def test_committed_modelo_180_registry_snapshot_calculates_annual_summary_from_modelo_115_relations(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("180", 2026, "0A")
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

    entries = {entry.target: entry for entry in result.entries}
    assert set(entries) == {"decl.total-perceptores", "decl.base-total", "decl.retenciones-total"}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-180-rel-115-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


_MODELO_180_DECLARANTE_FIELDS: dict[tuple[int, int], str] = {
    (1, 1): "1",
    (2, 4): "180",
    (5, 8): "2026",
    (9, 17): "B12345678",
    (136, 144): "000000002",
    (145, 160): " " + "100050".zfill(15),
    (161, 175): "19010".zfill(15),
}

_MODELO_180_PERCEPTOR_FIELDS: dict[tuple[int, int], str] = {
    (1, 1): "2",
    (2, 4): "180",
    (5, 8): "2026",
    (9, 17): "B12345678",
    (18, 26): "12345678Z",
    (27, 35): "87654321X",
    (36, 75): "ARRENDADOR EJEMPLO".ljust(40),
    (76, 77): "28",
    (78, 78): "1",
    (79, 92): "N" + "2500".zfill(13),
    (93, 96): "0000",
    (97, 109): "475".zfill(13),
    (110, 113): "2025",
    (114, 114): "1",
    (115, 134): "1234567VK4713C0001XY",
    (135, 139): "CL".ljust(5),
    (140, 189): "CALLE MAYOR".ljust(50),
    (190, 192): "NUM",
    (193, 197): "12".ljust(5),
    (198, 200): "BIS",
    (201, 203): "A".ljust(3),
    (204, 206): "1".ljust(3),
    (207, 209): "2".ljust(3),
    (210, 212): "03".ljust(3),
    (213, 215): "B".ljust(3),
    (216, 255): "EDIFICIO CENTRAL".ljust(40),
    (256, 285): "MADRID".ljust(30),
    (286, 315): "MADRID".ljust(30),
    (316, 320): "28079",
    (321, 322): "28",
    (323, 327): "28013",
}

_MODELO_180_EXPECTED_CASILLAS: tuple[tuple[str, object], ...] = (
    ("decl.total-perceptores", Decimal("2")),
    ("decl.base-total", Decimal("1000.50")),
    ("decl.retenciones-total", Decimal("190.10")),
    ("perc.nif", "12345678Z"),
    ("perc.nif-representante-legal", "87654321X"),
    ("perc.nombre", "ARRENDADOR EJEMPLO"),
    ("perc.provincia", "28"),
    ("perc.modalidad", "1"),
    ("perc.base", Decimal("-25.00")),
    ("perc.porcentaje-retencion", "0000"),
    ("perc.retenciones", Decimal("4.75")),
    ("perc.ejercicio-devengo", Decimal("2025")),
    ("perc.situacion-inmueble", "1"),
    ("perc.referencia-catastral", "1234567VK4713C0001XY"),
    ("perc.inmueble-tipo-via", "CL"),
    ("perc.inmueble-nombre-via", "CALLE MAYOR"),
    ("perc.inmueble-tipo-numeracion", "NUM"),
    ("perc.inmueble-numero-casa", "12"),
    ("perc.inmueble-calificador-numero", "BIS"),
    ("perc.inmueble-bloque", "A"),
    ("perc.inmueble-portal", "1"),
    ("perc.inmueble-escalera", "2"),
    ("perc.inmueble-planta", "03"),
    ("perc.inmueble-puerta", "B"),
    ("perc.inmueble-complemento", "EDIFICIO CENTRAL"),
    ("perc.inmueble-localidad", "MADRID"),
    ("perc.inmueble-municipio", "MADRID"),
    ("perc.inmueble-codigo-municipio", "28079"),
    ("perc.inmueble-provincia", "28"),
    ("perc.inmueble-codigo-postal", "28013"),
)


@pytest.fixture(scope="module")
def _modelo_180_parsed_casillas(
    registry_authority: ValidatedRegistryAuthority,
) -> dict[str, object]:
    """Parse the synthetic Modelo 180 declarante + perceptor record bundle once.

    Module-scoped so the record-design parse runs a single time and
    every parametrize case in
    test_committed_modelo_180_record_design_parses asserts against
    the same payload. Pulls the snapshot directly from the
    session-scoped ``registry_authority`` instead of the per-test
    ``registry_snapshot`` factory so the module scope is compatible.

    The fixed-width field maps and the expected casilla values are
    module-level constants so the test row table reads top-down.
    """
    snapshot = registry_authority.snapshot("180", filing_year=2026, period="0A")
    layout = resolve_export_layout(snapshot).layout
    declarante = _fixed_width_record(500, _MODELO_180_DECLARANTE_FIELDS)
    perceptor = _fixed_width_record(500, _MODELO_180_PERCEPTOR_FIELDS)
    parsed = parse_export_payload(layout, (declarante + perceptor).encode("latin-1"))
    return {field.casilla_id: field.value for field in parsed.casillas if field.casilla_id is not None}


@pytest.mark.parametrize(("casilla_id", "expected_value"), _MODELO_180_EXPECTED_CASILLAS)
def test_committed_modelo_180_record_design_parses_casilla(
    _modelo_180_parsed_casillas: dict[str, object],
    casilla_id: str,
    expected_value: object,
) -> None:
    """Modelo 180 fixed-width record-design parser yields the expected casilla value.

    One parametrize case per registered casilla. Each case carries
    a distinct test id (the casilla id), so a regression on a
    single casilla surfaces by name rather than by line number in
    a 30-assert chain.
    """
    assert _modelo_180_parsed_casillas[casilla_id] == expected_value


def _fixed_width_record(length: int, fields: dict[tuple[int, int], str]) -> str:
    record = [" "] * length
    for (start, end), value in fields.items():
        if len(value) != end - start + 1:
            raise AssertionError(f"field {start}-{end} has length {len(value)}")
        record[start - 1 : end] = value
    return "".join(record)
