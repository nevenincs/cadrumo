"""Golden-task eval gate for the modelo-130 preparation workflow.

Asserts the shipped scenario passes every dimension - its tool trajectory resolves
against the live CLI surface, follows the modelo lifecycle order, is consistent
with the shipped skill playbook, and the resolved revision's casillas carry their
registry legal grounding - and includes an anti-tautology proof that the runner
rejects a broken scenario (a fabricated verb and an out-of-order lifecycle), so a
green pass means the assertions actually have teeth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import load_scenario, run_golden_scenario

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "modelo_130.toml"


def _valid_commands() -> frozenset[str]:
    from ....entrypoints.cli._app_contract import _command_schema_refs

    return frozenset(ref.command for ref in _command_schema_refs())


def test_modelo_130_scenario_passes_every_dimension() -> None:
    result = run_golden_scenario(load_scenario(_SCENARIO), valid_commands=_valid_commands())
    assert result.passed, f"failures: {result.failures}"
    assert result.trajectory_resolves
    assert result.lifecycle_ordered
    assert result.skill_consistent
    assert result.provenance_present


def test_provenance_dimension_is_not_vacuous() -> None:
    # Prove the provenance dimension actually inspects real registry grounding:
    # the modelo-130 revision must carry casillas with legal_refs/source_refs, so a
    # pass is grounded, not an empty-set tautology.
    from ....core.resources import resources

    scenario = load_scenario(_SCENARIO)
    snapshot = resources().modelos.authority.snapshot(
        scenario.modelo, filing_year=scenario.filing_year, period=scenario.period
    )
    casillas = snapshot.revision.casillas
    rows = list(casillas.values()) if isinstance(casillas, dict) else list(casillas)
    assert rows, "modelo-130 revision has no casillas to ground"
    assert all(c.legal_refs and c.source_refs for c in rows)


def test_runner_rejects_a_fabricated_verb() -> None:
    scenario = load_scenario(_SCENARIO).model_copy(
        update={"expected_trajectory": ("modelo.work.create", "modelo.work.fabricated")}
    )
    result = run_golden_scenario(scenario, valid_commands=_valid_commands())
    assert not result.passed
    assert not result.trajectory_resolves


def test_runner_rejects_out_of_order_lifecycle() -> None:
    scenario = load_scenario(_SCENARIO).model_copy(
        update={"expected_trajectory": ("modelo.work.verify", "modelo.work.calculate")}
    )
    result = run_golden_scenario(scenario, valid_commands=_valid_commands())
    assert not result.passed
    assert not result.lifecycle_ordered
