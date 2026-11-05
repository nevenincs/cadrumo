"""Runtime login retains exact client and proof through Textual cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import get_ident
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, Checkbox, Input, Select

from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.tests.settled_click import click_when_laid_out
from cadrumo.entrypoints.tui.tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....frontend.tui.secret.runtime_login import RuntimeLoginScreen
from .....frontend.tui.secret.runtime_login_contracts import (
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
)
from .runtime_login_support import (
    HandoffOwner,
    LoginHost,
    NoReceiverLoginHost,
    RejectedDismissalScreen,
    ScriptedClient,
    UnmountNotifiedScreen,
    failed_reference_admission,
    login_choices,
    submit_stored_reference,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_unavailable_login_shows_manager_remedy_without_retrying() -> None:
    attempts = 0

    async def open_client(_profile_id: UUID) -> FrontendClient:
        nonlocal attempts
        attempts += 1
        raise RefusalError(RefusalCode.UNAVAILABLE)

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=login_choices(), open_client=open_client, accept_handoff=owner.accept)
    with override_settings(cadrumo_output_language="en"):
        async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot, workers=False)
            screen._status_refused(RefusalCode.UNAVAILABLE.value)
            status = screen.query_one("#runtime-login-status", PinnedStatusBar)
            assert "manager" in status.message and "runtime_unavailable" in status.message
            assert attempts == 0


@pytest.mark.asyncio
async def test_recovery_keeps_selected_profile_without_automatic_receipt_admission() -> None:
    attempts = 0

    async def open_client(_profile_id: UUID) -> FrontendClient:
        nonlocal attempts
        attempts += 1
        raise RefusalError(RefusalCode.UNAVAILABLE)

    owner = HandoffOwner()
    choices = login_choices()
    screen = RuntimeLoginScreen(
        choices=choices,
        preselected=choices[0].profile_id,
        auto_resume=False,
        open_client=open_client,
        accept_handoff=owner.accept,
    )
    async with LoginHost(screen).run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        assert attempts == 0
        assert screen.query_one("#runtime-login-profile", Select).value == choices[0].profile_id
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.RECEIPT
        assert await click_when_laid_out(pilot, screen.query_one("#runtime-login-submit", Button))
        await settle_until(
            pilot,
            lambda: screen._worker is not None and screen._worker.is_finished,
            "screen._worker is not None and screen._worker.is_finished",
            workers=False,
        )
        assert attempts == 1
        assert screen.is_mounted and pilot.app.is_running


@pytest.mark.asyncio
async def test_password_default_transfers_only_exact_selected_verified_client() -> None:
    choices = login_choices()
    selected = UUID(choices[1].profile_id)
    client = ScriptedClient(selected)
    opened: list[UUID] = []

    async def open_client(profile_id: UUID) -> FrontendClient:
        opened.append(profile_id)
        return client

    owner = HandoffOwner()
    proof_cleared_at_transfer: list[bool] = []

    def accept(handoff: RuntimeLoginHandoff) -> bool:
        proof_cleared_at_transfer.append(client.proof_buffer is not None and not any(client.proof_buffer))
        return owner.accept(handoff)

    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        accept_handoff=accept,
    )
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-profile", Select).value = choices[1].profile_id
        await settle(pilot, workers=False)
        assert screen.query_one("#runtime-login-method", Select).value is RuntimeLoginMethod.PASSWORD
        assert screen.query_one("#runtime-login-persist", Checkbox).value is False
        field = screen.query_one("#runtime-login-credential", Input)
        assert field.password
        field.value = "synthetic-password-proof"
        screen.action_submit()
        assert field.value == ""
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert host.handoff is not None
        assert host.handoff.profile_id == selected
        assert host.handoff.profile_label == choices[1].label
        assert host.handoff.client is client
        assert owner.accepted is host.handoff
        assert proof_cleared_at_transfer == [True]
        assert host.handoff.status.status.session_id == client.session_id
        assert "ScriptedClient" not in repr(host.handoff)
        assert opened == [selected]
        assert client.password_calls == 1 and client.api_calls == 0
        assert client.proof_before_wipe == b"synthetic-password-proof"
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_api_key_is_explicit_and_refusal_never_falls_back_to_password() -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    first = ScriptedClient(profile_id)
    first.refuse = True
    second = ScriptedClient(profile_id)
    candidates = iter((first, second))

    async def open_client(selected: UUID) -> FrontendClient:
        assert selected == profile_id
        return next(candidates)

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "old-password-candidate"
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_KEY
        await settle_until(pilot, lambda: field.value == "", "field.value == ''", workers=False)
        field.value = "synthetic-api-key-proof"
        screen.action_submit()
        await settle_until(
            pilot, lambda: first.closed and not screen._busy, "first.closed and not screen._busy", workers=False
        )
        assert first.api_calls == 1 and first.password_calls == 0
        assert first.proof_buffer is not None and not any(first.proof_buffer)
        assert host.handoff is None
        assert screen.is_mounted
        assert screen.query_one("#runtime-login-method", Select).value is RuntimeLoginMethod.API_KEY
        field.value = "fresh-api-key-proof"
        screen.action_submit()
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert second.api_calls == 1 and second.password_calls == 0
        assert host.handoff is not None and host.handoff.client is second
        assert owner.accepted is host.handoff
    second.close()


@pytest.mark.asyncio
async def test_stored_api_reference_uses_only_its_separate_opener_and_restricted_handoff() -> None:
    choices = login_choices()
    selected = UUID(choices[1].profile_id)
    reference = uuid4()
    client = ScriptedClient(selected)
    opened: list[tuple[UUID, UUID]] = []

    async def open_client(_selected: UUID) -> FrontendClient:
        raise AssertionError("stored-reference mode must not open the unadmitted proof path")

    async def open_reference(
        profile_id: UUID, credential_reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        opened.append((profile_id, credential_reference))
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        preselected=choices[1].profile_id,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        method = screen.query_one("#runtime-login-method", Select)
        proof_field = screen.query_one("#runtime-login-credential", Input)
        reference_field = screen.query_one("#runtime-login-reference", Input)
        assert not reference_field.display and proof_field.password
        proof_field.value = "discarded-password"
        method.value = RuntimeLoginMethod.API_REFERENCE
        await settle_until(
            pilot,
            lambda: reference_field.display and proof_field.value == "",
            "reference_field.display and proof_field.value == ''",
            workers=False,
        )
        assert not reference_field.password and not proof_field.display
        reference_field.value = "not-a-uuid"
        screen.action_submit()
        assert reference_field.value == "" and not opened
        reference_field.value = str(reference)
        screen.action_submit()
        assert reference_field.value == ""
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert opened == [(selected, reference)]
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.method is RuntimeLoginMethod.API_REFERENCE
        assert host.handoff.client is client and host.handoff.profile_id == selected
        assert client.status_calls == 1 and client.password_calls == client.api_calls == client.receipt_calls == 0
        assert client.proof_buffer is None and screen._pending_proof is None
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_stored_reference_refusal_does_not_open_other_proof_method() -> None:
    choices = login_choices()
    selected = UUID(choices[0].profile_id)
    attempted: list[UUID] = []

    async def open_client(_selected: UUID) -> FrontendClient:
        raise AssertionError("stored-reference refusal must not fall back")

    async def open_reference(
        profile_id: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        attempted.append(profile_id)
        raise FrontendRefusedError("credential_rejected")

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
        await submit_stored_reference(pilot, screen)
        await settle_until(
            pilot,
            lambda: len(attempted) == 1 and not screen._busy,
            "len(attempted) == 1 and not screen._busy",
            workers=False,
        )
        assert attempted == [selected]
        assert host.handoff is None and owner.accepted is None
        assert screen.is_mounted


@pytest.mark.asyncio
async def test_unmount_during_stored_reference_open_closes_after_open_settles() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_selected: UUID) -> FrontendClient:
        raise AssertionError("stored-reference opening must not use the password path")

    async def open_reference(
        _selected: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        started.set()
        await release.wait()
        return client

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
        assert not client.closed and host.handoff is None
        release.set()
        await settle_until(pilot, lambda: client.closed, "client.closed", workers=False)
        assert owner.accepted is None and client.status_calls == 0


@pytest.mark.asyncio
async def test_explicit_receipt_resume_uses_no_supplied_proof_and_transfers_exact_client() -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    client = ScriptedClient(profile_id)

    async def open_client(selected: UUID) -> FrontendClient:
        assert selected == profile_id
        return client

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    ui_thread = get_ident()
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "old-password-must-be-discarded"
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.RECEIPT
        await settle_until(
            pilot,
            lambda: field.value == "" and not field.display,
            "field.value == '' and not field.display",
            workers=False,
        )
        assert field.disabled
        field.value = "injected-value-must-not-be-read"

        screen.action_submit()
        assert field.value == ""
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)

        assert host.handoff is owner.accepted
        assert host.handoff is not None
        assert host.handoff.method is RuntimeLoginMethod.RECEIPT
        assert host.handoff.profile_id == profile_id and host.handoff.client is client
        assert client.receipt_calls == 1 and client.receipt_thread != ui_thread
        assert client.password_calls == client.api_calls == 0
        assert client.proof_buffer is None and client.proof_before_wipe is None
        assert screen._pending_proof is None
        assert not client.closed
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "receipt_refusal", (ProfileSessionRefusalReason.ABSENT, ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)
)
async def test_receipt_refusal_keeps_manual_password_available(
    receipt_refusal: ProfileSessionRefusalReason,
) -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    first = ScriptedClient(profile_id)
    first.receipt_refusal = receipt_refusal
    second = ScriptedClient(profile_id)
    candidates = iter((first, second))

    async def open_client(selected: UUID) -> FrontendClient:
        assert selected == profile_id
        return next(candidates)

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        method = screen.query_one("#runtime-login-method", Select)
        field = screen.query_one("#runtime-login-credential", Input)
        method.value = RuntimeLoginMethod.RECEIPT
        await settle_until(pilot, lambda: not field.display, "not field.display", workers=False)
        screen.action_submit()
        await settle_until(pilot, lambda: first.closed, "first.closed", workers=False)
        assert first.receipt_calls == 1 and first.password_calls == first.api_calls == 0
        assert first.proof_buffer is None
        assert host.handoff is None and screen.is_mounted
        assert method.value is RuntimeLoginMethod.RECEIPT

        method.value = RuntimeLoginMethod.PASSWORD
        await settle_until(
            pilot, lambda: field.display and not field.disabled, "field.display and not field.disabled", workers=False
        )
        field.value = "fresh-password-after-receipt-refusal"
        screen.action_submit()
        await settle_until(pilot, lambda: host.handoff is not None, "host.handoff is not None", workers=False)
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.method is RuntimeLoginMethod.PASSWORD
        assert second.password_calls == 1 and second.receipt_calls == second.api_calls == 0
        assert second.proof_buffer is not None and not any(second.proof_buffer)
        assert not second.closed
    second.close()


@pytest.mark.asyncio
async def test_unmount_during_blocked_receipt_resume_owns_call_until_close() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    client.release.clear()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner()
    screen = UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.RECEIPT
        await settle_until(
            pilot,
            lambda: not screen.query_one("#runtime-login-credential", Input).display,
            "not screen.query_one('#runtime-login-credential', Input).display",
            workers=False,
        )
        screen.action_submit()
        await settle_until(pilot, client.started.is_set, "client.started.is_set", workers=False)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), SETTLE_TIMEOUT_SECONDS)
        assert not client.closed and owner.accepted is None
        client.release.set()
        await settle_until(pilot, lambda: client.closed, "client.closed", workers=False)
        assert client.receipt_calls == 1 and client.password_calls == client.api_calls == 0
        assert client.proof_buffer is None and screen._pending_proof is None
        assert host.handoff is None


@pytest.mark.asyncio
async def test_unmount_during_blocking_login_closes_only_after_call_settles() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    client.release.clear()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner()
    screen = UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "bounded-proof"
        screen.action_submit()
        await settle_until(pilot, client.started.is_set, "client.started.is_set", workers=False)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), SETTLE_TIMEOUT_SECONDS)
        assert not client.closed
        assert host.handoff is None
        assert owner.accepted is None
        client.release.set()
        await settle_until(pilot, lambda: client.closed, "client.closed", workers=False)
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert host.handoff is None


@pytest.mark.asyncio
async def test_unmount_during_open_closes_late_acquired_client_without_proof() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))
    opening = asyncio.Event()
    release = asyncio.Event()

    async def open_client(_profile_id: UUID) -> FrontendClient:
        opening.set()
        await release.wait()
        return client

    owner = HandoffOwner()
    screen = UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-credential", Input).value = "unread-proof"
        screen.action_submit()
        await settle_until(pilot, opening.is_set, "opening.is_set", workers=False)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), SETTLE_TIMEOUT_SECONDS)
        assert not client.closed
        release.set()
        await settle_until(pilot, lambda: client.closed, "client.closed", workers=False)
        assert client.password_calls == 0 and client.api_calls == 0
        assert host.handoff is None
        assert owner.accepted is None


@pytest.mark.asyncio
async def test_wrong_profile_opener_is_closed_before_any_proof_delivery() -> None:
    choices = login_choices()
    foreign = ScriptedClient(uuid4())

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return foreign

    owner = HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "private-candidate"
        screen.action_submit()
        await settle_until(pilot, lambda: foreign.closed, "foreign.closed", workers=False)
        assert field.value == ""
        assert foreign.password_calls == 0 and foreign.api_calls == 0
        assert host.handoff is None
        assert owner.accepted is None
        assert screen.is_mounted


@pytest.mark.asyncio
async def test_accepted_handoff_survives_failed_screen_dismissal() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner()
    screen = RejectedDismissalScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = LoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        screen.query_one("#runtime-login-credential", Input).value = "one-shot-proof"
        screen.action_submit()
        await settle_until(pilot, lambda: owner.accepted is not None, "owner.accepted is not None", workers=False)
        assert host.handoff is None
        assert screen.is_mounted
        assert client.password_calls == 1
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_real_screen_stack_without_accepting_owner_closes_client() -> None:
    choices = login_choices()
    client = ScriptedClient(UUID(choices[0].profile_id))

    async def open_client(_profile_id: UUID) -> FrontendClient:
        return client

    owner = HandoffOwner(allow=False)
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = NoReceiverLoginHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await settle(pilot, workers=False)
        assert host.screen is screen
        screen.query_one("#runtime-login-credential", Input).value = "abandoned-proof"
        screen.action_submit()
        await settle_until(pilot, lambda: client.closed, "client.closed", workers=False)
        assert owner.accepted is None
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert host.screen is screen
        await host.pop_screen()


@pytest.mark.asyncio
async def test_reference_refusal_retains_failed_owner_without_closing_later_handoff() -> None:
    choices = login_choices()
    profile_id = UUID(choices[0].profile_id)
    failed = ScriptedClient(profile_id)
    failed.close_failures_remaining = 1
    admitted = ScriptedClient(profile_id)
    refusal = FrontendRefusedError("credential_rejected")
    attempts = 0

    async def open_client(_profile_id: UUID) -> FrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(
        _profile_id: UUID, _reference: UUID, _on_connected: Callable[[FrontendClient], None]
    ) -> FrontendClient:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return await failed_reference_admission(failed, refusal)
        return admitted

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
        await submit_stored_reference(pilot, screen)
        await settle_until(
            pilot, lambda: attempts == 1 and not screen._busy, "attempts == 1 and not screen._busy", workers=False
        )
        assert screen.is_mounted and host.handoff is None
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert "credential_rejected" in status.message
        assert "private-reference-close-canary" not in status.message
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert failed.close_calls == 1 and not failed.closed
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await settle_until(
            pilot,
            lambda: host.handoff is not None and failed.closed,
            "host.handoff is not None and failed.closed",
            workers=False,
        )
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.client is admitted
        assert failed.close_calls == 2
        assert admitted.close_calls == 0
    assert failed.close_calls == 2
    assert admitted.close_calls == 0
    admitted.close()
