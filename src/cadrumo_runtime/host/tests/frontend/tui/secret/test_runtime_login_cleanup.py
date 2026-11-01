"""Runtime login resume, persistence and failed-close cleanup keep their primary outcome."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import get_ident
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, Checkbox, Input, Select

from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....frontend.tui.secret.runtime_login import RuntimeLoginScreen
from .....frontend.tui.secret.runtime_login_contracts import (
    RuntimeLoginMethod,
)
from ._runtime_login_support import (
    HandoffOwner,
    LoginHost,
    NoReceiverLoginHost,
    ScriptedClient,
    ScriptedRecoveryClient,
    UnmountNotifiedScreen,
    failed_reference_admission,
    login_choices,
    submit_stored_reference,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_repeated_cancellation_of_failed_reference_open_preserves_cleanup_and_primary() -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    failed = ScriptedClient(profile_id)
    failed.close_failures_remaining = 1
    refusal = FrontendRefusedError("credential_rejected")
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(
        _profile_id: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        started.set()
        await release.wait()
        return await failed_reference_admission(failed, refusal)

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        task = asyncio.create_task(
            screen._attempt(profile_id, choices[0].label, RuntimeLoginMethod.API_REFERENCE, None, uuid4())
        )
        await asyncio.wait_for(started.wait(), SETTLE_TIMEOUT_SECONDS)
        task.cancel()
        task.cancel()
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.__dict__.get("cleanup_error") is refusal
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert failed.close_calls == 1 and not failed.closed
        assert host.handoff is None and owner.accepted is None
    assert failed.closed and failed.close_calls == 2


@pytest.mark.asyncio
async def test_unmount_during_failed_reference_open_drains_then_retries_cleanup() -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    failed = ScriptedClient(profile_id)
    failed.close_failures_remaining = 1
    refusal = FrontendRefusedError("credential_rejected")
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(
        _profile_id: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        started.set()
        await release.wait()
        return await failed_reference_admission(failed, refusal)

    owner = HandoffOwner()
    screen = UnmountNotifiedScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        await submit_stored_reference(pilot, screen)
        await asyncio.wait_for(started.wait(), SETTLE_TIMEOUT_SECONDS)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), SETTLE_TIMEOUT_SECONDS)
        assert failed.close_calls == 0
        release.set()
        await settle_until(pilot, lambda: failed.closed, "failed.closed", workers=False)
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert host.handoff is None and owner.accepted is None
    assert failed.close_calls == 2


@pytest.mark.asyncio
async def test_returned_reference_status_refusal_keeps_primary_and_retries_failed_close() -> None:
    refusal = FrontendRefusedError("credential_rejected")

    class RefusingStatusClient(ScriptedClient):
        @override
        def status(self, *, timeout: float = 5) -> ProfileStatus:
            self.status_calls += 1
            raise refusal

    choices = login_choices()
    client = RefusingStatusClient(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> FrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(
        _profile_id: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        await submit_stored_reference(pilot, screen)
        await settle_until(
            pilot,
            lambda: client.close_calls == 1 and not screen._busy,
            "client.close_calls == 1 and not screen._busy",
            workers=False,
        )
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert "credential_rejected" in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        assert client.status_calls == 1 and not client.closed
        assert owner.accepted is None
        assert screen.is_mounted
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
async def test_denied_handoff_failed_close_remains_owned_until_unmount_retry() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner(allow=False)
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-denied-handoff-proof")
    async with NoReceiverLoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        with pytest.raises(AsyncResourceCleanupError):
            await screen._attempt(client.profile_id, choices[0].label, RuntimeLoginMethod.PASSWORD, proof, None)
        assert not any(proof)
        assert owner.accepted is None
        assert client.close_calls == 1 and not client.closed
        assert not screen._busy
        assert (
            "private-reference-close-canary" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        )
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
async def test_cancelled_returned_candidate_failed_close_preserves_cancellation_and_retry() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1
    client.release.clear()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-cancelled-candidate-proof")
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        task = asyncio.create_task(
            screen._attempt(client.profile_id, choices[0].label, RuntimeLoginMethod.PASSWORD, proof, None)
        )
        await settle_until(pilot, client.started.is_set, "client.started.is_set", workers=False)
        task.cancel()
        task.cancel()
        assert not task.done() and client.close_calls == 0
        client.release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert isinstance(caught.value.__dict__.get("cleanup_error"), AsyncResourceCleanupError)
        assert not any(proof)
        assert client.close_calls == 1 and not client.closed
        assert owner.accepted is None
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("select_grants", [False, True], ids=["human_only", "selected_grants"])
async def test_cold_profile_resume_stays_unadmitted_and_next_login_uses_fresh_client(select_grants: bool) -> None:
    choices = login_choices()
    profile_id = UUID(choices[1].profile_id)
    recovery = ScriptedRecoveryClient(profile_id)
    login = ScriptedClient(profile_id)
    selected = frozenset({uuid4(), uuid4()}) if select_grants else frozenset[UUID]()
    opened: list[UUID] = []

    async def open_client(selected_profile: UUID) -> FrontendClient:
        opened.append(selected_profile)
        return recovery if len(opened) == 1 else login

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    ui_thread = get_ident()
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-profile", Select).value = choices[1].profile_id
        await settle(pilot, workers=False)
        password = screen.query_one("#runtime-login-resume-password", Input)
        assert password.password
        password.value = "synthetic-recovery-proof"
        screen.query_one("#runtime-login-resume-grants", Input).value = ", ".join(map(str, selected))
        screen.query_one("#runtime-login-resume", Button).press()
        await settle_until(
            pilot, lambda: recovery.closed and not screen._busy, "recovery.closed and not screen._busy", workers=False
        )
        assert password.value == ""
        assert recovery.resume_calls == 1 and recovery.grants_seen == selected
        assert recovery._session_id is None
        assert recovery.password_calls == recovery.api_calls == recovery.receipt_calls == recovery.status_calls == 0
        assert recovery.recovery_thread != ui_thread and all(thread != ui_thread for thread in recovery.close_threads)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert screen.query_one("#runtime-login-resume-grants", Input).value == ""
        assert host.screen is screen and host.handoff is None and owner.accepted is None
        assert "synthetic-recovery-proof" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        screen.query_one("#runtime-login-credential", Input).value = "separate-login-proof"
        screen.action_submit()
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert opened == [profile_id, profile_id]
        assert recovery.close_calls == 1 and login.close_calls == 0
        assert login.password_calls == 1 and login.proof_before_wipe == b"separate-login-proof"
        assert host.handoff is not None and host.handoff.client is login
    assert recovery.close_calls == 1
    login.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["not-a-uuid", "duplicate", "trailing_separator"])
async def test_invalid_resume_grants_clear_proof_before_any_native_connection(selection: str) -> None:
    choices = login_choices()
    opened = 0

    async def open_client(_profile_id: UUID) -> FrontendClient:
        nonlocal opened
        opened += 1
        raise AssertionError("invalid consent must not open native recovery")

    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=HandoffOwner().accept)
    identity = uuid4()
    raw = (
        f"{identity},{identity}"
        if selection == "duplicate"
        else f"{identity},"
        if selection == "trailing_separator"
        else selection
    )
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-resume-password", Input).value = "private-invalid-consent-proof"
        screen.query_one("#runtime-login-resume-grants", Input).value = raw
        screen.action_resume()
        assert opened == 0
        assert screen.query_one("#runtime-login-resume-password", Input).value == ""
        assert screen.query_one("#runtime-login-resume-grants", Input).value == ""
        assert not screen._busy and screen.is_mounted
        assert "private-invalid-consent-proof" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["unsupported", "credential_rejected"])
async def test_resume_typed_refusal_preserves_failed_close_for_unmount_retry(code: str) -> None:
    choices = login_choices()
    recovery = ScriptedRecoveryClient(UUID(choices[0].profile_id))
    refusal = FrontendRefusedError(code)
    recovery.recovery_failure = refusal
    recovery.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return recovery

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-resume-password", Input).value = "private-refused-recovery-proof"
        screen.action_resume()
        await settle_until(
            pilot,
            lambda: recovery.close_calls == 1 and not screen._busy,
            "recovery.close_calls == 1 and not screen._busy",
            workers=False,
        )
        assert recovery.resume_calls == 1 and not recovery.closed
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert code in status.message
        assert (
            "private-refused-recovery-proof" not in status.message
            and "private-reference-close-canary" not in status.message
        )
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert not screen.query_one("#runtime-login-resume", Button).disabled
        assert owner.accepted is None
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_resume_timeout_fences_mutation_replay_while_separate_login_remains_available() -> None:
    choices = login_choices()
    recovery = ScriptedRecoveryClient(UUID(choices[0].profile_id))
    recovery.recovery_failure = RefusalError(RefusalCode.TIMEOUT)
    opened = 0

    async def open_client(_profile_id: UUID) -> FrontendClient:
        nonlocal opened
        opened += 1
        return recovery

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-resume-password", Input).value = "private-timeout-proof"
        screen.action_resume()
        await settle_until(
            pilot, lambda: recovery.closed and not screen._busy, "recovery.closed and not screen._busy", workers=False
        )
        assert "runtime_timeout" in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        assert screen.query_one("#runtime-login-resume", Button).disabled
        assert not screen.query_one("#runtime-login-submit", Button).disabled
        screen.query_one("#runtime-login-resume-password", Input).value = "private-blind-replay-proof"
        screen.action_resume()
        assert recovery.resume_calls == 1 and opened == 1
        assert screen.query_one("#runtime-login-resume-password", Input).value == ""
        assert owner.accepted is None and screen.is_mounted
    assert recovery.close_calls == 1


@pytest.mark.asyncio
async def test_successful_resume_failed_close_keeps_outcome_and_retries_only_cleanup() -> None:
    choices = login_choices()
    recovery = ScriptedRecoveryClient(UUID(choices[0].profile_id))
    recovery.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return recovery

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-resume-password", Input).value = "synthetic-completed-recovery-proof"
        screen.action_resume()
        await settle_until(
            pilot,
            lambda: recovery.close_calls == 1 and not screen._busy,
            "recovery.close_calls == 1 and not screen._busy",
            workers=False,
        )
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert status.tone == "warning" and "runtime_unavailable" in status.message
        assert "private-reference-close-canary" not in status.message
        assert recovery.resume_calls == 1 and not recovery.closed
        assert owner.accepted is None and screen.is_mounted
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_cancelled_resume_keeps_body_refusal_and_failed_close_until_unmount_retry() -> None:
    choices = login_choices()
    recovery = ScriptedRecoveryClient(UUID(choices[0].profile_id))
    refusal = FrontendRefusedError("credential_rejected")
    recovery.recovery_failure = refusal
    recovery.close_failures_remaining = 1
    recovery.release.clear()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return recovery

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-cancelled-recovery-proof")
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        task = asyncio.create_task(screen._resume_attempt(recovery.profile_id, proof, frozenset()))
        await settle_until(pilot, recovery.started.is_set, "recovery.started.is_set", workers=False)
        task.cancel()
        task.cancel()
        assert not task.done() and recovery.close_calls == 0
        recovery.release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.__dict__.get("body_error") is refusal
        assert isinstance(caught.value.__dict__.get("cleanup_error"), AsyncResourceCleanupError)
        assert not any(proof) and recovery.close_calls == 1 and not recovery.closed
        assert owner.accepted is None
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_unmount_during_resume_drains_native_call_before_failed_close_retry() -> None:
    choices = login_choices()
    recovery = ScriptedRecoveryClient(UUID(choices[0].profile_id))
    recovery.close_failures_remaining = 1
    recovery.release.clear()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return recovery

    owner = HandoffOwner()
    screen = UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-resume-password", Input).value = "private-unmount-recovery-proof"
        screen.action_resume()
        await settle_until(pilot, recovery.started.is_set, "recovery.started.is_set", workers=False)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), SETTLE_TIMEOUT_SECONDS)
        assert recovery.close_calls == 0
        recovery.release.set()
        await settle_until(pilot, lambda: recovery.closed, "recovery.closed", workers=False)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert owner.accepted is None
    assert recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("persist", [False, True])
async def test_password_persistence_is_explicit_and_frozen_at_submission(persist: bool) -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))

    async def open_client(profile_id: UUID) -> FrontendClient:
        assert profile_id == client.profile_id
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        checkbox = screen.query_one("#runtime-login-persist", Checkbox)
        assert checkbox.display and not checkbox.disabled and not checkbox.value
        checkbox.value = persist
        screen.query_one("#runtime-login-credential", Input).value = "synthetic-password-proof"
        screen.action_submit()
        assert checkbox.disabled
        checkbox.value = not persist  # A programmatic UI change cannot alter the captured request.
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert client.persistence_requests == [persist]
        assert client.api_calls == client.receipt_calls == 0
        assert host.handoff is owner.accepted
    client.close()


@pytest.mark.asyncio
async def test_persistence_choice_is_cleared_on_profile_and_proof_changes() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[1].profile_id))

    async def open_client(profile_id: UUID) -> FrontendClient:
        assert profile_id == client.profile_id
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        checkbox = screen.query_one("#runtime-login-persist", Checkbox)
        checkbox.value = True
        screen.query_one("#runtime-login-profile", Select).value = choices[1].profile_id
        await settle(pilot, workers=False)
        assert not checkbox.value
        method = screen.query_one("#runtime-login-method", Select)
        for target in (RuntimeLoginMethod.RECEIPT, RuntimeLoginMethod.API_KEY):
            checkbox.value = True
            method.value = target
            await settle(pilot, workers=False)
            assert not checkbox.value and not checkbox.display and checkbox.disabled
            method.value = RuntimeLoginMethod.PASSWORD
            await settle(pilot, workers=False)
            assert not checkbox.value and checkbox.display and not checkbox.disabled
        method.value = RuntimeLoginMethod.API_KEY
        await settle(pilot, workers=False)
        checkbox.value = True  # Hidden controls cannot request password persistence for an API grant.
        screen.query_one("#runtime-login-credential", Input).value = "synthetic-api-proof"
        screen.action_submit()
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert client.api_calls == 1 and client.persistence_requests == []
    client.close()
