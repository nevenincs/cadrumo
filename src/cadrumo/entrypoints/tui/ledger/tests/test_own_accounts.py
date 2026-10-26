"""Mounted own bank account setup over the real own-account request and register projections.

The door applies each request with the application's own
``apply_own_account_request`` against an in-memory register, so the screen is
driven by the same request validation and masked projection the registered
operation publishes. Account numbers are synthetic published examples.
"""

from __future__ import annotations

import asyncio
from typing import cast, override

import pytest
from pydantic import ValidationError
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.ledger.own_account_operation import LedgerOwnAccountRequest, LedgerOwnAccountResult
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.operations import OperationEffect
from ...account import AccountSessionExpiredError
from ...operations.outcome import OperationOutcomeUnknownError
from ...tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from ..controller import LedgerWorkspaceController
from ..overview import LedgerOverviewScreen
from ..own_accounts import LedgerOwnAccountDoorV1, LedgerOwnAccountsScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .own_account_fixtures import (
    OWN_ACCOUNT_REFUSAL_KEY,
    SYNTHETIC_ES_IBAN,
    SYNTHETIC_ES_IBAN_2,
    MemoryOwnAccountDoor,
)
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_SECRETS = (SYNTHETIC_ES_IBAN, SYNTHETIC_ES_IBAN[4:-4], SYNTHETIC_ES_IBAN_2, SYNTHETIC_ES_IBAN_2[4:-4])


def _screen(door: MemoryOwnAccountDoor) -> LedgerOwnAccountsScreen:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            own_account_door=cast(LedgerOwnAccountDoorV1, door),
        ),
    )
    return LedgerOwnAccountsScreen(controller, cast(LedgerOwnAccountDoorV1, door))


def _rendered(screen: LedgerOwnAccountsScreen) -> str:
    """Every visible text and table cell, which must never hold account material."""
    texts = [str(widget.render()) for widget in screen.query(Static)]
    table = screen.query_one("#ledger-own-accounts", DataTable)
    texts.extend(str(cell) for row in range(table.row_count) for cell in table.get_row_at(row))
    return "\n".join(texts)


def _assert_masked(screen: LedgerOwnAccountsScreen) -> None:
    rendered = _rendered(screen)
    for secret in _SECRETS:
        assert secret not in rendered


