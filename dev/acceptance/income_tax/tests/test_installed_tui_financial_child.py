"""Focused contract checks for the installed financial child."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ..installed_tui_financial_child import (
    _N26_HEADER,
    _open_destination,
    _transaction_csv,
    _validate_annual_artifact,
    required_profile_facts,
)
from ..scenario import build_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_profile_configuration_uses_canonical_manager_row_paths() -> None:
    facts = required_profile_facts(build_scenario(2025))
    paths = {fact.path for fact in facts}
    assert "identity.tax_id" in paths
    assert "activities.description" not in paths
    assert "taxpayer_type.irpf_income_categories" in paths
    assert "irpf.estimation_regime" in paths
    assert "renta_taxpayer.birth_date" in paths
    assert "withholding.has_employees" in paths
    assert "obligations.monedas_virtuales_extranjero_above_threshold" in paths
    assert "obligations.premio_loteria_gravamen_especial_sin_retencion" in paths
    assert all((fact.value is None) != (fact.option_index is None) for fact in facts)


def test_transaction_csv_is_n26_compatible_transient_scenario_input(tmp_path: Path) -> None:
    path = _transaction_csv(scenario=build_scenario(2025), directory=tmp_path)
    assert path.parent == tmp_path
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == _N26_HEADER
    assert len(lines) == 9
    assert all(line.endswith(",EUR," + line.rsplit(",", 1)[-1]) for line in lines[1:])


def test_annual_artifact_parser_checks_financial_meaning_and_official_schema() -> None:
    root = Path(__file__).resolve().parents[4]
    xml = Path(__file__).resolve().parent / "fixtures" / "modelo-100-2025-0A-synthetic.xml"
    schema = root / (
        "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/"
        "03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd"
    )
    values, validation = _validate_annual_artifact(xml_path=xml, xsd_path=schema, scenario=build_scenario(2025))
    assert values == {"E1INGRESO": "12000.00", "E1NGD": "2400.00", "E1RN": "9600.00", "PAGOS": "680.00"}
    assert validation["xsd_valid"] is True
    assert validation["normalization_count"] == 16
    assert validation["original_schema_sha256"] == ("df94cc5160e8ad8244e6fc5fb0f257280b4c8c3f70107f0c2acc99d395f678c2")


@pytest.mark.asyncio
async def test_palette_selects_the_exact_destination_after_fuzzy_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.i18n.render import tr

    destination = tr("tui.search.destination.declarations")
    options = [
        SimpleNamespace(hit=SimpleNamespace(text="A recent declaration result")),
        SimpleNamespace(hit=SimpleNamespace(text=destination)),
    ]
    listing = SimpleNamespace(
        option_count=len(options), highlighted=None, get_option_at_index=lambda index: options[index]
    )
    search = SimpleNamespace(value="")
    screen = SimpleNamespace(query_one=lambda selector: search if selector.__name__ == "Input" else listing)
    pressed: list[str] = []

    class PilotStub:
        app = SimpleNamespace(screen=screen)

        async def press(self, key: str) -> None:
            pressed.append(key)

        async def pause(self) -> None:
            return

    async def available(_pilot: Any, _selector: str, *, polls: int) -> None:
        assert polls == 180

    monkeypatch.setattr("dev.acceptance.income_tax.installed_tui_financial_child.wait_for_public_selector", available)
    await _open_destination(PilotStub(), query="declarations", expected_selector="#declarations-list")
    assert listing.highlighted == 1
    assert pressed == ["ctrl+p", "enter"]
