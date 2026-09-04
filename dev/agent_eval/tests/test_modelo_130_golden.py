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

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.authority import bundled_authority

from .._runner import load_scenario, run_golden_scenario
from ._real_cli_support import valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_SCENARIO = _SCENARIOS_DIR / "modelo_130.toml"
_ALL_SCENARIOS = scan_directory(_SCENARIOS_DIR, pattern="*.toml")


@pytest.mark.parametrize("scenario_path", _ALL_SCENARIOS, ids=lambda p: p.stem)
def test_every_golden_scenario_passes_all_dimensions(scenario_path: Path) -> None:
    # Covers the full lifecycle for every shipped scenario (modelo 130 and 303);
    # adding a scenario TOML auto-extends this gate.
    result = run_golden_scenario(load_scenario(scenario_path), valid_commands=valid_cli_commands())
    assert result.passed, f"{scenario_path.stem} failures: {result.failures}"
    assert result.trajectory_resolves
    assert result.lifecycle_ordered
    assert result.skill_consistent
    assert result.provenance_present
    # No live dispatch is wired for this cross-scenario sweep, so the
    # response-provenance dimension holds trivially; the real dispatch + its
    # anti-tautology proof live in test_response_provenance_golden.py.
    assert result.response_provenance_present
    assert result.verification_grounded


def test_at_least_the_130_and_303_scenarios_are_shipped() -> None:
    stems = {path.stem for path in _ALL_SCENARIOS}
    assert {"modelo_130", "modelo_303"} <= stems


def test_provenance_dimension_is_not_vacuous() -> None:
    # Prove the provenance dimension actually inspects real registry grounding:
    # the modelo-130 revision must carry casillas with legal_refs/source_refs, so a
    # pass is grounded, not an empty-set tautology.

    scenario = load_scenario(_SCENARIO)
    snapshot = bundled_authority().snapshot(scenario.modelo, filing_year=scenario.filing_year, period=scenario.period)
    casillas = snapshot.revision.casillas
    rows = list(casillas.values()) if isinstance(casillas, dict) else list(casillas)
    assert rows, "modelo-130 revision has no casillas to ground"
    assert all(c.legal_refs and c.source_refs for c in rows)


def test_runner_rejects_a_fabricated_verb() -> None:
    scenario = load_scenario(_SCENARIO).model_copy(
        update={"expected_trajectory": ("modelo.work.create", "modelo.work.fabricated")}
    )
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert not result.passed
    assert not result.trajectory_resolves


def test_runner_rejects_out_of_order_lifecycle() -> None:
    scenario = load_scenario(_SCENARIO).model_copy(
        update={"expected_trajectory": ("modelo.work.verify", "modelo.work.calculate")}
    )
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert not result.passed
    assert not result.lifecycle_ordered


def test_runner_rejects_a_duplicate_declared_lifecycle_stage() -> None:
    scenario = load_scenario(_SCENARIO).model_copy(
        update={
            "expected_trajectory": (
                "modelo.work.create",
                "modelo.work.calculate",
                "modelo.work.calculate",
                "modelo.work.verify",
                "modelo.export",
            ),
        },
    )
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())

    assert not result.passed
    assert not result.lifecycle_ordered
    assert "trajectory declares lifecycle stage(s) more than once: modelo.work.calculate" in result.failures


def test_runner_accepts_one_declaration_per_lifecycle_stage() -> None:
    result = run_golden_scenario(load_scenario(_SCENARIO), valid_commands=valid_cli_commands())

    assert result.passed, result.failures
    assert result.lifecycle_ordered


def test_verification_dimension_is_grounded_and_not_vacuous() -> None:
    # The modelo-130 revision must declare an AEAT-grounded verification contract
    # (computed_casilla_ids with source_refs), so a pass is grounded.

    scenario = load_scenario(_SCENARIO)
    revision = (
        bundled_authority().snapshot(scenario.modelo, filing_year=scenario.filing_year, period=scenario.period).revision
    )
    expectations = list(revision.verification_expectations)
    assert expectations, "modelo-130 revision declares no verification contract"
    computed = {c for e in expectations for c in e.computed_casilla_ids}
    assert {"03", "04", "07"} <= computed
    assert all(e.source_refs for e in expectations if e.computed_casilla_ids)


def test_runner_rejects_an_ungrounded_expected_computed_casilla() -> None:
    # Anti-tautology: a casilla id that is NOT in the registry's AEAT-grounded
    # computed set must fail the verification dimension.
    scenario = load_scenario(_SCENARIO).model_copy(update={"expected_computed_casillas": ("9999",)})
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert not result.passed
    assert not result.verification_grounded