async def _press(pilot: Pilot[None], screen: LedgerOwnAccountsScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


async def _review_and_confirm(pilot: Pilot[None], screen: LedgerOwnAccountsScreen, review_id: str) -> None:
    await _press(pilot, screen, review_id)
    assert screen.staged is not None, str(screen.query_one("#ledger-refusal", Static).render())
    _assert_masked(screen)
    await _press(pilot, screen, "own-account-confirm")


async def _select_row(pilot: Pilot[None], screen: LedgerOwnAccountsScreen, row: int) -> None:
    table = screen.query_one("#ledger-own-accounts", DataTable)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


async def _add(pilot: Pilot[None], screen: LedgerOwnAccountsScreen, label: str, iban: str) -> None:
    await _press(pilot, screen, "own-account-new")
    screen.query_one("#own-account-label", Input).value = label
    screen.query_one("#own-account-iban", Input).value = iban
    await _review_and_confirm(pilot, screen, "own-account-review")


@pytest.mark.asyncio
async def test_own_account_setup_adds_edits_designates_and_closes_masked() -> None:
    door = MemoryOwnAccountDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            table = screen.query_one("#ledger-own-accounts", DataTable)
            assert table.row_count == 0
            assert str(screen.query_one("#ledger-flow-status", Static).render()) == tr("tui.ledger.own_accounts.empty")

            await _add(pilot, screen, "main", SYNTHETIC_ES_IBAN)
            assert screen.query_one("#own-account-iban", Input).value == ""
            assert door.requests[-2].action == "add"
            assert door.requests[-2].iban == SYNTHETIC_ES_IBAN
            assert table.row_count == 1
            assert table.get_row_at(0)[:3] == ["acc-01", "main", "ES ···· 1332"]

            await _add(pilot, screen, "savings", SYNTHETIC_ES_IBAN_2)
            assert table.row_count == 2

            await _select_row(pilot, screen, 0)
            assert screen.selected_id == "acc-01"
            assert door.requests[-1].action == "show"
            assert "acc-01 · main · ES ···· 1332" in str(screen.query_one("#own-account-detail", Static).render())
            assert screen.query_one("#own-account-label", Input).value == "main"
            assert screen.query_one("#own-account-iban", Input).value == ""

            screen.query_one("#own-account-label", Input).value = "renamed"
            await _press(pilot, screen, "own-account-review")
            staged = str(screen.query_one("#own-account-staged", Static).render())
            assert "renamed" in staged
            assert "ES ···· 1332" in staged
            await _press(pilot, screen, "own-account-confirm")
            update = next(request for request in reversed(door.requests) if request.action == "update")
            assert update.own_account_id == "acc-01"
            assert update.label == "renamed"
            assert update.iban is None
            assert table.get_row_at(0)[1] == "renamed"

            await _review_and_confirm(pilot, screen, "own-account-review-designate")
            assert door.repository.register.designations[0].own_account_id == "acc-01"
            await _select_row(pilot, screen, 1)
            cast("Select[str]", screen.query_one("#own-account-role", Select)).value = "refund"
            screen.query_one("#own-account-modelo", Input).value = "303"
            await _review_and_confirm(pilot, screen, "own-account-review-designate")
            roles = str(table.get_row_at(1)[4])
            assert tr("tui.ledger.own_accounts.role.refund") in roles
            assert tr("tui.ledger.own_accounts.scope.modelo", modelo="303") in roles
            assert tr("tui.ledger.own_accounts.role.refund") in str(
                screen.query_one("#own-account-detail", Static).render()
            )

            await _review_and_confirm(pilot, screen, "own-account-review-undesignate")
            assert [item.own_account_id for item in door.repository.register.designations] == ["acc-01"]

            screen.query_one("#own-account-closed-on", Input).value = "2026-06-30"
            await _review_and_confirm(pilot, screen, "own-account-review-close")
            assert str(table.get_row_at(1)[5]) == tr("tui.ledger.own_accounts.state.closed", date="2026-06-30")
            _assert_masked(screen)


@pytest.mark.asyncio
async def test_own_account_review_refuses_an_invalid_iban_before_anything_is_sent() -> None:
    door = MemoryOwnAccountDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen.query_one("#own-account-label", Input).value = "broken"
            screen.query_one("#own-account-iban", Input).value = SYNTHETIC_ES_IBAN[:-1] + "3"
            await _press(pilot, screen, "own-account-review")
            assert screen.staged is None
            assert str(screen.query_one("#ledger-refusal", Static).render())
            assert [request.action for request in door.requests] == ["list"]
            assert screen.query_one("#own-account-confirm", Button).disabled
            assert not screen.query_one("#own-account-decision").display
            _assert_masked(screen)


@pytest.mark.asyncio
async def test_own_account_removal_shows_the_typed_refusal_and_keeps_the_account() -> None:
    door = MemoryOwnAccountDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _add(pilot, screen, "main", SYNTHETIC_ES_IBAN)
            await _select_row(pilot, screen, 0)
            await _review_and_confirm(pilot, screen, "own-account-review-remove")
            assert door.requests[-1].action == "remove"
            assert str(screen.query_one("#ledger-refusal", Static).render()) == tr(OWN_ACCOUNT_REFUSAL_KEY)
            assert screen.query_one("#ledger-own-accounts", DataTable).row_count == 1
            # The reviewed request stays staged so the operator can cancel it or retry.
            assert screen.staged is not None
            await _press(pilot, screen, "own-account-cancel")
            assert screen.staged is None


@pytest.mark.asyncio
async def test_own_account_screen_discards_account_facts_when_the_session_is_lost() -> None:
    door = MemoryOwnAccountDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _add(pilot, screen, "main", SYNTHETIC_ES_IBAN)
            await _select_row(pilot, screen, 0)
            door.expired = True
            screen.query_one("#own-account-iban", Input).value = SYNTHETIC_ES_IBAN_2
            await _review_and_confirm(pilot, screen, "own-account-review")
            assert screen.accounts == ()
            assert screen.selected_id is None
            assert screen.query_one("#ledger-own-accounts", DataTable).row_count == 0
            assert screen.query_one("#own-account-iban", Input).value == ""
            assert str(screen.query_one("#own-account-detail", Static).render()) == ""


class _RereadRefusedDoor(MemoryOwnAccountDoor):
    """Applies every write, then refuses the register reads that follow it."""

    def __init__(self, reread_error: CadrumoError) -> None:
        super().__init__()
        self.reread_error = reread_error
        self.written = False

    @override
    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        if request.action == "list" and self.written:
            self.requests.append(request)
            raise self.reread_error
        result = await super().__call__(request)
        self.written = self.written or request.action != "list"
        return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reread_error",
    [RefusalError(RefusalCode.DRAINING), AccountSessionExpiredError()],
    ids=["refused", "session-lost"],
)
async def test_a_saved_change_whose_register_reread_fails_is_said_to_be_saved(reread_error: CadrumoError) -> None:
    door = _RereadRefusedDoor(reread_error)
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _add(pilot, screen, "main", SYNTHETIC_ES_IBAN)
            await settle_until(
                pilot, lambda: len(door.requests) >= 3 and not screen.in_flight, "the add and the read after it"
            )

            assert [request.action for request in door.requests] == ["list", "add", "list"]
            assert len(door.repository.register.accounts) == 1
            # The add returned, so it is saved; only the read after it failed.
            assert str(screen.query_one("#ledger-flow-status", Static).render()) == tr("tui.ledger.flow.refresh_failed")
            assert str(screen.query_one("#ledger-refusal", Static).render()) == resolve_error_message(reread_error)
            assert tr("tui.ledger.records.failed") not in _rendered(screen)
            # Nothing stays staged to be confirmed a second time.
            assert screen.staged is None
            assert screen.query_one("#own-account-confirm", Button).disabled
            assert not screen.query_one("#own-account-decision").display
            assert not screen.in_flight
            _assert_masked(screen)


