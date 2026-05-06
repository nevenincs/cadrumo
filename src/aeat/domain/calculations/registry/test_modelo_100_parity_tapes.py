"""Modelo 100 scenario/tape parity coverage."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from aeat.core.paths import PROJECT_ROOT

from ._loader import load_registry_tree
from ._parity_tapes import ParityScenario, replay_parity_tape, run_parity_scenario, save_parity_tape
from ._snapshot import build_snapshot
from ._workbook_parity import SyntheticInputSet, SyntheticInputValue, WorkbookCellRef

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_modelo_100_renta_parity_tape_covers_economic_activity_and_payments(tmp_path: Path) -> None:
    root = tmp_path / "renta-open-parity"
    workbook_path = root / "data" / "modelo_100" / "files" / "modelo-100-renta-open-parity.xlsx"
    scenario_path = root / "scenarios" / "modelo-100-renta-open-parity.json"
    tape_path = root / "tapes" / "modelo-100-renta-open-parity.json"
    _write_modelo_100_renta_parity_workbook(workbook_path)
    scenario = _modelo_100_renta_parity_scenario()

    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo_100 = next(modelo for modelo in modelos if modelo.id == "100")
    snapshot = build_snapshot(modelo_100, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A")
    cross_reference = snapshot.live_cross_references["modelo-100-renta-web-open"]

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is True
    assert cross_reference.requires_authentication is False

    tape = run_parity_scenario(
        scenario,
        registry_root=PROJECT_ROOT / "registry" / "aeat",
        source_root=PROJECT_ROOT,
        scenario_path=scenario_path,
    )

    assert tape.report.status == "match"
    comparisons = {comparison.output_id: comparison for comparison in tape.report.comparisons}
    assert comparisons["casilla-0180"].actual_registry_value == Decimal("1200.00")
    assert comparisons["casilla-0224"].actual_registry_value == Decimal("850.00")
    assert comparisons["casilla-0235"].actual_registry_value == Decimal("825.00")
    assert comparisons["casilla-0604"].actual_registry_value == Decimal("100.00")
    assert comparisons["casilla-0609"].actual_registry_value == Decimal("191.00")
    assert set(comparisons["casilla-0224"].source_refs) == {
        "aeat-dr-100-2025-dictionary",
        "aeat-dr-100-2025-xsd",
        "aeat-renta-2025-manual-parte1",
        "boe-modelo-100-2025-form",
    }

    save_parity_tape(tape, tape_path)
    replay = replay_parity_tape(
        tape,
        registry_root=PROJECT_ROOT / "registry" / "aeat",
        source_root=PROJECT_ROOT,
        tape_path=tape_path,
    )

    assert replay.status == "match"
    assert replay.differences == ()


def _write_modelo_100_renta_parity_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Renta"
    worksheet["A1"] = 1000
    worksheet["A2"] = 200
    worksheet["A3"] = 300
    worksheet["A4"] = 50
    worksheet["A5"] = 10
    worksheet["A6"] = 5
    worksheet["A7"] = 1
    worksheet["A8"] = 2
    worksheet["A9"] = 3
    worksheet["A10"] = 4
    worksheet["A11"] = 45
    worksheet["A12"] = 55
    for row in range(13, 26):
        worksheet[f"A{row}"] = row - 12
    worksheet["B1"] = "=A1+A2"
    worksheet["B2"] = "=B1-(A3+A4)"
    worksheet["B3"] = "=B2-A5-A6-A7-A8-A9-A10"
    worksheet["B4"] = "=A11+A12"
    worksheet["B5"] = "=SUM(A13:A25)+B4"
    workbook.save(path)
    workbook.close()


def _modelo_100_renta_parity_scenario() -> ParityScenario:
    return ParityScenario(
        id="modelo-100-renta-web-open-2025-economic-activity-payments",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        workbook_path=Path("../data/modelo_100/files/modelo-100-renta-open-parity.xlsx"),
        synthetic_input=SyntheticInputSet(
            id="modelo-100-renta-web-open-direct-estimation-basic",
            modelo="100",
            revision="2025",
            values=(
                _input("0171", 1000, "A1"),
                _input("0172", 200, "A2"),
                _input("0181", 300, "A3"),
                _input("0219", 50, "A4"),
                _input("0225", 10, "A5"),
                _input("0236", 5, "A6"),
                _input("0232", 1, "A7"),
                _input("0233", 2, "A8"),
                _input("0234", 3, "A9"),
                _input("0237", 4, "A10"),
                SyntheticInputValue(
                    id="rel-130-pagos-fraccionados",
                    value=45,
                    workbook_cell=WorkbookCellRef(sheet="Renta", coordinate="A11"),
                ),
                SyntheticInputValue(
                    id="rel-131-pagos-fraccionados",
                    value=55,
                    workbook_cell=WorkbookCellRef(sheet="Renta", coordinate="A12"),
                ),
                _input("0592", 1, "A13"),
                _input("0593", 2, "A14"),
                _input("0594", 3, "A15"),
                _input("0596", 4, "A16"),
                _input("0597", 5, "A17"),
                _input("0153", 6, "A18"),
                _input("0599", 7, "A19"),
                _input("0600", 8, "A20"),
                _input("0601", 9, "A21"),
                _input("0602", 10, "A22"),
                _input("0603", 11, "A23"),
                _input("0605", 12, "A24"),
                _input("0606", 13, "A25"),
                SyntheticInputValue(
                    id="direct-estimation-mode-normal",
                    value=Decimal("1"),
                    registry_binding="renta-2025-modelo-100-estimacion-directa-es-normal",
                ),
            ),
        ),
        output_cells={
            "casilla-0180": WorkbookCellRef(sheet="Renta", coordinate="B1"),
            "casilla-0224": WorkbookCellRef(sheet="Renta", coordinate="B2"),
            "casilla-0235": WorkbookCellRef(sheet="Renta", coordinate="B3"),
            "casilla-0604": WorkbookCellRef(sheet="Renta", coordinate="B4"),
            "casilla-0609": WorkbookCellRef(sheet="Renta", coordinate="B5"),
        },
        registry_outputs={
            "casilla-0180": "0180",
            "casilla-0224": "0224",
            "casilla-0235": "0235",
            "casilla-0604": "0604",
            "casilla-0609": "0609",
        },
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("45.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("55.00"),
        },
        notes=(
            "Renta WEB Open is the classified read-only executable parity surface for this synthetic shape.",
            "Authenticated Renta surfaces remain observation-only and are not used by this scenario.",
        ),
    )


def _input(casilla_id: str, value: Decimal | int, coordinate: str) -> SyntheticInputValue:
    return SyntheticInputValue(
        id=f"casilla-{casilla_id}",
        value=value,
        workbook_cell=WorkbookCellRef(sheet="Renta", coordinate=coordinate),
        registry_binding=casilla_id,
    )
