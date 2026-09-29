"""Native workflow reads bind explicit periods to the captured encrypted run."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....adapters.local_runtime.startup import RuntimeLaunchDoor
from ....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.operations.public_period import PublicPeriod
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeClientHello
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile
from ....application.workflow.persistence import load_run, save_run
from ....application.workflow.run_models import WorkflowObligationFacts, WorkflowResult, WorkflowStage
from ....application.workflow.run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
)
from ....core.modelo import Modelo
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import ObligationStatus
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import run_registered_operation
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_LABEL = "Native workflow run reader"
_FIRST = Period.from_year_and_code(2025, "1T")
_SECOND = Period.from_year_and_code(2025, "2T")
_NOW = datetime(2026, 4, 12, 9, tzinfo=UTC)
_RUN_ID = "a" * 16
_MISSING_ID = "b" * 16


def _facts() -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Workflow",
        "activities.description": "consulting",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


def _run(run_id: str, *, period: Period | None) -> WorkflowResult:
    return WorkflowResult(
        run_id=run_id,
        started_at=_NOW,
        ended_at=_NOW,
        final_stage=WorkflowStage.DONE,
        obligation=(
            WorkflowObligationFacts(
                modelo=Modelo("130"),
                period=period,
                opens_on=date(2025, 4, 1),
                closes_on=date(2025, 4, 20),
                status=ObligationStatus.UPCOMING,
            )
            if period is not None
            else None
        ),
        steps=(),
        summary_locale_key="application.workflow.results.completed",
    )


def _invoke(fixture: NativeCliProfileFixture, *arguments: str):
    assert fixture.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            fixture.label,
            "--profile-secrets-stdin",
            "app",
            "modelo",
            "work",
            *arguments,
        ),
        input=json.dumps({"profile_passphrase": fixture.passphrase}),
    )
    assert fixture.passphrase not in result.output
    return result


def _scope(client_id: UUID, *, result: bool, all_periods: bool = False) -> AccessScope:
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
        operations=frozenset({WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID, WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID}),
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
                    projection_id=f"{WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=None if all_periods else frozenset({_FIRST}),
        allow_period_independent=True,
        allow_delegation=False,
    )


def _api_client(session: NativeApiCliSession[None], root: Path) -> RuntimeFrontendClient:
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    launch = RuntimeLaunchDoor(
        endpoint,
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
    )
    client = asyncio.run(
        RuntimeFrontendClient.open(launch, profile_id=session.profile_id, frontend=OperationFrontendProjection.CLI)
    )
    secret = bytearray(session._credential.get_secret_value())
    client.login_api_key(secret)
    assert secret == bytes(len(secret))
    return client


def _read(client: RuntimeFrontendClient, run_id: str, expected: Period):
    return run_registered_operation(
        client,
        WorkflowRunReadRequest(
            profile_id=client.profile_id, run_id=run_id, expected_period=PublicPeriod.from_period(expected)
        ),
        definition_id=WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
        subject_ref=run_id,
        result_type=WorkflowRunReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )


def test_native_cli_run_details_and_inventory_use_encrypted_terminal_snapshot(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_facts())
        save_run(_run(_RUN_ID, period=_FIRST))
        close_active_bucket_session()

        run = _invoke(fixture, "run", _RUN_ID)
        assert run.exit_code == 0, run.output
        row = unwrap_cli_result(run)
        assert row["run_id"] == _RUN_ID
        assert row["modelo"] == "130" and row["final_stage"] == "DONE"
        assert row["obligation_status"] == "UPCOMING"
        details = _invoke(fixture, "run-details", _RUN_ID)
        assert details.exit_code == 0, details.output
        detail = unwrap_cli_result(details)
        assert detail["run_id"] == _RUN_ID
        assert detail["summary_locale_key"] == "application.workflow.results.completed"
        inventory = _invoke(fixture, "runs")
        assert inventory.exit_code == 0, inventory.output
        assert [item["run_id"] for item in unwrap_cli_result(inventory)["runs"]] == [_RUN_ID]

        close_active_bucket_session()
        login_profile(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            assert load_run(_RUN_ID) == _run(_RUN_ID, period=_FIRST)
        finally:
            close_active_bucket_session()


def test_native_expected_period_uses_finite_grant_and_same_reloaded_record(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare(_profile_id: UUID, _root: Path) -> None:
        save_run(_run(_RUN_ID, period=_FIRST))
        save_run(_run(_MISSING_ID, period=None))

    root = tmp_path / "finite" / "cadrumo-storage"
    with native_api_cli_session(
        tmp_path / "finite",
        scope_for_destination=lambda client_id: _scope(client_id, result=True),
        prepare_profile=prepare,
    ) as session:
        with _api_client(session, root) as client:
            completed = _read(client, _RUN_ID, _FIRST)
            assert completed.projection.run.run_id == _RUN_ID
            assert completed.projection.expected_period == PublicPeriod.from_period(_FIRST)
            assert completed.effect is OperationEffect.NONE
            with pytest.raises(RuntimeFrontendRefusedError) as missing:
                _read(client, _MISSING_ID, _FIRST)
            assert missing.value.reason == "period_denied"

        close_active_bucket_session()
        login_profile(
            name=session.profile_label,
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            save_run(_run(_RUN_ID, period=_SECOND))
        finally:
            close_active_bucket_session()
        with _api_client(session, root) as client:
            with pytest.raises(RuntimeFrontendRefusedError) as changed:
                _read(client, _RUN_ID, _FIRST)
            assert changed.value.reason == "period_denied"

        denied_read = session.invoke_credential_reference("app", "modelo", "work", "run", _RUN_ID)
        assert denied_read.exit_code == 2, denied_read.output
        assert require_error_document(denied_read.output)["error"]["context"]["reason"] == "period_denied"
        denied_list = session.invoke_credential_reference("app", "modelo", "work", "runs")
        assert denied_list.exit_code == 2, denied_list.output
        assert require_error_document(denied_list.output)["error"]["context"]["reason"] == "period_denied"


def test_native_result_denial_keeps_succeeded_none_receipt(tmp_path: Path) -> None:
    def prepare(_profile_id: UUID, _root: Path) -> None:
        save_run(_run(_RUN_ID, period=_FIRST))

    root = tmp_path / "result-denied" / "cadrumo-storage"
    with (
        native_api_cli_session(
            tmp_path / "result-denied",
            scope_for_destination=lambda client_id: _scope(client_id, result=False),
            prepare_profile=prepare,
        ) as session,
        _api_client(session, root) as client,
    ):
        with pytest.raises(CliRefusedBoundaryError) as denied:
            _read(client, _RUN_ID, _FIRST)
        assert denied.value.context is not None
        assert denied.value.context["reason"] == "operation_denied"
        assert denied.value.context["terminal_condition"] == "succeeded"
        assert denied.value.context["effect"] == "none"