_UNKNOWN = OperationOutcomeUnknownError(operation_id="e" * 64, effect=OperationEffect.UNKNOWN)


class _UnknownWriteDoor(MemoryOwnAccountDoor):
    """Applies each write but loses its outcome, then holds the register read that follows until released."""

    def __init__(self) -> None:
        super().__init__()
        self.written = False
        self.reread_started = asyncio.Event()
        self.reread_release = asyncio.Event()

    @override
    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        if request.action == "list" and self.written:
            self.reread_started.set()
            await self.reread_release.wait()
        result = await super().__call__(request)
        if request.action != "list":
            self.written = True
            raise _UNKNOWN
        return result


@pytest.mark.asyncio
async def test_an_own_account_write_with_an_unknown_outcome_drops_its_secrets_and_rereads_the_register() -> None:
    door = _UnknownWriteDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _press(pilot, screen, "own-account-new")
            screen.query_one("#own-account-label", Input).value = "main"
            screen.query_one("#own-account-iban", Input).value = SYNTHETIC_ES_IBAN
            await _press(pilot, screen, "own-account-review")
            assert screen.staged is not None
            screen.query_one("#own-account-confirm", Button).press()
            await asyncio.wait_for(door.reread_started.wait(), SETTLE_TIMEOUT_SECONDS)

            # The add may have landed: its account number is gone, and nothing is offered over the old register.
            assert screen.query_one("#own-account-iban", Input).value == ""
            assert screen.staged is None
            assert screen.in_flight
            assert screen.accounts == ()
            screen.query_one("#own-account-review", Button).press()
            await settle(pilot, workers=False)
            assert screen.staged is None
            assert str(screen.query_one("#ledger-flow-status", Static).render()) == tr(
                "tui.ledger.flow.in_flight_refusal"
            )

            door.reread_release.set()
            await settle(pilot)
            assert [request.action for request in door.requests] == ["list", "add", "list"]
            assert len(screen.accounts) == 1
            assert not screen.in_flight
            assert str(screen.query_one("#ledger-flow-status", Static).render()) == tr(
                "tui.ledger.flow.outcome_unknown"
            )
            assert str(screen.query_one("#ledger-refusal", Static).render()) == resolve_error_message(_UNKNOWN)
            assert not screen.query_one("#own-account-decision").display
            _assert_masked(screen)


class _ContractBreakingDoor(MemoryOwnAccountDoor):
    """Answers every write with a result that breaks the operation's own contract."""

    @override
    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        if request.action == "list":
            return await super().__call__(request)
        self.requests.append(request)
        return LedgerOwnAccountResult.model_validate({})


@pytest.mark.asyncio
async def test_an_own_account_write_that_fails_unexpectedly_does_not_stay_in_flight() -> None:
    door = _ContractBreakingDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _press(pilot, screen, "own-account-new")
            screen.query_one("#own-account-label", Input).value = "main"
            screen.query_one("#own-account-iban", Input).value = SYNTHETIC_ES_IBAN
            await _press(pilot, screen, "own-account-review")
            staged = screen.staged
            assert staged is not None
            # The worker the confirm button starts, run here so its failure is observed rather than ending the app.
            screen._busy = True
            with pytest.raises(ValidationError):
                await screen._submit(staged)
            assert not screen.in_flight


@pytest.mark.asyncio
async def test_ledger_overview_opens_own_account_setup_when_its_door_is_injected() -> None:
    door = MemoryOwnAccountDoor()
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            own_account_door=cast(LedgerOwnAccountDoorV1, door),
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(LedgerOverviewScreen(controller)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            pilot.app.screen.query_one("#ledger-own-accounts-open", Button).press()
            await settle(pilot)
            assert isinstance(pilot.app.screen, LedgerOwnAccountsScreen)
            assert door.requests[0].action == "list"
