"""Mounted own bank account setup over the real own-account request and register projections.

The door applies each request with the application's own
``apply_own_account_request`` against an in-memory register, so the screen is
driven by the same request validation and masked projection the registered
operation publishes. Account numbers are synthetic published examples.
"""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....core.config import override_settings
from .....core.i18n.render import tr
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
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

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
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


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
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await pilot.app.workers.wait_for_complete()
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await pilot.app.workers.wait_for_complete()
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
        async with _WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await pilot.app.workers.wait_for_complete()
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
        async with _WorkspaceHostApp(LedgerOverviewScreen(controller)).run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            pilot.app.screen.query_one("#ledger-own-accounts-open", Button).press()
            await pilot.pause()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(pilot.app.screen, LedgerOwnAccountsScreen)
            assert door.requests[0].action == "list"
