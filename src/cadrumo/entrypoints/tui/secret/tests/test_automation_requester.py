"""Requester form binds public choices to one server-minted recipient."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, Checkbox, Input, Select, SelectionList

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.user_profile.access_contracts import AccessAction, DisclosureCategory
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.secret.automation_requester import RuntimeAutomationRequesterScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _view_contracts() -> OperationPublicContractSetV1:
    """Use the real profile registration without constructing unrelated live families."""
    definitions = build_user_profile_operation_definitions()
    registration = next(
        item
        for item in build_user_profile_operation_registrations(definitions)
        if str(item.contract.definition_id) == "user-profile.view"
    )
    return OperationPublicContractSetV1.build((registration.contract,))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
async def test_api_change_form_pins_target_and_protected_reference(kind: EnrollmentKind) -> None:
    """An admitted API client can request only a typed change of its own grant."""
    profile_id = uuid4()
    client = _OwnedRequesterClient(profile_id, _HeldEnrollment(profile_id))
    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        client=client,
    )
    app = ScreenHostApp(screen)
    target_grant, target_key, reference = uuid4(), uuid4(), uuid4()
    async with app.run_test() as pilot:
        await pilot.pause()
        cast("Select[EnrollmentKind]", screen.query_one("#automation-request-kind", Select)).value = kind
        await pilot.pause()
        cast("SelectionList[str]", screen.query_one("#automation-request-operations", SelectionList)).select(
            "user-profile.view"
        )
        cast("SelectionList[str]", screen.query_one("#automation-request-actions", SelectionList)).select(
            AccessAction.OBSERVE.value
        )
        cast("SelectionList[str]", screen.query_one("#automation-request-actions", SelectionList)).select(
            AccessAction.COMMIT.value
        )
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-grant", Input).value = str(target_grant)
        screen.query_one("#automation-request-reference", Input).value = str(reference)
        if kind is EnrollmentKind.ROTATE:
            screen.query_one("#automation-request-key", Input).value = str(target_key)
            screen.query_one("#automation-request-key-expiry", Input).value = (
                datetime.now(UTC) + timedelta(days=15)
            ).isoformat()
        draft = screen._draft()
        proposal = draft.proposal(uuid4())
        assert proposal.kind is kind
        assert proposal.target_grant_id == target_grant
        assert proposal.target_key_id == (target_key if kind is EnrollmentKind.ROTATE else None)
        assert draft.credential_reference == reference
        assert proposal.scope.operations == {"user-profile.view"}
        assert proposal.scope.actions == {AccessAction.OBSERVE, AccessAction.COMMIT}
        assert not client.closed
        app.exit()
    assert not client.closed


@pytest.mark.asyncio
async def test_form_uses_registered_tui_choices_and_server_destination_only() -> None:
    """A selected schema never carries a destination supplied by the form."""
    profile_id = uuid4()
    opened: list[UUID] = []

    async def open_client(target: UUID) -> RuntimeFrontendClient:
        opened.append(target)
        raise AssertionError("form must not open a client")

    contracts = _view_contracts()
    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=contracts,
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
    )
    app = ScreenHostApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        operation = "user-profile.view"
        contract = next(item for item in contracts.definitions if str(item.definition_id) == operation)
        assert OperationFrontendProjection.TUI in contract.permitted_frontends
        assert operation in screen._operation_choices
        assert all(
            str(item.definition_id) in screen._operation_choices
            for item in contracts.definitions
            if OperationFrontendProjection.TUI in item.permitted_frontends
        )
        assert all(
            str(item.definition_id) not in screen._operation_choices
            for item in contracts.definitions
            if OperationFrontendProjection.TUI not in item.permitted_frontends
        )
        cast("SelectionList[str]", screen.query_one("#automation-request-operations", SelectionList)).select(operation)
        cast("SelectionList[str]", screen.query_one("#automation-request-actions", SelectionList)).select(
            AccessAction.OBSERVE.value
        )
        assert contract.result_schema is not None
        schema_id = str(contract.result_schema.schema_id)
        cast("SelectionList[str]", screen.query_one("#automation-request-disclosures", SelectionList)).select(
            f"{schema_id}|{DisclosureCategory.PROFILE_VALUES.value}"
        )
        cast("Select[str]", screen.query_one("#automation-request-period-mode", Select)).value = "all"
        screen.query_one("#automation-request-independent", Checkbox).value = True
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-key-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=15)
        ).isoformat()
        draft = screen._draft()
        destination = uuid4()
        proposal = draft.proposal(destination)
        assert proposal.kind is EnrollmentKind.ENROLL
        assert proposal.scope.operations == {operation}
        assert proposal.scope.actions == {AccessAction.OBSERVE}
        assert proposal.scope.periods is None
        assert len(proposal.scope.disclosures) == 1
        disclosure = next(iter(proposal.scope.disclosures))
        assert disclosure.destination_id == destination
        assert str(disclosure.projection_id) == schema_id
        assert disclosure.category is DisclosureCategory.PROFILE_VALUES
        assert opened == []
        app.exit()


@pytest.mark.asyncio
async def test_form_refuses_unlisted_operation_and_never_opens_client() -> None:
    """Mutated widget selection cannot add a grant outside the immutable manifest."""
    profile_id = uuid4()
    calls: list[UUID] = []

    async def open_client(target: UUID) -> RuntimeFrontendClient:
        calls.append(target)
        raise AssertionError("form must not open a client")

    contracts = _view_contracts()
    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=contracts,
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
    )
    app = ScreenHostApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-key-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=15)
        ).isoformat()
        operation = "user-profile.view"
        cast("SelectionList[str]", screen.query_one("#automation-request-operations", SelectionList)).select(operation)
        choices = screen._operation_choices
        screen._operation_choices = ()
        with pytest.raises(ValueError, match="undeclared operation"):
            screen._draft()
        screen._operation_choices = choices
    assert calls == []
    app.exit()


class _HeldEnrollment:
    """A transport-seam double that blocks one protected poll, not an authority."""

    def __init__(self, profile_id: UUID) -> None:
        self.prepared = SimpleNamespace(enrollment_request_id=uuid4(), destination_id=uuid4())
        self._profile_id = profile_id
        self.release = Event()
        self.polling = Event()
        self.declined = False
        self.submits = 0

    def _receipt(self, stage: EnrollmentStage) -> AutomationReceiptProjection:
        return AutomationReceiptProjection(
            request_id=self.prepared.enrollment_request_id,
            profile_id=self._profile_id,
            stage=stage,
            review_digest="a" * 64,
            grant_id=uuid4(),
            key_id=None,
            credential_reference=None,
        )

    def submit(self, _proposal: object, *, timeout: float) -> AutomationReceiptProjection:
        assert timeout > 0
        self.submits += 1
        return self._receipt(EnrollmentStage.REQUESTED)

    def inspect(self, *, timeout: float) -> AutomationReceiptProjection:
        assert timeout > 0
        return self._receipt(EnrollmentStage.DECLINED if self.declined else EnrollmentStage.REQUESTED)

    def poll(self, *, timeout: float) -> None:
        assert timeout > 0
        self.polling.set()
        assert self.release.wait(5)
        self.declined = True

    def verified_terminal(self) -> None:
        return None


class _OwnedRequesterClient(RuntimeFrontendClient):
    """Observe only frontend ownership around one already-prepared seam."""

    def __init__(self, profile_id: UUID, enrollment: _HeldEnrollment) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id = uuid4()
        self.enrollment = enrollment
        self.closed = False

    @override
    def prepare_enrollment(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        del secrets_store
        assert timeout > 0
        return cast(NativeEnrollmentClient, self.enrollment)

    @override
    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_close_waits_for_submitted_delivery_before_closing_owned_client() -> None:
    """A dismissed view cannot abandon the native request or misreport decline."""
    profile_id = uuid4()
    enrollment = _HeldEnrollment(profile_id)
    client = _OwnedRequesterClient(profile_id, enrollment)

    async def open_client(target: UUID) -> RuntimeFrontendClient:
        assert target == profile_id
        return client

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
    )
    app = ScreenHostApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-key-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=15)
        ).isoformat()
        screen.query_one("#automation-request-submit", Button).press()
        async with asyncio.timeout(5):
            while not enrollment.polling.is_set():
                await pilot.pause(0.02)
        assert screen._submitted is not None
        assert not client.closed
        app.exit()
        await pilot.pause(0.05)
        assert not client.closed
        enrollment.release.set()
    outcome = screen.safe_outcome
    assert outcome is not None
    assert outcome.stage is EnrollmentStage.DECLINED
    assert not outcome.uncertain
    assert outcome.request_id == enrollment.prepared.enrollment_request_id
    assert enrollment.submits == 1
    assert client.closed
