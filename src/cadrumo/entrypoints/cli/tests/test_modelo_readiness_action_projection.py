"""The modelo-readiness triple carries typed action axes beside native facts."""

from __future__ import annotations

import pytest

from cadrumo.application.ledger import LedgerPreflightIssue, LedgerPreflightIssueReason
from cadrumo.application.state_projection import (
    MODELO_READINESS_MISSING_PROFILE_ACTION,
    OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE,
    OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE,
    ProjectionModeloBindingRequirement,
    ProjectionModeloReadiness,
)
from cadrumo.application.user_profile import ProfilePreflightRequirement
from cadrumo.core import BindingSourceKind, OperatorActionAxis, Period

from .._modelo_readiness_cli import _readiness_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_readiness_action_projections_are_total_over_their_native_codes() -> None:
    assert MODELO_READINESS_MISSING_PROFILE_ACTION is OperatorActionAxis.SET_PROFILE_FACT
    assert set(OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE) == set(BindingSourceKind)
    assert set(OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE) == set(LedgerPreflightIssueReason)
    assert set(OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE.values()) <= set(OperatorActionAxis)
    assert set(OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE.values()) <= set(OperatorActionAxis)


@pytest.mark.parametrize(
    ("source", "expected_action"),
    (
        (BindingSourceKind.RETENCIONES_AGGREGATION, OperatorActionAxis.SUPPLY_MANUAL_INPUT),
        (BindingSourceKind.WITHHOLDING, OperatorActionAxis.SUPPLY_MANUAL_INPUT),
        (BindingSourceKind.FOREIGN_ASSET, OperatorActionAxis.SUPPLY_MANUAL_INPUT),
        (BindingSourceKind.ATRIBUCION_MEMBER, OperatorActionAxis.SET_PROFILE_FACT),
        (BindingSourceKind.RELATED_PARTY_OPERATION, OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE),
        (BindingSourceKind.REFUND_OPERATION, OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE),
    ),
)
def test_non_ledger_binding_sources_project_their_actual_operator_workflow(
    source: BindingSourceKind,
    expected_action: OperatorActionAxis,
) -> None:
    assert OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE[source] is expected_action


def test_readiness_payload_projects_actions_without_dropping_native_facts() -> None:
    period = Period.from_year_and_code(2026, "1T")
    report = ProjectionModeloReadiness(
        profile_id="11111111-1111-4111-8111-111111111111",
        modelo="303",
        revision_id="2026-y-siguientes",
        filing_year=2026,
        period=period,
        missing=(
            ProfilePreflightRequirement(
                selector="tax_residence.jurisdiction_scope",
                section_key="tax_residence",
                field_key="jurisdiction_scope",
                label="Jurisdiction scope",
            ),
        ),
        profile_ready=False,
        per_operation_requirements_assessed=True,
        missing_bindings=(
            ProjectionModeloBindingRequirement(
                binding_id="m303-prior-period-result",
                source=BindingSourceKind.PREVIOUS_FILING,
                input_channel="decimal",
            ),
        ),
        binding_ready=False,
        ledger_preflight_required=True,
        ledger_ready=False,
        ledger_period=period,
        ledger_checked_transaction_count=1,
        ledger_issues=(
            LedgerPreflightIssue(
                transaction_id="tx-1",
                reason=LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
                detail="counterparty identification state is required",
            ),
        ),
        ready=False,
    )

    payload = _readiness_result(
        report,
        modelo="303",
        revision_id="2026-y-siguientes",
        filing_year=2026,
    )

    assert payload.missing[0].selector == "tax_residence.jurisdiction_scope"
    assert payload.missing[0].operator_action is OperatorActionAxis.SET_PROFILE_FACT
    assert payload.missing_bindings[0].source is BindingSourceKind.PREVIOUS_FILING
    assert payload.missing_bindings[0].operator_action is OperatorActionAxis.FILE_PRIOR_PERIOD
    assert payload.ledger_issues[0].reason == LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE.value
    assert payload.ledger_issues[0].operator_action is OperatorActionAxis.RESOLVE_IDENTITY
