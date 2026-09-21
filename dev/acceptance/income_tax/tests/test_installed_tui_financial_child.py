"""Focused contract checks for the installed financial child."""
from __future__ import annotations

from pathlib import Path

import pytest

from ..installed_tui_financial_child import _N26_HEADER, _transaction_csv, required_profile_facts
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
    assert all((fact.value is None) != (fact.option_index is None) for fact in facts)


def test_transaction_csv_is_n26_compatible_transient_scenario_input(tmp_path: Path) -> None:
    path = _transaction_csv(scenario=build_scenario(2025), directory=tmp_path)
    assert path.parent == tmp_path
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == _N26_HEADER
    assert len(lines) == 9
    assert all(line.endswith(",EUR," + line.rsplit(",", 1)[-1]) for line in lines[1:])
