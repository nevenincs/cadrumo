"""Response-layer provenance gate for the operator golden-task eval.

Guards against provenance dropped at the RESPONSE layer: the runner's existing
provenance dimension (``_check_provenance``) inspects the REGISTRY snapshot, which
proves the registry itself is grounded but NOT that the CLI
``modelo.work.calculate`` RESPONSE payload actually relayed that grounding — the
real repro is a real M130 calculate that returned correct casilla values but no
``legal_refs``/``formula_id`` at the CLI layer.

This module dispatches a REAL ``modelo.work.calculate`` through the actual CLI
command handling, decodes the JSON RESPONSE payload's ``observations`` rows, and
feeds them into :func:`dev.mcp_eval.runner.run_golden_scenario` via its
``response_observations`` parameter so the ``response_provenance_present``
dimension asserts over the payload the operator actually reads.

No mocks: every seeded row is a genuine ``TransactionCatalogueRepository`` write
and every response value is what the real registry engine plus the real CLI
envelope serializer produced.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.m130_source_support import (
    seed_m130_expense_transaction,
    seed_m130_income_transaction,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_covering
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import CliWorldProvider, bind_cli_fixture_ports
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_fixture_ports import CliInvocation
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import (
    bind_public_cli_runner,
    invoke_cached_cli,
)
from cadrumo_runtime.host.tests.frontend.cli.runtime_profile_backend import runtime_cli_profile

from ..models import GoldenScenario
from ..runner import load_scenario, run_golden_scenario
from .real_cli_support import create_m130_work_unit, seed_natural_person_profile, valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_SCENARIO_PATH = _SCENARIOS_DIR / "modelo_130.toml"


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
    run_cadrumo_cli: Callable[..., Result],
    cli_world_provider: CliWorldProvider,
    invoke_cli: CliInvocation,
) -> Iterator[TestRuntimeProfile]:
    """Real-session backend (real KEK/DEK, real SQLite per active bucket).

    The product's own CLI helpers reach the operator through the injected
    fixture ports, so this fixture binds them as the owning package's conftest
    does; without them the work-unit helper has no invocation.
    """
    with (
        bind_public_cli_runner(run_cadrumo_cli),
        bind_cli_fixture_ports(cli_world_provider, invoke_cli),
        runtime_cli_profile(
            tmp_path=tmp_path,
            label="Response-provenance golden-eval test profile",
        ) as profile,
    ):
        yield profile


def _dispatch_real_m130_calculate(
    runtime_profile: TestRuntimeProfile,
    *,
    filing_year: int,
    period: str,
) -> tuple[Mapping[str, Any], ...]:
    """Dispatch a REAL ``modelo.work.calculate`` and return the response ``observations`` rows.

    Drives real command handling end to end (create work unit -> seed real
    ledger rows -> calculate). Every returned value is what the real registry
    engine and the real CLI envelope serializer produced — not a hand-rolled dict.
    """
    seed_natural_person_profile(
        runtime_profile, name="Response Provenance Operator", label="Response-provenance golden-eval test profile"
    )
    seed_m130_income_transaction(amount=Decimal("12000.00"), filing_year=filing_year, source_key="ingresos")
    seed_m130_expense_transaction(amount=Decimal("4000.00"), filing_year=filing_year, source_key="gastos")

    work_unit_id = create_m130_work_unit(
        filing_year=filing_year, period=period, revision=revision_covering("130", filing_year).id
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = require_schema_envelope(result.output)
    observations = payload["observations"]
    assert observations, "real M130 calculate response carried zero observations"
    return tuple(observations)


def _expected_computed_observations(
    scenario: GoldenScenario,
    observations: tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    expected = set(scenario.expected_computed_casillas)
    computed = tuple(obs for obs in observations if str(obs["casilla_id"]) in expected)
    assert {str(obs["casilla_id"]) for obs in computed} == expected
    return computed


def test_m130_calculate_response_payload_carries_provenance(runtime_profile: TestRuntimeProfile) -> None:
    """A real dispatched M130 calculate RESPONSE payload is provenance-complete.

    Dispatches the real CLI ``modelo work calculate`` command (not the registry
    snapshot alone) and asserts the ``response_provenance_present`` dimension
    holds against the decoded JSON ``observations`` the operator actually reads.
    """
    scenario = load_scenario(_SCENARIO_PATH)
    observations = _dispatch_real_m130_calculate(
        runtime_profile,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )

    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        response_observations=observations,
    )

    assert result.response_provenance_present, result.failures
    assert all(obs["legal_refs"] and obs["source_refs"] for obs in observations)
    assert all(obs["formula_id"] for obs in _expected_computed_observations(scenario, observations))


def test_runner_rejects_a_response_with_provenance_stripped(runtime_profile: TestRuntimeProfile) -> None:
    """Anti-tautology: a response with legal_refs/source_refs stripped MUST fail.

    Takes the SAME real dispatched response and strips provenance from every
    observation — reproducing the exact historical regression this dimension
    closes (a real M130 calculate that returned correct values but no
    legal_refs/formula_id at the CLI layer) — and proves
    ``response_provenance_present`` catches it. Without this proof the dimension
    could pass vacuously regardless of what the CLI actually emitted.
    """
    scenario = load_scenario(_SCENARIO_PATH)
    observations = _dispatch_real_m130_calculate(
        runtime_profile,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )
    stripped = tuple({**dict(obs), "legal_refs": [], "source_refs": []} for obs in observations)

    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        response_observations=stripped,
    )

    assert not result.passed
    assert not result.response_provenance_present
    assert any("lack legal_refs/source_refs" in failure for failure in result.failures)


def test_runner_rejects_expected_computed_response_rows_without_formula_id(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology: expected computed response rows without formula_id MUST fail."""
    scenario = load_scenario(_SCENARIO_PATH)
    observations = _dispatch_real_m130_calculate(
        runtime_profile,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )
    expected = set(scenario.expected_computed_casillas)
    stripped = tuple(
        {**dict(obs), "formula_id": None} if str(obs["casilla_id"]) in expected else dict(obs) for obs in observations
    )

    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        response_observations=stripped,
    )

    assert not result.passed
    assert not result.response_provenance_present
    assert any("formula provenance" in failure and "formula_id" in failure for failure in result.failures)


def test_runner_allows_formula_id_absent_outside_expected_computed_rows(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Negative control: input/manual response rows do not need formula_id."""
    scenario = load_scenario(_SCENARIO_PATH)
    observations = _dispatch_real_m130_calculate(
        runtime_profile,
        filing_year=scenario.filing_year,
        period=scenario.period,
    )
    expected = set(scenario.expected_computed_casillas)
    outside_expected = tuple(obs for obs in observations if str(obs["casilla_id"]) not in expected)
    assert outside_expected, "real M130 response must include input/manual rows outside the computed contract"
    stripped = tuple(
        {**dict(obs), "formula_id": None} if str(obs["casilla_id"]) not in expected else dict(obs)
        for obs in observations
    )

    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        response_observations=stripped,
    )

    assert result.response_provenance_present, result.failures


def test_response_provenance_dimension_holds_trivially_when_not_dispatched() -> None:
    """No live dispatch supplied -> the dimension holds trivially, no other check regresses.

    ``run_golden_scenario`` never dispatches the calculate call itself (mirrors
    the ``valid_commands`` injection pattern); this proves the new parameter's
    default does not silently fail every existing scenario run.
    """
    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert result.response_provenance_present
