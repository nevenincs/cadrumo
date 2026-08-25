"""Tests for committed AEAT registry definitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id, validated_casilla_id_map
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.relations import resolve_relation_values
from ..schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _inputs(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="committed registry input casillas")


def test_committed_modelo_130_registry_snapshot_is_calculable(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("130", 2026, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_inputs(
            {
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "06": Decimal("100"),
                "08": Decimal("2000"),
                "10": Decimal("10"),
                "16": Decimal("0"),
                "18": Decimal("0"),
            },
        ),
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("6000"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    assert snapshot.revision.id == "2019-y-siguientes"
    assert snapshot.revision.period_selector.year_from == 2019
    assert {entry.target_casilla_id for entry in result.entries} == {
        "03",
        "04",
        "07",
        "09",
        "11",
        "12",
        "13",
        "14",
        "15",
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
        inputs=_inputs(
            {
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
        ),
        date_context={"filing_period": date(2026, 3, 31)},
    )

    assert {entry.target_casilla_id for entry in result.entries} == {"28", "30"}
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["28"].operand_refs == ("03", "06", "09", "12", "15", "18", "21", "24", "27")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-108"} <= set(entries["28"].legal_refs)
    assert {"aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"} <= set(entries["28"].source_refs)
    assert entries["30"].operand_refs == ("28", "29")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-108"} <= set(entries["30"].legal_refs)
    assert {"aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"} <= set(entries["30"].source_refs)
    assert "ley-35-2006:art-99" in snapshot.legal
    assert "aeat-modelo-111-instructions" in snapshot.sources


def test_committed_modelo_115_registry_snapshot_calculates_rental_withholding(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("115", 2026, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_inputs(
            {
                "01": Decimal("1"),
                "02": Decimal("1250.50"),
                "04": Decimal("10.00"),
            },
        ),
        date_context={"filing_period": date(2026, 3, 31)},
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("02", "irpf.urban_rental_withholding_rate")
    assert entries["03"].operand_casilla_refs == ("02",)
    assert entries["03"].operand_values == (Decimal("1250.50"), Decimal("19"))
    assert entries["03"].value == Decimal("237.60")
    assert {"rd-439-2007:art-100"} <= set(entries["03"].legal_refs)
    assert {"aeat-modelo-115-180-folleto-actividades"} <= set(entries["03"].source_refs)
    assert entries["05"].operand_refs == ("03", "04")
    assert entries["05"].operand_casilla_refs == ("03", "04")
    assert {"ley-35-2006:art-99", "rd-439-2007:art-100", "rd-439-2007:art-108"} <= set(entries["05"].legal_refs)
    assert {"aeat-dr-115-2019-v13", "aeat-modelo-115-guia-censal"} <= set(entries["05"].source_refs)


def test_committed_modelo_123_registry_snapshot_calculates_current_totals(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("123", 2026, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_inputs(
            {
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
        ),
        date_context={"filing_period": date(2026, 3, 31)},
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
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
        inputs=_inputs(
            {
                "01": Decimal("2"),
                "02": Decimal("1201.00"),
                "03": Decimal("228.19"),
                "04": Decimal("0"),
                "05": Decimal("7.50"),
                "07": Decimal("12.25"),
            },
        ),
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
    assert {entry.target_casilla_id for entry in result.entries} == {"06", "08"}


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
    snapshot = registry_snapshot("131", filing_year, "1T", grade=RegistryAuthorityGrade.CALCULATION)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_inputs(
            {
                "01": Decimal("10000"),
                "02": Decimal("300"),
                "03": Decimal("2000"),
                "05": Decimal("4000"),
                "08": Decimal("50"),
                "09": Decimal("25"),
                "12": Decimal("15"),
                "14": Decimal("20"),
            },
        ),
        date_context={"filing_period": filing_period},
        binding_values={f"modelo-131-{revision_id}-resultados-negativos-anteriores": Decimal("10")},
    )

    assert snapshot.revision.id == revision_id
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    expected_entries = {
        "04",
        "06",
        "07",
        "10",
        "13",
        "15",
        "saldo-negativo-fin-periodo",
    }
    if revision_id in ("2024", "2025", "2026"):
        # 2024, 2025, and 2026 additionally carry the estimación-objetiva
        # módulos engine (fase 1ª rendimiento neto previo, fase 2ª
        # rendimiento neto minorado, fase 3ª rendimiento neto de módulos,
        # fase 4ª reducción general), a bounded first-slice computed
        # reference figure that never substitutes for the manual casilla 01.
        # The 2024 and 2026 revisions replicate the 2025 engine per-year
        # roll-forward/back-fill (Orden HFP/1359/2023 and Orden
        # HAC/1425/2025 both reproduce the same tabled coefficients as
        # Orden HAC/1347/2024).
        expected_entries |= {
            "modulos-rendimiento-neto-previo",
            "modulos-rendimiento-neto-minorado",
            "modulos-rendimiento-neto-modulos",
            "modulos-rendimiento-neto-actividad",
        }
    if revision_id in ("2024", "2025"):
        # 2024 and 2025 additionally carry the Fase 3ª índices correctores
        # generales (b.1, b.2, b.4) advisory-support flags, which never fire
        # with no blank/zero declared índices (see
        # test_modelo_131_modulos_engine.TestModulosIndicesGeneralesAdvisoryFlags).
        expected_entries |= {
            "modulos-pequena-dimension-ignorado-flag",
            "modulos-temporada-inicio-actividad-conflicto-flag",
        }
    assert set(entries) == expected_entries
    assert entries["04"].operand_refs == ("03", "irpf.objective_no_base_fractional_payment_rate")
    assert entries["06"].operand_refs == ("05", "irpf.objective_agriculture_fractional_payment_rate")
    assert entries["07"].operand_refs == ("02", "04", "06")
    assert entries["10"].operand_refs == ("07", "08", "09")
    assert entries["13"].operand_refs == ("10", "11", "12")
    assert entries["15"].operand_refs == ("13", "14")
    assert source_ref in snapshot.sources
    assert legal_ref in snapshot.legal


def test_committed_modelo_180_registry_snapshot_calculates_annual_summary_from_modelo_115_relations_and_count_binding(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("180", 2026, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    relation_values = resolve_relation_values(
        snapshot.revision,
        {
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
    binding_values = {"modelo-180-115-perceptores-anual": Decimal("2")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2026, 12, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert set(entries) == {"decl.base-total", "decl.retenciones-total"}
    assert result.values["decl.total-perceptores"] == binding_values["modelo-180-115-perceptores-anual"]
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


_MODELO_180_DECLARANTE_FIELDS: dict[tuple[int, int], str] = {
    (1, 1): "1",
    (2, 4): "180",
    (5, 8): "2026",
    (9, 17): "B12345678",
    # Tipo de soporte. The layout declares this position a LITERAL "T" -- the
    # design admits only "C" (cinta magnetica) and "T" (transmision telematica),
    # and this producer writes a telematic file -- so a payload that leaves it
    # blank cannot parse against the layout it is meant to exercise.
    (58, 58): "T",
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


def _expected_casilla_value(casilla_id: object, value: object) -> tuple[CasillaId, object]:
    return (
        validated_casilla_id(casilla_id, surface="_MODELO_180_EXPECTED_CASILLAS"),
        value,
    )


_MODELO_180_EXPECTED_CASILLAS: tuple[tuple[CasillaId, object], ...] = (
    _expected_casilla_value("decl.total-perceptores", Decimal("2")),
    _expected_casilla_value("decl.base-total", Decimal("1000.50")),
    _expected_casilla_value("decl.retenciones-total", Decimal("190.10")),
    _expected_casilla_value("perc.nif", "12345678Z"),
    _expected_casilla_value("perc.nif-representante-legal", "87654321X"),
    _expected_casilla_value("perc.nombre", "ARRENDADOR EJEMPLO"),
    _expected_casilla_value("perc.provincia", "28"),
    _expected_casilla_value("perc.modalidad", "1"),
    _expected_casilla_value("perc.base", Decimal("-25.00")),
    _expected_casilla_value("perc.porcentaje-retencion", Decimal("0.00")),
    _expected_casilla_value("perc.retenciones", Decimal("4.75")),
    _expected_casilla_value("perc.ejercicio-devengo", Decimal("2025")),
    _expected_casilla_value("perc.situacion-inmueble", "1"),
    _expected_casilla_value("perc.referencia-catastral", "1234567VK4713C0001XY"),
    _expected_casilla_value("perc.inmueble-tipo-via", "CL"),
    _expected_casilla_value("perc.inmueble-nombre-via", "CALLE MAYOR"),
    _expected_casilla_value("perc.inmueble-tipo-numeracion", "NUM"),
    _expected_casilla_value("perc.inmueble-numero-casa", "12"),
    _expected_casilla_value("perc.inmueble-calificador-numero", "BIS"),
    _expected_casilla_value("perc.inmueble-bloque", "A"),
    _expected_casilla_value("perc.inmueble-portal", "1"),
    _expected_casilla_value("perc.inmueble-escalera", "2"),
    _expected_casilla_value("perc.inmueble-planta", "03"),
    _expected_casilla_value("perc.inmueble-puerta", "B"),
    _expected_casilla_value("perc.inmueble-complemento", "EDIFICIO CENTRAL"),
    _expected_casilla_value("perc.inmueble-localidad", "MADRID"),
    _expected_casilla_value("perc.inmueble-municipio", "MADRID"),
    _expected_casilla_value("perc.inmueble-codigo-municipio", "28079"),
    _expected_casilla_value("perc.inmueble-provincia", "28"),
    _expected_casilla_value("perc.inmueble-codigo-postal", "28013"),
)


@pytest.fixture(scope="module")
def _modelo_180_parsed_casillas(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> dict[CasillaId, object]:
    """Parse the synthetic Modelo 180 declarante + perceptor record bundle once.

    Module-scoped so the record-design parse runs a single time and
    every parametrize case in
    test_committed_modelo_180_record_design_parses asserts against
    the same payload. This is a genuine filing/export-record concern
    (parses a fixed-width export layout), so it keeps the default FILING
    grade -- ``registry_snapshot`` is now session-scoped, so a module-scoped
    consumer no longer needs to bypass it via the raw ``registry_authority``.

    The fixed-width field maps and the expected casilla values are
    module-level constants so the test row table reads top-down.
    """
    snapshot = registry_snapshot("180", 2026, "0A")
    layout = resolve_export_layout(snapshot).layout
    declarante = _fixed_width_record(500, _MODELO_180_DECLARANTE_FIELDS)
    perceptor = _fixed_width_record(500, _MODELO_180_PERCEPTOR_FIELDS)
    parsed = parse_export_payload(layout, (declarante + perceptor).encode("latin-1"))
    return {field.casilla_id: field.value for field in parsed.casillas if field.casilla_id is not None}


@pytest.mark.parametrize(("casilla_id", "expected_value"), _MODELO_180_EXPECTED_CASILLAS)
def test_committed_modelo_180_record_design_parses_casilla(
    _modelo_180_parsed_casillas: dict[CasillaId, object],
    casilla_id: CasillaId,
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
