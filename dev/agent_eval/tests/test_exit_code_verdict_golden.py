"""Real negative-recovery-retry coverage for the operator eval runner.

The runner must not treat a non-zero exit as a dead-end string-matching exercise.
These tests dispatch live CLI leaves, build the same application-owned typed
precondition facts, and let the runner resolve, safely execute, and retry through
the live operator surface.  No test owns an expected action or a recovery command.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.application.modelo import build_modelo_precondition_failure
from cadrumo.application.operator_actions import no_action_precondition_verdict
from cadrumo.core import ActionEvidenceProvenance, resolve_active_bucket_id
from cadrumo.core.json_contract import EnvelopeStatus
from cadrumo.domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from cadrumo.domain.user_profile import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.profile_capsule import open_test_profile_session, seed_test_profile_record
from cadrumo.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

from .. import ExitCodeScenario, check_exit_code_scenario
from .._action_coverage import LeafConditionScenario, production_leaf_condition_scenario_matrix

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FILING_YEAR = 2025
_PERIOD = "1T"
_PROFILE_ID = "0ac1e000-0000-4000-8000-000000000344"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> TestRuntimeProfile:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Exit-code golden-eval test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    schema = load_user_profile_schema()
    seed_test_profile_record(
        UserProfileRecord(
            schema_id=schema.id,
            schema_version=schema.version,
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value="Exit Code Operator"),
                UserProfileFact(path="identity.surnames", value="Golden Eval"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
        ),
        root=runtime_profile.storage_root,
        label="Exit-code golden-eval test profile",
    )


def _recovery_coverage() -> LeafConditionScenario:
    return production_leaf_condition_scenario_matrix().row_for(
        (
            "modelo.work.verify",
            "modelo.work.verify.calculation_revision.addresses_calculation",
            "modelo.work.verify.calculation_revision.work_unit_target",
        ),
    )


def _no_recovery_coverage() -> LeafConditionScenario:
    return production_leaf_condition_scenario_matrix().row_for(
        (
            "modelo.work.verify",
            "modelo.work.verify.cross_period_dependency.clean",
            "modelo.work.verify.cross_period_dependency.unclean",
        ),
    )


def _dispatch_unprepared_m347_verify(runtime_profile: TestRuntimeProfile) -> tuple[int, dict[str, Any], str]:
    """Create a real draft, then ask the live verify leaf to address no calculation.

    This is the safe recovery chain: the declared recovery action calculates the
    exact work unit, and the runner retries the original verify leaf afterwards.
    """
    _seed_natural_person_profile(runtime_profile)
    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "347", "--year", "2024", "--period", "0A",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = str(require_schema_envelope(created.output)["work_unit_id"])

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", work_unit_id],
    )
    return verified.exit_code, json.loads(verified.output), work_unit_id


def _recovery_precondition(*, coverage: LeafConditionScenario, work_unit_id: str):
    action = coverage.profile.declaration.action
    assert action is not None
    return build_modelo_precondition_failure(
        subject_leaf_key=coverage.subject_leaf_key,
        condition_id=coverage.condition_id,
        scenario_id=coverage.scenario_id,
        evidence_id="workflow.work_unit.addressing",
        evidence_values={
            "work_unit_id": work_unit_id,
            "modelo": "347",
            "year": 2024,
            "period": "0A",
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_id=action.action_id,
        action_argument_values={"work_unit_id": work_unit_id},
    ).verdict


def _seed_m130_income_transaction(*, amount: Decimal, filing_year: int) -> None:
    """Seed one real actividad-economica income row for source-bound M130 casilla 01."""
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    value_date = date(filing_year, 2, 15)
    income = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"exit-code-golden-income-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description="exit-code golden eval income",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="f" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "m130_exit_code_golden_income", "source_key": "exit-code-golden"},
            ),
            "direction": TransactionDirection.INCOMING,
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
        transactions = (*tuple(existing.transactions.values()), income)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


def _dispatch_m130_verify_with_cross_period_finding(runtime_profile: TestRuntimeProfile) -> tuple[int, dict[str, Any]]:
    """Dispatch a real M130 verify that reaches an explicit operator-decision outcome."""
    _seed_natural_person_profile(runtime_profile)
    _seed_m130_income_transaction(amount=Decimal("12000.00"), filing_year=_FILING_YEAR)
    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    calculated = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output
    verified = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    payload = require_schema_envelope(verified.output)
    assert payload["granted_verificado_completo"] is False, verified.output
    assert payload["findings"][0]["kind"] == "cross_period_dependency_unclean", verified.output
    return verified.exit_code, json.loads(verified.output)


def test_runner_executes_only_the_safe_canonical_recovery_then_retries_the_original_leaf(
    runtime_profile: TestRuntimeProfile,
) -> None:
    coverage = _recovery_coverage()
    exit_code, envelope, work_unit_id = _dispatch_unprepared_m347_verify(runtime_profile)
    assert exit_code == 1, envelope
    scenario = ExitCodeScenario(
        name="m347-verify-without-calculation",
        command=coverage.subject_leaf_key,
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.ERROR,
        leaf_condition_scenario=coverage.identity,
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        precondition_verdict=_recovery_precondition(coverage=coverage, work_unit_id=work_unit_id),
        original_argv=("app", "modelo", "work", "verify", work_unit_id),
    )

    assert result.passed, result.failures
    assert result.production_action_assertion.passed


def test_runner_leaves_explicit_operator_decision_outcome_unexecuted(runtime_profile: TestRuntimeProfile) -> None:
    coverage = _no_recovery_coverage()
    outcome = coverage.profile.declaration.no_recovery_outcome
    assert outcome is not None
    exit_code, envelope = _dispatch_m130_verify_with_cross_period_finding(runtime_profile)
    assert exit_code == 1, envelope
    scenario = ExitCodeScenario(
        name="m130-verify-cross-period-unclean",
        command=coverage.subject_leaf_key,
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.WARNING,
        leaf_condition_scenario=coverage.identity,
    )
    refusal = no_action_precondition_verdict(
        condition_id=coverage.condition_id,
        evidence_id="modelo.work.verify.cross_period_dependency",
        facts={"modelo": "130", "year": _FILING_YEAR, "period": _PERIOD},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=outcome,
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        precondition_verdict=refusal,
    )

    assert result.passed, result.failures
    assert result.production_action_assertion.observed_no_recovery_outcome is outcome


def test_runner_rejects_a_retry_that_does_not_name_the_resolved_subject_leaf(
    runtime_profile: TestRuntimeProfile,
) -> None:
    coverage = _recovery_coverage()
    exit_code, envelope, work_unit_id = _dispatch_unprepared_m347_verify(runtime_profile)
    scenario = ExitCodeScenario(
        name="m347-verify-retry-must-stay-on-subject",
        command=coverage.subject_leaf_key,
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.ERROR,
        leaf_condition_scenario=coverage.identity,
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        precondition_verdict=_recovery_precondition(coverage=coverage, work_unit_id=work_unit_id),
        original_argv=("app", "modelo", "work", "calculate", work_unit_id),
    )

    assert not result.passed
    assert any("does not invoke its canonical subject leaf" in failure for failure in result.failures)
