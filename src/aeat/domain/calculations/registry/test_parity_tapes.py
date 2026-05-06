"""Tests for the manual scenario/tape parity harness."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from aeat.core.paths import PROJECT_ROOT

from ._parity_tapes import (
    ParityScenario,
    generate_parity_tape_path,
    load_parity_scenario,
    load_parity_tape,
    replay_parity_tape,
    run_parity_scenario,
    save_parity_scenario,
    save_parity_tape,
)
from ._workbook_parity import SyntheticInputSet, SyntheticInputValue, WorkbookCellRef

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _write_modelo_130_parity_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Modelo"
    worksheet["A1"] = Decimal("10000")
    worksheet["A2"] = Decimal("4000")
    worksheet["A3"] = Decimal("250")
    worksheet["A4"] = Decimal("100")
    worksheet["A5"] = Decimal("2000")
    worksheet["A6"] = Decimal("10")
    worksheet["A7"] = Decimal("0")
    worksheet["A8"] = Decimal("0")
    worksheet["A9"] = Decimal("0")
    worksheet["A10"] = Decimal("0")
    worksheet["B1"] = "=MAX(0,MAX(0,(A1-A2)*20/100)-A3-A4)+MAX(0,A5*2/100-A6)-A7-A8-A9-A10"
    workbook.save(path)
    workbook.close()


def test_parity_scenario_round_trips_and_replays(tmp_path: Path) -> None:
    root = tmp_path / "parity"
    workbook_path = root / "data" / "modelo_130" / "files" / "130-parity.xlsx"
    scenario_path = root / "scenarios" / "modelo-130-parity.json"
    tape_path = root / "tapes" / "modelo-130-parity.json"
    _write_modelo_130_parity_workbook(workbook_path)

    scenario = ParityScenario(
        id="modelo-130-manual-parity",
        modelo="130",
        revision="2019-y-siguientes",
        filing_year=2026,
        period="1T",
        workbook_path=Path("../data/modelo_130/files/130-parity.xlsx"),
        synthetic_input=SyntheticInputSet(
            id="modelo-130-registry-parity-basic",
            modelo="130",
            revision="2019-y-siguientes",
            values=(
                SyntheticInputValue(
                    id="casilla-01",
                    value=Decimal("10000"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A1"),
                    registry_binding="01",
                ),
                SyntheticInputValue(
                    id="casilla-02",
                    value=Decimal("4000"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A2"),
                    registry_binding="02",
                ),
                SyntheticInputValue(
                    id="casilla-05",
                    value=Decimal("250"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A3"),
                    registry_binding="05",
                ),
                SyntheticInputValue(
                    id="casilla-06",
                    value=Decimal("100"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A4"),
                    registry_binding="06",
                ),
                SyntheticInputValue(
                    id="casilla-08",
                    value=Decimal("2000"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A5"),
                    registry_binding="08",
                ),
                SyntheticInputValue(
                    id="casilla-10",
                    value=Decimal("10"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A6"),
                    registry_binding="10",
                ),
                SyntheticInputValue(
                    id="casilla-13",
                    value=Decimal("0"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A7"),
                ),
                SyntheticInputValue(
                    id="previous-year-net-income",
                    value=Decimal("13000"),
                    registry_binding="irpf.previous_year_economic_activity_net_income",
                ),
                SyntheticInputValue(
                    id="casilla-15",
                    value=Decimal("0"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A8"),
                    registry_binding="15",
                ),
                SyntheticInputValue(
                    id="casilla-16",
                    value=Decimal("0"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A9"),
                    registry_binding="16",
                ),
                SyntheticInputValue(
                    id="casilla-18",
                    value=Decimal("0"),
                    workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A10"),
                    registry_binding="18",
                ),
            ),
        ),
        output_cells={"casilla-19": WorkbookCellRef(sheet="Modelo", coordinate="B1")},
        registry_outputs={"casilla-19": "19"},
        date_context={"filing_period": date(2026, 3, 31)},
    )

    save_parity_scenario(scenario, scenario_path)
    loaded_scenario = load_parity_scenario(scenario_path)
    assert loaded_scenario == scenario

    tape = run_parity_scenario(
        loaded_scenario,
        registry_root=PROJECT_ROOT / "registry" / "aeat",
        source_root=PROJECT_ROOT,
        scenario_path=scenario_path,
    )

    assert tape.scenario_path == scenario_path.resolve().as_posix()
    assert tape.report.status == "match"
    assert tape.report.comparisons[0].expected_workbook_value == 880
    assert tape.report.comparisons[0].actual_registry_value == Decimal("880.00")
    assert tape.workbook.path == "data/modelo_130/files/130-parity.xlsx"

    saved_tape_path = save_parity_tape(tape, tape_path)
    assert saved_tape_path == tape_path
    loaded_tape = load_parity_tape(tape_path)
    assert loaded_tape.scenario == tape.scenario

    replay = replay_parity_tape(
        loaded_tape,
        registry_root=PROJECT_ROOT / "registry" / "aeat",
        source_root=PROJECT_ROOT,
        tape_path=tape_path,
    )

    assert replay.status == "match"
    assert replay.differences == ()
    assert replay.current.report.status == "match"
    assert replay.current.report.comparisons[0].expected_workbook_value == 880
    assert replay.current.report.comparisons[0].actual_registry_value == Decimal("880.00")


def test_generate_parity_tape_path_uses_slugged_scenario_id() -> None:
    created_at = datetime(2026, 5, 5, 0, 0, tzinfo=UTC)
    path = generate_parity_tape_path(Path("var/aeat/parity"), "Modelo 130 Manual", created_at)

    assert path.as_posix().endswith("modelo-130-manual/20260505T000000Z.json")
