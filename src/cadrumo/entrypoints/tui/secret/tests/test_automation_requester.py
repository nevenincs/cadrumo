"""Requester form binds public choices to one server-minted recipient."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event, get_ident
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, Checkbox, Input, Select, SelectionList

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    DisclosureCategory,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile.automation_inventory import RuntimeAutomationInventoryScreen
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
        self.close_calls = 0

    @override
    def prepare_enrollment(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        del secrets_store
        assert timeout > 0
        return cast(NativeEnrollmentClient, self.enrollment)

    @override
    def close(self) -> None:
        self.close_calls += 1
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
    outcome = screen._outcome
    assert outcome is not None
    assert outcome.stage is EnrollmentStage.DECLINED
    assert not outcome.uncertain
    assert outcome.request_id == enrollment.prepared.enrollment_request_id
    assert enrollment.submits == 1
    assert client.closed


class _ReviewerClient(_OwnedRequesterClient):
    """Presentation status port; this fixture cannot approve runtime work."""

    @override
    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        assert timeout > 0
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                grant_state=None,
                grant_expires_at=None,
                grant_valid=False,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                ),
                denial=None,
            ),
        )


@pytest.mark.asyncio
async def test_pending_delivery_allows_human_review_and_cancel_preserves_request_ownership() -> None:
    """Opening/cancelling the real review view neither abandons nor approves delivery."""
    profile_id = uuid4()
    enrollment = _HeldEnrollment(profile_id)
    requester = _OwnedRequesterClient(profile_id, enrollment)
    reviewer = _ReviewerClient(profile_id, enrollment)

    async def open_client(target: UUID) -> RuntimeFrontendClient:
        assert target == profile_id
        return requester

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
        reviewer_client=reviewer,
    )
    app = ScreenHostApp(screen)
    async with app.run_test(size=(140, 48)) as pilot:
        await pilot.pause()
        assert screen.query_one("#automation-request-review", Button).disabled
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-key-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=15)
        ).isoformat()
        screen.query_one("#automation-request-submit", Button).press()
        try:
            async with asyncio.timeout(5):
                while not enrollment.polling.is_set():
                    await pilot.pause(0.02)
            screen.query_one("#automation-request-review", Button).press()
            await pilot.pause()
            review_screen = app.screen
            assert isinstance(review_screen, RuntimeAutomationInventoryScreen)
            assert review_screen._client is reviewer
            assert screen._busy and not requester.closed and not reviewer.closed
            review_screen.action_close()
            await pilot.pause()
            assert app.screen is screen
            assert screen._busy and screen._outcome is None
            assert enrollment.submits == 1
            assert not screen.query_one("#automation-request-review", Button).disabled
        finally:
            enrollment.release.set()
        async with asyncio.timeout(5):
            while screen._busy:
                await pilot.pause(0.02)
        assert not screen.query_one("#automation-request-close", Button).disabled
        assert screen._outcome is not None and screen._outcome.stage is EnrollmentStage.DECLINED
        app.exit()
    assert requester.closed and not reviewer.closed


@pytest.mark.asyncio
async def test_review_bridge_refuses_retargeted_human_session() -> None:
    profile_id = uuid4()
    enrollment = _HeldEnrollment(profile_id)
    reviewer = _ReviewerClient(profile_id, enrollment)

    async def open_client(_target: UUID) -> RuntimeFrontendClient:
        raise AssertionError("request should not be submitted")

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
        reviewer_client=reviewer,
    )
    app = ScreenHostApp(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen._submitted = enrollment._receipt(EnrollmentStage.REQUESTED)
        reviewer._session_id = uuid4()
        screen._open_review()
        await pilot.pause()
        assert app.screen is screen
        assert screen._owned_client is None and not reviewer.closed
        app.exit()


class _FailedCleanupOwner:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.close_calls = 0
        self.closed = False

    async def close(self) -> None:
        self.close_calls += 1
        if self.failures:
            self.failures -= 1
            raise OSError("private-close-error-canary")
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cancelled", "close_failures"),
    [(False, 1), (False, 2), (True, 1)],
    ids=["uncertain", "teardown-retry", "cancelled"],
)
async def test_failed_fresh_admission_keeps_request_uncertain_and_cleanup_retryable(
    cancelled: bool, close_failures: int
) -> None:
    class ReconciliationEnrollment(_HeldEnrollment):
        @override
        def inspect(self, *, timeout: float) -> AutomationReceiptProjection:
            assert timeout > 0
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    class BorrowedClient(_OwnedRequesterClient):
        @override
        def prepare_grant_change(
            self, secrets_store: AutomationSecretStore, *, timeout: float = 10
        ) -> NativeEnrollmentClient:
            del secrets_store
            assert timeout > 0
            return cast(NativeEnrollmentClient, self.enrollment)

    profile_id, reference = uuid4(), uuid4()
    enrollment = ReconciliationEnrollment(profile_id)
    client = BorrowedClient(profile_id, enrollment)
    failed_owner = _FailedCleanupOwner(close_failures)
    primary = asyncio.CancelledError() if cancelled else AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    fresh_attempts = 0

    def fresh_opener(target: UUID, received_reference: UUID, timeout: float) -> RuntimeFrontendClient:
        nonlocal fresh_attempts
        assert target == profile_id and received_reference == reference
        assert timeout > 0
        fresh_attempts += 1
        asyncio.run(close_async_resources(failed_owner, task_name="test-fresh-admission-close", primary_error=primary))
        raise primary

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        client=client,
        fresh_credential_client=fresh_opener,
    )
    async with ScreenHostApp(screen).run_test() as pilot:
        await pilot.pause()
        cast(
            "Select[EnrollmentKind]", screen.query_one("#automation-request-kind", Select)
        ).value = EnrollmentKind.RENEW
        await pilot.pause()
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-grant", Input).value = str(uuid4())
        screen.query_one("#automation-request-reference", Input).value = str(reference)
        draft = screen._draft()
        if cancelled:
            with pytest.raises(asyncio.CancelledError):
                await screen._execute(draft)
        else:
            await screen._execute(draft)
        outcome = screen._outcome
        assert outcome is not None and outcome.uncertain
        assert outcome.request_id == enrollment.prepared.enrollment_request_id
        assert outcome.review_digest == "a" * 64
        assert outcome.stage is None and outcome.credential_reference is None
        assert outcome.reason == (None if cancelled else "unavailable")
        assert enrollment.submits == fresh_attempts == 1
        assert not failed_owner.closed and failed_owner.close_calls == 1
        if close_failures == 2:
            with pytest.raises(AsyncResourceCleanupError) as caught:
                await screen.on_unmount()
            assert not failed_owner.closed and failed_owner.close_calls == 2
            await caught.value.retry_cleanup()
        else:
            await screen.on_unmount()
        assert failed_owner.closed
        assert failed_owner.close_calls == close_failures + 1
        await screen.on_unmount()
        assert failed_owner.close_calls == close_failures + 1
        assert enrollment.submits == fresh_attempts == 1
        assert not client.closed and client.close_calls == 0


@pytest.mark.asyncio
async def test_prepare_failure_cleanup_and_originating_owned_client_both_close_on_unmount() -> None:
    profile_id = uuid4()
    failed_owner = _FailedCleanupOwner(1)
    primary = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    class PreparationFailureClient(_OwnedRequesterClient):
        @override
        def prepare_enrollment(
            self, secrets_store: AutomationSecretStore, *, timeout: float = 10
        ) -> NativeEnrollmentClient:
            del secrets_store
            assert timeout > 0
            asyncio.run(close_async_resources(failed_owner, task_name="test-prepare-close", primary_error=primary))
            raise primary

    client = PreparationFailureClient(profile_id, _HeldEnrollment(profile_id))

    async def open_client(target: UUID) -> RuntimeFrontendClient:
        assert target == profile_id
        return client

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        open_client=open_client,
    )
    async with ScreenHostApp(screen).run_test() as pilot:
        await pilot.pause()
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-key-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=15)
        ).isoformat()
        await screen._execute(screen._draft())
        outcome = screen._outcome
        assert outcome is not None and not outcome.uncertain
        assert outcome.request_id is None
        assert client.enrollment.submits == 0
        assert not client.closed and not failed_owner.closed
        await screen.on_unmount()
        assert client.closed and client.close_calls == 1
        assert failed_owner.closed and failed_owner.close_calls == 2
        await screen.on_unmount()
        assert client.close_calls == 1 and failed_owner.close_calls == 2


@pytest.mark.asyncio
async def test_returned_fresh_client_refusal_keeps_primary_and_retries_failed_close() -> None:
    primary = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    ui_thread = get_ident()
    close_threads: list[int] = []

    class ReconciliationEnrollment(_HeldEnrollment):
        @override
        def inspect(self, *, timeout: float) -> AutomationReceiptProjection:
            assert timeout > 0
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    class BorrowedClient(_OwnedRequesterClient):
        @override
        def prepare_grant_change(
            self, secrets_store: AutomationSecretStore, *, timeout: float = 10
        ) -> NativeEnrollmentClient:
            del secrets_store
            assert timeout > 0
            return cast(NativeEnrollmentClient, self.enrollment)

    class FreshClient(_OwnedRequesterClient):
        @override
        def reconcile_enrollment(self, request_id: UUID, *, timeout: float = 10) -> AutomationReceiptProjection:
            assert request_id == self.enrollment.prepared.enrollment_request_id
            assert timeout > 0
            raise primary

        @override
        def close(self) -> None:
            close_threads.append(get_ident())
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("private-fresh-close-canary")
            self.closed = True

    profile_id, reference = uuid4(), uuid4()
    enrollment = ReconciliationEnrollment(profile_id)
    original = BorrowedClient(profile_id, enrollment)
    fresh = FreshClient(profile_id, enrollment)
    fresh_attempts = 0

    def fresh_opener(target: UUID, received_reference: UUID, timeout: float) -> RuntimeFrontendClient:
        nonlocal fresh_attempts
        assert target == profile_id and received_reference == reference
        assert timeout > 0
        fresh_attempts += 1
        return fresh

    screen = RuntimeAutomationRequesterScreen(
        profile_id=profile_id,
        contracts=_view_contracts(),
        secrets_store=cast(AutomationSecretStore, object()),
        client=original,
        fresh_credential_client=fresh_opener,
    )
    async with ScreenHostApp(screen).run_test() as pilot:
        await pilot.pause()
        cast(
            "Select[EnrollmentKind]", screen.query_one("#automation-request-kind", Select)
        ).value = EnrollmentKind.RENEW
        await pilot.pause()
        screen.query_one("#automation-request-expiry", Input).value = (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat()
        screen.query_one("#automation-request-grant", Input).value = str(uuid4())
        screen.query_one("#automation-request-reference", Input).value = str(reference)
        await screen._execute(screen._draft())
        outcome = screen._outcome
        assert outcome is not None and outcome.uncertain
        assert outcome.reason == "unavailable"
        assert outcome.request_id == enrollment.prepared.enrollment_request_id
        assert outcome.review_digest == "a" * 64
        assert outcome.stage is None and outcome.credential_reference is None
        assert isinstance(primary.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert enrollment.submits == fresh_attempts == 1
        assert fresh.close_calls == 1 and not fresh.closed
        assert len(close_threads) == 1 and close_threads[0] != ui_thread
        await screen.on_unmount()
        assert fresh.closed and fresh.close_calls == 2
        assert len(close_threads) == 2 and all(thread != ui_thread for thread in close_threads)
        await screen.on_unmount()
        assert fresh.close_calls == 2
        assert enrollment.submits == fresh_attempts == 1
        assert not original.closed and original.close_calls == 0


@pytest.mark.asyncio
async def test_unmount_caller_cancellation_drains_native_request_and_releases_owned_client() -> None:
    async def scenario() -> None:
        profile_id = uuid4()
        enrollment = _HeldEnrollment(profile_id)
        client = _OwnedRequesterClient(profile_id, enrollment)

        async def open_client(target: UUID) -> RuntimeFrontendClient:
            assert target == profile_id
            return client

        async def event_loop_checkpoint() -> None:
            checkpoint = asyncio.Event()
            asyncio.get_running_loop().call_soon(checkpoint.set)
            await checkpoint.wait()

        screen = RuntimeAutomationRequesterScreen(
            profile_id=profile_id,
            contracts=_view_contracts(),
            secrets_store=cast(AutomationSecretStore, object()),
            open_client=open_client,
        )
        async with ScreenHostApp(screen).run_test() as pilot:
            await pilot.pause()
            screen.query_one("#automation-request-expiry", Input).value = (
                datetime.now(UTC) + timedelta(days=30)
            ).isoformat()
            screen.query_one("#automation-request-key-expiry", Input).value = (
                datetime.now(UTC) + timedelta(days=15)
            ).isoformat()
            screen._request_task = asyncio.create_task(screen._execute(screen._draft()))
            try:
                assert await asyncio.to_thread(enrollment.polling.wait, 5)
                closing = asyncio.create_task(screen.on_unmount())
                await event_loop_checkpoint()
                closing.cancel()
                await event_loop_checkpoint()
                closing.cancel()
                await event_loop_checkpoint()
                assert not closing.done()
                assert not client.closed and client.close_calls == 0
                enrollment.release.set()
                with pytest.raises(asyncio.CancelledError):
                    await closing
                assert client.closed and client.close_calls == 1
                outcome = screen._outcome
                assert outcome is not None and outcome.stage is EnrollmentStage.DECLINED
                assert not outcome.uncertain
                assert outcome.request_id == enrollment.prepared.enrollment_request_id
                assert enrollment.submits == 1
                await screen.on_unmount()
                assert client.close_calls == 1
            finally:
                enrollment.release.set()

    await asyncio.wait_for(scenario(), timeout=10)
