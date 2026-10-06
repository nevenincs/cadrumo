"""The restricted TUI shell displays status without acquiring human authority."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.profile_access import RuntimeProfileStatus, RuntimeSessionsLocked
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessStatus,
)
from ....application.user_profile.access_projections import PublicAccessSession
from ....application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ....core.i18n.render import tr
from ....core.period import Period
from ..account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..runtime_session import RuntimeRestrictedSessionApp

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_pushed_retirement_clears_private_view_without_waiting_for_status_poll() -> None:
    client = _Client()
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic private profile")
    async with app.run_test() as pilot:
        await _shown(app, pilot)
        reads = client.status_calls
        assert client.retirement_callback is not None
        client.retirement_callback()
        await pilot.pause()
        assert app._cleared
        assert str(app.query_one("#restricted-profile", Static).render()) == ""
        assert client.status_calls == reads
    assert client.retirement_callback is None


class _Client(RuntimeFrontendClient):
    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self._frontend = OperationFrontendProjection.TUI
        self.retirement_callback: Callable[[], None] | None = None
        self.status_calls = 0
        self.lock_calls = 0
        self.close_calls = 0
        self.human_calls = 0
        self.lock_started = Event()
        self.lock_release = Event()
        self.lock_release.set()
        self.lock_acknowledged = True
        self.lock_refusal = False
        self.reported_profile_id = self._profile_id
        self.expires_at = datetime.now(UTC) + timedelta(minutes=5)
        self.grant_valid = True
        self.scope = AccessScope(
            operations=frozenset({"user-profile.view"}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=frozenset({Period.from_year_and_code(2025, "1T")}),
            allow_period_independent=False,
            allow_delegation=False,
        )

    @override
    def subscribe_session_retirement(self, receive: Callable[[], None]) -> Callable[[], None]:
        self.retirement_callback = receive

        def unsubscribe() -> None:
            self.retirement_callback = None

        return unsubscribe

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
                profile_id=self.reported_profile_id,
                session_id=self._session_id,
                session_expires_at=self.expires_at,
                grant_state=AuthorityState.ACTIVE,
                grant_expires_at=datetime.now(UTC) + timedelta(minutes=10),
                grant_valid=self.grant_valid,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=self.scope,
                denial=None,
            ),
        )

    @override
    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        self.lock_calls += 1
        self.lock_started.set()
        if not self.lock_release.wait(5):
            raise TimeoutError("test lock was not released")
        if self.lock_refusal:
            raise RuntimeFrontendRefusedError("SESSION_LOCKED")
        return RuntimeSessionsLocked(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            session_ids=(self.session_id,) if self.lock_acknowledged else (),
        )

    @override
    def close(self) -> None:
        self.close_calls += 1

    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        self.human_calls += 1
        raise AssertionError("restricted shell must not request human inventory")

    @override
    def deny_automation(
        self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
    ) -> AutomationDenialReceipt:
        self.human_calls += 1
        raise AssertionError("restricted shell must not request administrator controls")

    @override
    def refresh_api_key(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        self.human_calls += 1
        raise AssertionError("status polling must not renew a lease")


async def _shown(app: RuntimeRestrictedSessionApp, pilot: Pilot[AccountRecomposeRequiredV1 | None]) -> None:
    async with asyncio.timeout(5):
        while not str(app.query_one("#restricted-profile", Static).render()).strip():
            await pilot.pause()
        await pilot.pause()


def _disclosure_scope(client: _Client, *, delegation: bool = True) -> None:
    client.scope = AccessScope(
        operations=client.scope.operations,
        actions=client.scope.actions,
        disclosures=frozenset(
            DisclosurePermission(
                destination_id=UUID(int=destination),
                projection_id="user-profile.view.result",
                category=category,
            )
            for destination, category in (
                (2, DisclosureCategory.TAX_VALUES),
                (1, DisclosureCategory.PROFILE_VALUES),
            )
        ),
        periods=client.scope.periods,
        allow_period_independent=client.scope.allow_period_independent,
        allow_delegation=delegation,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("delegation", [False, True])
@pytest.mark.parametrize("size", [(80, 24), (48, 24)])
async def test_status_renders_exact_disclosures_and_delegation_and_clears_on_close(
    delegation: bool, size: tuple[int, int]
) -> None:
    client = _Client()
    _disclosure_scope(client, delegation=delegation)
    app = RuntimeRestrictedSessionApp(client, profile_label="[bold]Literal profile[/bold]")
    async with app.run_test(size=size) as pilot:
        await _shown(app, pilot)
        assert "[bold]Literal profile[/bold]" in str(app.query_one("#restricted-profile", Static).render())
        expected = (
            f"{UUID(int=1)}/user-profile.view.result/profile_values, {UUID(int=2)}/user-profile.view.result/tax_values"
        )
        assert str(app.query_one("#restricted-disclosures", Static).render()) == (
            f"{tr('tui.automation_inventory.disclosures')}: {expected}"
        )
        assert str(app.query_one("#restricted-delegation", Static).render()) == (
            f"{tr('tui.automation_inventory.delegation')}: "
            f"{tr('tui.restricted.yes') if delegation else tr('tui.restricted.no')}"
        )
        assert await pilot.click("#restricted-close")
        assert str(app.query_one("#restricted-disclosures", Static).render()) == ""
        assert str(app.query_one("#restricted-delegation", Static).render()) == ""
    assert client.close_calls == 0 and client.lock_calls == 0 and client.human_calls == 0


@pytest.mark.asyncio
async def test_status_shows_exact_allowlisted_scope_without_human_calls_or_client_close() -> None:
    client = _Client()
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic API profile")
    async with app.run_test() as pilot:
        await _shown(app, pilot)
        assert str(client.profile_id) in str(app.query_one("#restricted-profile", Static).render())
        assert "user-profile.view" in str(app.query_one("#restricted-operations", Static).render())
        assert "submit" in str(app.query_one("#restricted-scope-actions", Static).render())
        assert "2025 1T" in str(app.query_one("#restricted-periods", Static).render())
        assert client.human_calls == 0
        assert await pilot.click("#restricted-close")
        assert app.return_value is None
        assert str(app.query_one("#restricted-scope-actions", Static).render()) == ""
    assert client.close_calls == 0 and client.lock_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["profile", "expiry", "binding"])
async def test_wrong_binding_or_expired_lease_clears_and_exits(invalid: str) -> None:
    client = _Client()
    if invalid == "profile":
        client.reported_profile_id = uuid4()
    elif invalid == "expiry":
        client.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic API profile")
    if invalid == "binding":
        client._session_id = uuid4()
    async with app.run_test() as pilot:
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        assert str(app.query_one("#restricted-profile", Static).render()) == ""
    assert client.close_calls == 0 and client.human_calls == 0


@pytest.mark.asyncio
async def test_periodic_status_detects_revoked_grant_and_wipes_previous_projection() -> None:
    client = _Client()
    _disclosure_scope(client)
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic API profile")
    async with app.run_test() as pilot:
        await _shown(app, pilot)
        assert "profile_values" in str(app.query_one("#restricted-disclosures", Static).render())
        assert tr("tui.restricted.yes") in str(app.query_one("#restricted-delegation", Static).render())
        assert str(app.query_one("#restricted-profile", Static).render())
        client.grant_valid = False
        app._start_status_read()
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        assert str(app.query_one("#restricted-profile", Static).render()) == ""
        assert str(app.query_one("#restricted-disclosures", Static).render()) == ""
        assert str(app.query_one("#restricted-delegation", Static).render()) == ""
        assert str(app.query_one("#restricted-operations", Static).render()) == ""
    assert client.close_calls == 0 and client.human_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("button", "reason"),
    [
        ("#restricted-lock", AccountRecomposeReasonV1.SIGNED_OUT),
        ("#restricted-change-user", AccountRecomposeReasonV1.CHANGE_USER),
    ],
)
async def test_lock_clears_private_status_before_owned_native_completion(
    button: str, reason: AccountRecomposeReasonV1
) -> None:
    client = _Client()
    _disclosure_scope(client)
    client.lock_release.clear()
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic API profile")
    async with app.run_test() as pilot:
        await _shown(app, pilot)
        assert "profile_values" in str(app.query_one("#restricted-disclosures", Static).render())
        assert tr("tui.restricted.yes") in str(app.query_one("#restricted-delegation", Static).render())
        assert await pilot.click(button)
        try:
            assert str(app.query_one("#restricted-profile", Static).render()) == ""
            assert str(app.query_one("#restricted-disclosures", Static).render()) == ""
            assert str(app.query_one("#restricted-delegation", Static).render()) == ""
            await asyncio.wait_for(asyncio.to_thread(client.lock_started.wait, 5), 5)
            assert app.return_value is None
        finally:
            client.lock_release.set()
        await asyncio.wait_for(app.workers.wait_for_complete(), 5)
        assert app.return_value == AccountRecomposeRequiredV1(reason=reason)
    assert client.lock_calls == 1 and client.close_calls == 0 and client.human_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", [False, True])
async def test_missing_lock_acknowledgement_or_refusal_requires_fresh_admission(refusal: bool) -> None:
    client = _Client()
    client.lock_acknowledged = False
    client.lock_refusal = refusal
    app = RuntimeRestrictedSessionApp(client, profile_label="Synthetic API profile")
    async with app.run_test() as pilot:
        await _shown(app, pilot)
        assert await pilot.click("#restricted-lock")
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        assert str(app.query_one("#restricted-profile", Static).render()) == ""
    assert client.close_calls == 0
