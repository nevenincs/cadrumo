"""Automation inventory UI owns a read but never owns the borrowed client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.content import Content
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from cadrumo.adapters.local_runtime.automation_decision import AutomationDecisionCompletion, AutomationDecisionRunError
from cadrumo.adapters.local_runtime.automation_inventory import AutomationInventoryCompletion
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationGrantProjection,
    AutomationInventoryProjection,
    AutomationKeyProjection,
    AutomationPeriodProjection,
    AutomationProposalProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile import automation_inventory as subject
from cadrumo.entrypoints.tui.profile import automation_inventory_details as detail_subject
from cadrumo.entrypoints.tui.runtime_access_management import RuntimeAccessManagementScreen
from cadrumo.entrypoints.tui.secret import automation_decision as decision_subject

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Client(RuntimeFrontendClient):
    """Explicit screen fault port; registered reader acceptance is tested elsewhere."""

    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self._frontend = OperationFrontendProjection.TUI
        self.status_calls = 0
        self.closed = False
        self.expires_at = datetime.now(UTC) + timedelta(minutes=5)

    @override
    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        self.status_calls += 1
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=self.expires_at,
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

    @override
    def close(self) -> None:
        self.closed = True

    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        return ()


def _inventory(profile_id: UUID) -> AutomationInventoryProjection:
    instant = datetime.now(UTC)
    grant_id, key_id = uuid4(), uuid4()
    scope = AutomationScopeProjection(
        operations=("user-profile.field-mutation", "[red]literal-operation[/red]"),
        actions=(),
        disclosures=(),
        periods=(AutomationPeriodProjection(filing_year=2026, code="3T"),),
        allow_period_independent=False,
        allow_delegation=False,
    )
    return AutomationInventoryProjection(
        grants=(
            AutomationGrantProjection(
                grant_id=grant_id,
                profile_id=profile_id,
                client_id=uuid4(),
                state=AuthorityState.ACTIVE,
                scope=scope,
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                unattended=True,
                allow_os_lock=False,
            ),
        ),
        keys=(
            AutomationKeyProjection(
                key_id=key_id,
                grant_id=grant_id,
                profile_id=profile_id,
                state=AuthorityState.ACTIVE,
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                last_used_at=None,
            ),
        ),
        requests=(
            AutomationReviewProjection(
                receipt=AutomationReceiptProjection(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    stage=EnrollmentStage.REQUESTED,
                    review_digest="b" * 64,
                    grant_id=grant_id,
                    key_id=key_id,
                    credential_reference=None,
                ),
                client_id=uuid4(),
                destination_id=uuid4(),
                proposal=AutomationProposalProjection(
                    kind=EnrollmentKind.RENEW,
                    scope=scope,
                    expires_at=instant + timedelta(days=1),
                    key_expires_at=instant + timedelta(days=1),
                    unattended=False,
                    allow_os_lock=True,
                    target_grant_id=grant_id,
                    target_key_id=key_id,
                ),
                expires_at=instant + timedelta(minutes=10),
            ),
        ),
    )


async def _until[T](pilot: Pilot[T], condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not condition():
            await pilot.pause(0.02)


@pytest.mark.asyncio
@pytest.mark.parametrize("loss", ["changed_binding", "expired"])
async def test_inventory_tables_show_public_details_and_refresh_only_on_action(
    monkeypatch: pytest.MonkeyPatch, loss: str
) -> None:
    client = _Client()
    projection = _inventory(client.profile_id)
    calls = 0

    def read(bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        nonlocal calls
        assert bound is client
        calls += 1
        return AutomationInventoryCompletion(operation_id="a" * 64, projection=projection)

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    screen = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(screen).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: screen.query_one("#automation-inventory-grants", DataTable).row_count == 1)
        assert calls == 1 and client.status_calls == 2
        assert screen.query_one("#automation-inventory-keys", DataTable).row_count == 1
        assert screen.query_one("#automation-inventory-requests", DataTable).row_count == 1
        details = str(screen.query_one("#automation-inventory-details", Static).content)
        assert "user-profile.field-mutation" in details
        assert "[red]literal-operation[/red]" in details
        rendered = screen.query_one("#automation-inventory-details", Static).render()
        assert isinstance(rendered, Content)
        assert "[red]literal-operation[/red]" in rendered.plain
        assert "2026/3T" in details
        assert tr("flows.confirm.yes") in details and tr("flows.confirm.no") in details
        assert "secret" not in details and "verifier" not in details and "dek" not in details
        grant_row = screen.query_one("#automation-inventory-grants", DataTable).get_row_at(0)
        assert str(projection.grants[0].grant_id) == grant_row[0]
        await pilot.pause(0.05)
        assert calls == 1

        screen.query_one("#automation-inventory-refresh", Button).press()
        await _until(pilot, lambda: calls == 2 and not screen._busy)
        if loss == "changed_binding":
            client._session_id = uuid4()
        else:
            client.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        screen.query_one("#automation-inventory-refresh", Button).press()
        await _until(pilot, lambda: screen.access_lost)
        assert calls == 2
        assert screen.query_one("#automation-inventory-grants", DataTable).row_count == 0
        assert screen.query_one("#automation-inventory-refresh", Button).disabled
        assert not client.closed


def test_period_restrictions_and_review_validity_are_not_collapsed() -> None:
    profile_id = uuid4()
    inventory = _inventory(profile_id)
    scope = inventory.grants[0].scope
    unrestricted = scope.model_copy(update={"periods": None})
    none_allowed = scope.model_copy(update={"periods": ()})
    assert tr("tui.automation_inventory.all_periods") in "\n".join(detail_subject._scope(unrestricted))
    assert tr("tui.automation_inventory.no_periods") in "\n".join(detail_subject._scope(none_allowed))
    assert "2026/3T" in "\n".join(detail_subject._scope(scope))
    unattended_notice = tr("tui.automation_inventory.unattended_notice")
    assert unattended_notice in detail_subject._grant_detail(inventory.grants[0])
    assert unattended_notice not in detail_subject._grant_detail(
        inventory.grants[0].model_copy(update={"unattended": False})
    )

    request = inventory.requests[0]
    detail = detail_subject._request_detail(request)
    assert request.expires_at.isoformat() in detail
    assert request.proposal.expires_at.isoformat() in detail
    assert request.proposal.key_expires_at is not None
    assert request.proposal.key_expires_at.isoformat() in detail
    assert str(request.proposal.target_grant_id) in detail
    assert str(request.proposal.target_key_id) in detail
    assert tr("tui.automation_inventory.grant_expires") in detail
    assert tr("tui.automation_inventory.key_expires") in detail


@pytest.mark.asyncio
async def test_known_session_expiry_clears_display_without_a_second_inventory_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    reads = 0

    def read(_bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        nonlocal reads
        reads += 1
        return AutomationInventoryCompletion(operation_id="e" * 64, projection=_inventory(client.profile_id))

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    screen = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(screen).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: screen.query_one("#automation-inventory-grants", DataTable).row_count == 1)
        client.expires_at = datetime.now(UTC) + timedelta(milliseconds=700)
        screen.query_one("#automation-inventory-refresh", Button).press()
        await _until(pilot, lambda: reads == 2 and not screen._busy)
        await _until(pilot, lambda: screen.access_lost)
        assert reads == 2
        assert screen.query_one("#automation-inventory-grants", DataTable).row_count == 0
        assert screen.query_one("#automation-inventory-refresh", Button).disabled
        assert not client.closed


@pytest.mark.asyncio
async def test_parent_opens_human_inventory_without_rebinding_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("inventory cannot open a recovery connection")

    def read(bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        assert bound is client
        return AutomationInventoryCompletion(operation_id="d" * 64, projection=_inventory(client.profile_id))

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    parent = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(parent).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: not parent.query_one("#runtime-access-view-automation", Button).disabled)
        parent.query_one("#runtime-access-view-automation", Button).press()
        await _until(pilot, lambda: isinstance(pilot.app.screen, subject.RuntimeAutomationInventoryScreen))
        inventory = pilot.app.screen
        assert isinstance(inventory, subject.RuntimeAutomationInventoryScreen)
        await _until(pilot, lambda: inventory.is_mounted)
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-grants", DataTable).row_count == 1)
        inventory.action_close()
        await _until(pilot, lambda: pilot.app.screen is parent)
        assert not parent.access_lost
        assert not client.closed


@pytest.mark.asyncio
async def test_unmount_clears_rows_and_drains_inflight_read_without_late_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    started, release, finished = Event(), Event(), Event()

    def read(_bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        started.set()
        if not release.wait(5):
            raise TimeoutError("test inventory read was not released")
        finished.set()
        return AutomationInventoryCompletion(operation_id="c" * 64, projection=_inventory(client.profile_id))

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    screen = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(screen).run_test(size=(130, 45)) as pilot:
        assert await asyncio.to_thread(started.wait, 5)
        closing = asyncio.ensure_future(pilot.app.pop_screen())
        try:
            await asyncio.sleep(0.05)
            assert not closing.done()
            assert not finished.is_set()
            assert screen._inventory is None
        finally:
            release.set()
        await asyncio.wait_for(closing, 5)
        assert finished.is_set()
        assert screen._inventory is None
        assert not client.closed


@pytest.mark.asyncio
async def test_selected_review_approval_repeats_consent_and_wipes_one_fresh_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    projection = _inventory(client.profile_id)
    review = projection.requests[0]
    started, release = Event(), Event()
    captured: list[bytearray] = []

    def read(bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        assert bound is client
        return AutomationInventoryCompletion(operation_id="a" * 64, projection=projection)

    def decide(
        bound: RuntimeFrontendClient,
        selected: AutomationReviewProjection,
        *,
        decision: str,
        password: bytearray | None,
    ) -> AutomationDecisionCompletion:
        assert bound is client and selected is review and decision == "approve"
        assert password is not None and bytes(password) == b"fresh-review-proof"
        captured.append(password)
        started.set()
        if not release.wait(5):
            raise TimeoutError("test approval was not released")
        return AutomationDecisionCompletion("c" * 64, review.receipt, OperationEffect.UPDATED)

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    monkeypatch.setattr(decision_subject, "run_automation_decision", decide)
    inventory = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(inventory).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-requests", DataTable).row_count == 1)
        table = inventory.query_one("#automation-inventory-requests", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await _until(pilot, lambda: not inventory.query_one("#automation-inventory-approve", Button).disabled)
        inventory.query_one("#automation-inventory-approve", Button).press()
        await _until(pilot, lambda: isinstance(pilot.app.screen, decision_subject.RuntimeAutomationDecisionScreen))
        modal = pilot.app.screen
        assert isinstance(modal, decision_subject.RuntimeAutomationDecisionScreen)
        consent = str(modal.query_one("#automation-decision-review", Static).content)
        assert str(review.receipt.profile_id) in consent
        assert str(review.receipt.request_id) in consent
        assert review.receipt.review_digest in consent
        assert review.proposal.expires_at.isoformat() in consent
        assert review.proposal.key_expires_at is not None
        assert review.proposal.key_expires_at.isoformat() in consent
        assert "[red]literal-operation[/red]" in consent
        password_field = modal.query_one("#automation-decision-password", Input)
        assert password_field.password
        password_field.value = "fresh-review-proof"
        modal.query_one("#automation-decision-confirm", Button).press()
        try:
            assert await asyncio.to_thread(started.wait, 5)
            assert password_field.value == ""
            assert modal.query_one("#automation-decision-confirm", Button).disabled
        finally:
            release.set()
        await _until(pilot, lambda: modal._outcome is not None and modal._outcome.completed and not modal._busy)
        assert captured and captured[0] == bytes(len(captured[0]))
        modal.action_close()
        await _until(pilot, lambda: pilot.app.screen is inventory)
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-requests", DataTable).row_count == 0)
        status = str(inventory.query_one("#automation-inventory-status", Static).content)
        assert "c" * 64 in status and OperationEffect.UPDATED.value in status
        assert not client.closed


@pytest.mark.asyncio
async def test_decline_has_no_password_and_preserves_unknown_post_submit_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    projection = _inventory(client.profile_id)
    review = projection.requests[0]

    def read(_bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        return AutomationInventoryCompletion(operation_id="a" * 64, projection=projection)

    def refuse(
        bound: RuntimeFrontendClient,
        selected: AutomationReviewProjection,
        *,
        decision: str,
        password: bytearray | None,
    ) -> AutomationDecisionCompletion:
        assert bound is client and selected is review and decision == "decline" and password is None
        raise AutomationDecisionRunError(operation_id="d" * 64, code=RuntimeRefusalCode.CONNECTION_CLOSED.value)

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    monkeypatch.setattr(decision_subject, "run_automation_decision", refuse)
    inventory = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(inventory).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-requests", DataTable).row_count == 1)
        table = inventory.query_one("#automation-inventory-requests", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await _until(pilot, lambda: not inventory.query_one("#automation-inventory-decline", Button).disabled)
        inventory.query_one("#automation-inventory-decline", Button).press()
        await _until(pilot, lambda: isinstance(pilot.app.screen, decision_subject.RuntimeAutomationDecisionScreen))
        modal = pilot.app.screen
        assert isinstance(modal, decision_subject.RuntimeAutomationDecisionScreen)
        assert not modal.query("#automation-decision-password")
        modal.query_one("#automation-decision-confirm", Button).press()
        await _until(pilot, lambda: modal._outcome is not None and not modal._busy)
        assert modal._outcome is not None
        assert modal._outcome.operation_id == "d" * 64
        assert modal._outcome.effect is None and not modal._outcome.completed
        assert tr("tui.automation_decision.unknown_effect") in str(
            modal.query_one("#automation-decision-status", Static).content
        )
        modal.action_close()
        await _until(pilot, lambda: pilot.app.screen is inventory)
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-requests", DataTable).row_count == 0)
        assert "d" * 64 in str(inventory.query_one("#automation-inventory-status", Static).content)
        assert not client.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_expiry_during_submitted_decision_clears_consent_and_waits_for_settlement(
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    client = _Client()
    projection = _inventory(client.profile_id)
    started, release, finished = Event(), Event(), Event()

    def read(_bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        return AutomationInventoryCompletion(operation_id="a" * 64, projection=projection)

    def decide(
        _bound: RuntimeFrontendClient,
        _selected: AutomationReviewProjection,
        *,
        decision: str,
        password: bytearray | None,
    ) -> AutomationDecisionCompletion:
        assert decision == "approve" and password is not None
        started.set()
        if not release.wait(5):
            raise TimeoutError("test decision was not released")
        finished.set()
        if failed:
            raise AutomationDecisionRunError(
                operation_id="e" * 64,
                code=RuntimeRefusalCode.CONNECTION_CLOSED.value,
                terminal_condition=OperationTerminalCondition.FAILED,
                effect=OperationEffect.UPDATED,
            )
        return AutomationDecisionCompletion("e" * 64, projection.requests[0].receipt, OperationEffect.UPDATED)

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    monkeypatch.setattr(decision_subject, "run_automation_decision", decide)
    inventory = subject.RuntimeAutomationInventoryScreen(client)
    async with ScreenHostApp(inventory).run_test(size=(130, 45)) as pilot:
        await _until(pilot, lambda: inventory.query_one("#automation-inventory-requests", DataTable).row_count == 1)
        table = inventory.query_one("#automation-inventory-requests", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await _until(pilot, lambda: not inventory.query_one("#automation-inventory-approve", Button).disabled)
        inventory.query_one("#automation-inventory-approve", Button).press()
        await _until(pilot, lambda: isinstance(pilot.app.screen, decision_subject.RuntimeAutomationDecisionScreen))
        modal = pilot.app.screen
        assert isinstance(modal, decision_subject.RuntimeAutomationDecisionScreen)
        client.expires_at = datetime.now(UTC) + timedelta(milliseconds=650)
        password_field = modal.query_one("#automation-decision-password", Input)
        password_field.value = "fresh-proof"
        modal.query_one("#automation-decision-confirm", Button).press()
        try:
            assert await asyncio.to_thread(started.wait, 5)
            await _until(pilot, lambda: modal.access_lost)
            assert str(modal.query_one("#automation-decision-review", Static).content) == ""
            assert password_field.value == ""
            assert not finished.is_set()
            closing = asyncio.ensure_future(pilot.app.pop_screen())
            await asyncio.sleep(0.05)
            assert not closing.done()
        finally:
            release.set()
        await asyncio.wait_for(closing, 5)
        assert finished.is_set()
        assert modal._outcome is not None
        assert modal._outcome.operation_id == "e" * 64
        assert modal._outcome.effect is OperationEffect.UPDATED
        assert modal._outcome.completed is not failed
        assert modal._outcome.terminal_condition is (
            OperationTerminalCondition.FAILED if failed else OperationTerminalCondition.SUCCEEDED
        )
        assert modal._review is None and modal._consent_text == ""
        await _until(pilot, lambda: pilot.app.screen is inventory)
        await _until(pilot, lambda: inventory.access_lost)
        assert inventory.query_one("#automation-inventory-requests", DataTable).row_count == 0
        assert not client.closed
