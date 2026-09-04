"""Response-layer provenance gate for the operator golden-task eval.

Guards against provenance dropped at the RESPONSE layer: the runner's existing
provenance dimension (``_check_provenance``) inspects the REGISTRY snapshot, which
proves the registry itself is grounded but NOT that the CLI/MCP
``modelo.work.calculate`` RESPONSE payload actually relayed that grounding — the
real repro is a real M130 calculate that returned correct casilla values but no
``legal_refs``/``formula_id`` at the CLI layer.

This module dispatches a REAL ``modelo.work.calculate`` through the actual CLI
command handling (the identical transport
:func:`cadrumo_harness.mcp._dispatch.tool_request_argv` projects the
``cadrumo_modelo_work_calculate`` MCP tool call onto: ``app modelo work calculate``),
decodes the JSON RESPONSE payload's ``observations`` rows, and feeds them into
:func:`dev.agent_eval._runner.run_golden_scenario` via its ``response_observations``
parameter so the ``response_provenance_present`` dimension asserts over the
payload the operator actually reads.

No mocks: every seeded row is a genuine ``TransactionCatalogueRepository`` write
and every response value is what the real registry engine plus the real CLI
envelope serializer produced.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.loader import load_user_profile_schema
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.profile_capsule import open_test_profile_session, seed_test_profile_record
from cadrumo.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

from .._models import GoldenScenario
from .._runner import load_scenario, run_golden_scenario
from ._real_cli_support import create_m130_work_unit, valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000000099"
_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_SCENARIO_PATH = _SCENARIOS_DIR / "modelo_130.toml"
_REVISION = "2019-y-siguientes"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Real-session backend (real KEK/DEK, real SQLite per active bucket)."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Response-provenance golden-eval test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a natural-person (IRPF estimacion directa) profile into the active bucket.

    Written directly (mirrors the pattern in
    ``entrypoints.cli.tests.test_modelo_calculation_through_real_cli``) to bypass
    ``config profile create``, which would re-provision the already-present
    bucket manifest.
    """
    # Both identity fields come from the loaded schema rather than from
    # literals. The record pins each to exactly what the schema declares, so a
    # literal is a copy of the authority that goes stale the moment the schema
    # moves -- and reading them from one loaded object also keeps the pair
    # self-consistent, since two literals can drift into naming different
    # schemas.
    schema = load_user_profile_schema()
    record = UserProfileRecord(
        schema_id=schema.id,
        schema_version=schema.version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Response Provenance Operator"),
            UserProfileFact(path="identity.surnames", value="Golden Eval"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(
        record,
        root=runtime_profile.storage_root,
        label="Response-provenance golden-eval test profile",
    )


def _seed_ledger_row(*, direction: TransactionDirection, amount: Decimal, filing_year: int, label: str) -> None:
    """Seed one real actividad-economica ledger row for a source-bound M130 casilla.

    Deliberately local to this module rather than importing
    ``entrypoints.cli.tests._m130_source_support`` (a private helper module scoped
    to the ``entrypoints.cli.tests`` package) across a package boundary. Writes a
    genuine row through the real ``TransactionCatalogueRepository``.
    """
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    value_date = date(filing_year, 2, 15)
    row = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"response-provenance-{label}-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Contraparte SA",
                description=f"response-provenance golden eval {label}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256=("d" if direction == TransactionDirection.INCOMING else "e") * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": f"m130_response_provenance_{label}", "source_key": label},
            ),
            "direction": direction,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "purchase_invoice_evidence_id": None,
            "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    with open_test_profile_session(bucket_id):
        existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        transactions = (*tuple(existing.transactions.values()), row)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


def _dispatch_real_m130_calculate(
    runtime_profile: TestRuntimeProfile,
    *,
    filing_year: int,
    period: str,
) -> tuple[Mapping[str, Any], ...]:
    """Dispatch a REAL ``modelo.work.calculate`` and return the response ``observations`` rows.

    Drives real command handling end to end (create work unit -> seed real
    ledger rows -> calculate) — the same transport the ``cadrumo_modelo_work_calculate``
    MCP tool dispatches to, since
    :func:`cadrumo_harness.mcp._dispatch.tool_request_argv` projects that tool
    call onto the identical ``app modelo work calculate`` CLI argv this test
    invokes directly. Every returned value is what the real registry engine and
    the real CLI envelope serializer produced — not a hand-rolled dict.
    """
    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_m130_work_unit(filing_year=filing_year, period=period, revision=_REVISION)
    _seed_ledger_row(
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12000.00"),
        filing_year=filing_year,
        label="ingresos",
    )
    _seed_ledger_row(
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("4000.00"),
        filing_year=filing_year,
        label="gastos",
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
