"""Exact-session operation dispatch for the installed activity-asset TUI door."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ActivityAssetAuthorityProvenance,
    ActivityAssetInspectRequest,
    ActivityAssetOperationPortsFactory,
)
from cadrumo.application.actividad_asset.activity_asset_projections import ActivityAssetInspectProjection
from cadrumo.application.actividad_asset.activity_asset_results import ActivityAssetInspectionRevision
from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetRevisionSnapshot
from cadrumo.application.actividad_asset.registered_operations import (
    build_activity_asset_inspect_definition,
    build_activity_asset_inspect_registration,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController
from cadrumo.entrypoints.tui.runtime_actividad_asset import RuntimeActivityAssetTuiActionsV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_AUTHORITY = ActivityAssetAuthorityProvenance(logical_generation="b" * 64, reader_incarnation="c" * 64)
_NOW = datetime(2026, 9, 29, tzinfo=UTC)


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(
        self,
        *,
        observation: OperationObservationSuccessV1,
        result: ActivityAssetInspectProjection,
        client: _Client,
        expire_after_result: bool,
    ) -> None:
        self.observation = observation
        self.result = result
        self.client = client
        self.expire_after_result = expire_after_result
        self.started = False
        self.result_reads: list[tuple[type[BaseModel], int, bool]] = []

    async def start(self) -> str:
        self.started = True
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> ActivityAssetInspectProjection:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        if self.expire_after_result:
            self.client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
        return self.result


def _revision() -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="runtime-tui-asset",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="1" * 64,
            invoice_evidence_id="runtime-tui-invoice",
            evidence_fingerprint="2" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("100.00"),
            prior_allocation_provenance="runtime TUI fixture",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0.00"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-informacion-software",
        ),
    )


def _inspect_contract():
    factory = cast(ActivityAssetOperationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_activity_asset_inspect_definition(factory)
    registration = build_activity_asset_inspect_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry.lookup_public_contract(ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID), registry.public_contract_set


def _observation(*, effect: OperationEffect = OperationEffect.NONE) -> OperationObservationSuccessV1:
    contract, contract_set = _inspect_contract()
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref="f" * 64,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _projection(revision: ActivityAssetRevision) -> ActivityAssetInspectProjection:
    return ActivityAssetInspectProjection(
        profile_id=_PROFILE_ID,
        authority=_AUTHORITY,
        outcome="succeeded",
        asset_id=revision.asset_id,
        revisions=(
            ActivityAssetInspectionRevision(
                revision=ActivityAssetRevisionSnapshot.from_domain(revision),
                revision_id=revision.revision_id,
            ),
        ),
    )


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client: _Client,
    result: ActivityAssetInspectProjection,
    expire_after_result: bool = False,
    effect: OperationEffect = OperationEffect.NONE,
) -> tuple[list[dict[str, object]], _Controller]:
    from cadrumo.entrypoints.tui.operations import runtime_profile_session as bridge

    status_checks: list[tuple[UUID, UUID]] = []

    def read_session(
        _client: RuntimeFrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        status_checks.append((profile_id, session_id))
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    controller = _Controller(
        observation=_observation(effect=effect),
        result=result,
        client=client,
        expire_after_result=expire_after_result,
    )
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        return controller

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    return submissions, controller


def test_activity_asset_tui_door_submits_exact_profile_and_reads_complete_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    revision = _revision()
    result = _projection(revision)
    submissions, controller = _install_runtime(monkeypatch, client=client, result=result)
    actions = RuntimeActivityAssetTuiActionsV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    inspection = actions.inspect(revision.asset_id)

    assert inspection.asset_id == revision.asset_id
    assert inspection.revisions == (revision,)
    assert controller.started
    assert controller.result_reads == [(ActivityAssetInspectProjection, 1, True)]
    assert submissions[0]["definition_id"] == ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID
    assert submissions[0]["subject_ref"] == profile_operation_subject(str(_PROFILE_ID))
    assert submissions[0]["payload"] == ActivityAssetInspectRequest(profile_id=_PROFILE_ID, asset_id=revision.asset_id)
    assert submissions[0]["expected_session_id"] == _SESSION_ID


def test_activity_asset_tui_door_retains_terminal_receipt_if_access_expires_after_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    revision = _revision()
    submissions, _controller = _install_runtime(
        monkeypatch,
        client=client,
        result=_projection(revision),
        expire_after_result=True,
    )
    actions = RuntimeActivityAssetTuiActionsV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    with pytest.raises(AccountSessionExpiredError) as raised:
        actions.inspect(revision.asset_id)

    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
        "effect": OperationEffect.NONE.value,
        "refusal_code": None,
    }


def test_activity_asset_tui_door_fails_closed_when_its_retained_session_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    revision = _revision()
    submissions, _controller = _install_runtime(monkeypatch, client=client, result=_projection(revision))
    actions = RuntimeActivityAssetTuiActionsV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        actions.inspect(revision.asset_id)

    assert submissions == []
