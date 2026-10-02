"""Native API scopes for the overview pipeline keep its global ledger facts visible."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ....application.ledger.actions_manual import create_manual_transaction
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.overview.pipeline_operation import OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import TransactionDirection
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...ledger_action_composition import compose_ledger_action_ports
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_TARGET = Period.from_year_and_code(2025, "1T")
_OUTSIDE = Period.from_year_and_code(2025, "2T")


def _scope(
    client_id: UUID,
    *,
    periods: frozenset[Period] | None,
    result: bool = True,
) -> AccessScope:
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if result:
        actions.add(AccessAction.RESULT)
    return AccessScope(
        operations=frozenset({OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID}),
        actions=frozenset(actions),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=periods,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _seed_profile(
    profile_id: UUID,
    _root: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    """Create one real ledger row in each quarter through the canonical action."""
    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    transaction_ids: list[str] = []
    for label, period, booked_date, amount in (
        ("selected", _TARGET, date(2025, 2, 15), Decimal("121.00")),
        ("outside", _OUTSIDE, date(2025, 5, 15), Decimal("60.50")),
    ):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=booked_date,
                amount=amount,
                direction=TransactionDirection.OUTGOING,
                description=f"Overview pipeline {label} period seed",
                actor="native-overview-pipeline",
                idempotency_key=f"native-overview-pipeline-{period.registry_token}",
            ),
            ports=ports,
            occurred_at=datetime.combine(booked_date, datetime.min.time(), tzinfo=UTC),
        )
        transaction_ids.append(created.transaction.transaction_id)
    return tuple(transaction_ids)


def _prepare(operation: PinnedAuthorityOperation):
    def prepare(profile_id: UUID, root: Path) -> tuple[str, ...]:
        return _seed_profile(profile_id, root, operation=operation)

    return prepare


def _pipeline(session: NativeApiCliSession[tuple[str, ...]]):
    return session.invoke_credential_reference(
        "app",
        "overview",
        "pipeline",
        "--year",
        str(_TARGET.filing_year),
        "--period",
        _TARGET.registry_token,
    )


def _assert_password_status_matches_pipeline(
    session: NativeApiCliSession[tuple[str, ...]], pipeline: dict[str, object]
) -> None:
    """Use the separate human status reader as a canonical encrypted ledger oracle."""
    status = session.invoke_password(
        "app",
        "ledger",
        "status",
        "--year",
        str(_TARGET.filing_year),
        "--period",
        _TARGET.registry_token,
    )
    assert status.exit_code == 0, status.output
    canonical = unwrap_cli_result(status)
    pipeline_ledger = cast("dict[str, object]", pipeline["ledger"])
    for field in (
        "period",
        "total_count",
        "active_count",
        "pending_review_count",
        "reviewed_count",
        "skipped_count",
        "business_income_total",
        "business_expense_total",
        "business_net_total",
    ):
        assert pipeline_ledger[field] == canonical[field]


def test_native_pipeline_requires_whole_profile_scope_and_keeps_result_receipt(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A selected quarter does not narrow the global ledger counters or its access grant."""
    with native_api_cli_session(
        tmp_path / "finite-period",
        scope_for_destination=lambda client_id: _scope(client_id, periods=frozenset({_TARGET})),
        prepare_profile=_prepare(authority_operation),
    ) as finite:
        denied = _pipeline(finite)
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
        assert error["context"] == {"reason": "period_denied"}
        assert "total_count" not in denied.output

    with native_api_cli_session(
        tmp_path / "whole-profile",
        scope_for_destination=lambda client_id: _scope(client_id, periods=None),
        prepare_profile=_prepare(authority_operation),
    ) as whole_profile:
        accepted = _pipeline(whole_profile)
        assert accepted.exit_code == 0, accepted.output
        result = unwrap_cli_result(accepted)
        assert result["period"] == _TARGET.registry_token
        ledger = cast("dict[str, object]", result["ledger"])
        assert ledger["total_count"] == 2
        assert ledger["active_count"] == 2
        assert ledger["pending_review_count"] == 2
        _assert_password_status_matches_pipeline(whole_profile, result)

    with native_api_cli_session(
        tmp_path / "result-denied",
        scope_for_destination=lambda client_id: _scope(client_id, periods=None, result=False),
        prepare_profile=_prepare(authority_operation),
    ) as result_denied:
        denied = _pipeline(result_denied)
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        context = cast("dict[str, object]", error["context"])
        assert context["reason"] == "operation_denied"
        assert context["terminal_condition"] == "succeeded"
        assert context["effect"] == "none"
        assert "total_count" not in denied.output

        status = result_denied.invoke_password(
            "app",
            "ledger",
            "status",
            "--year",
            str(_TARGET.filing_year),
            "--period",
            _TARGET.registry_token,
        )
        assert status.exit_code == 0, status.output
        result = unwrap_cli_result(status)
        assert len(result_denied.prepared) == 2
        assert result["total_count"] == 2
