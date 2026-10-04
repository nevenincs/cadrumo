"""Own bank account setup states for reviewing the shipped Ledger screen.

The screen is driven through its own controls over an in-memory register that
applies each request with the application's own-account logic, so every frame
shows the masked projection the registered operation publishes. Account
numbers are synthetic published examples; nothing is written to storage.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import cast, override

from textual.events import Mount
from textual.widgets import Button, DataTable, Input, Select, Static

from cadrumo.application.ledger.own_account_operation import LedgerOwnAccountRequest
from cadrumo.domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.own_accounts import LedgerOwnAccountDoorV1, LedgerOwnAccountsScreen
from cadrumo.entrypoints.tui.ledger.tests.own_account_fixtures import (
    OWN_ACCOUNT_PROFILE_ID,
    SYNTHETIC_ES_IBAN,
    SYNTHETIC_ES_IBAN_2,
    MemoryOwnAccountDoor,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection

_SCREEN_INTERFACE = "cadrumo.entrypoints.tui.ledger.own_accounts.LedgerOwnAccountsScreen"
# A third synthetic Spanish account number with a valid mod-97 check.
_SYNTHETIC_ES_IBAN_3 = "ES6000491500051234567892"


class OwnAccountFixtureState(StrEnum):
    """The reviewable states of the own-account screen."""

    EMPTY = "empty"
    POPULATED = "populated"
    DETAIL = "detail"
    ADD_FORM = "add-form"
    EDIT_FORM = "edit-form"
    DESIGNATION = "designation"
    REMOVE_REFUSED = "remove-refused"


def _seed(door: MemoryOwnAccountDoor) -> None:
    """Two accounts: a salary account used for every charge and a savings account."""
    for label, iban, holding in (
        ("Cuenta nómina", SYNTHETIC_ES_IBAN, OwnAccountHolding.TITULAR),
        ("Ahorro compartido", SYNTHETIC_ES_IBAN_2, OwnAccountHolding.COTITULAR),
    ):
        door.apply(
            LedgerOwnAccountRequest(
                profile_id=OWN_ACCOUNT_PROFILE_ID, action="add", label=label, holding=holding, iban=iban
            )
        )
    door.apply(
        LedgerOwnAccountRequest(
            profile_id=OWN_ACCOUNT_PROFILE_ID,
            action="designate",
            own_account_id="acc-01",
            role=OwnAccountRole.CHARGE,
        )
    )


class OwnAccountCaptureHost(ScreenHostApp[None]):
    """Drive the production screen to one declared, settled review state."""

    def __init__(self, screen: LedgerOwnAccountsScreen, state: OwnAccountFixtureState) -> None:
        """Bind the production screen and the state the capture must reach."""
        super().__init__(screen)
        self.accounts_screen = screen
        self.fixture_state = state

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the
        # inherited handler a second time.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self._settle()
        await self._reach_state()

    async def _settle(self) -> None:
        """Let posted messages land, then wait for every door call they started."""
        for _ in range(5):
            await asyncio.sleep(0.01)
        await self.workers.wait_for_complete()
        await asyncio.sleep(0.01)

    async def _press(self, button_id: str) -> None:
        self.accounts_screen.query_one(f"#{button_id}", Button).press()
        await self._settle()

    async def _select(self, row: int) -> None:
        table = cast("DataTable[str]", self.accounts_screen.query_one("#ledger-own-accounts", DataTable))
        table.move_cursor(row=row)
        table.action_select_cursor()
        await self._settle()

    def _show(self, selector: str) -> None:
        self.accounts_screen.query_one(selector).scroll_visible(top=True, animate=False, immediate=True)

    async def _reach_state(self) -> None:
        screen = self.accounts_screen
        state = self.fixture_state
        if state in {OwnAccountFixtureState.EMPTY, OwnAccountFixtureState.POPULATED}:
            return
        if state is OwnAccountFixtureState.ADD_FORM:
            screen.query_one("#own-account-label", Input).value = "Cuenta de la actividad"
            screen.query_one("#own-account-iban", Input).value = _SYNTHETIC_ES_IBAN_3
            await self._press("own-account-review")
            self._show("#own-account-staged")
            return
        await self._select(1 if state is OwnAccountFixtureState.DESIGNATION else 0)
        if state is OwnAccountFixtureState.DETAIL:
            return
        if state is OwnAccountFixtureState.EDIT_FORM:
            screen.query_one("#own-account-label", Input).value = "Cuenta nómina principal"
            await self._press("own-account-review")
        elif state is OwnAccountFixtureState.DESIGNATION:
            cast("Select[str]", screen.query_one("#own-account-role", Select)).value = OwnAccountRole.REFUND.value
            screen.query_one("#own-account-modelo", Input).value = "303"
            await self._press("own-account-review-designate")
        else:
            await self._press("own-account-review-remove")
            await self._press("own-account-confirm")
        self._show("#own-account-detail")
        if not str(screen.query_one("#own-account-staged", Static).render()):
            raise RuntimeError(f"own-account capture did not stage a request for {state.value}")


def build_own_account_fixture(state: OwnAccountFixtureState) -> OwnAccountCaptureHost:
    """Open the own-account screen over a synthetic in-memory register."""
    door = MemoryOwnAccountDoor()
    if state is not OwnAccountFixtureState.EMPTY:
        _seed(door)
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            own_account_door=cast(LedgerOwnAccountDoorV1, door),
        ),
    )
    return OwnAccountCaptureHost(LedgerOwnAccountsScreen(controller, cast(LedgerOwnAccountDoorV1, door)), state)


def own_account_fixture_interfaces(_state: OwnAccountFixtureState) -> tuple[str, ...]:
    """Every state is the one own-account screen."""
    return (_SCREEN_INTERFACE,)


__all__ = [
    "OwnAccountCaptureHost",
    "OwnAccountFixtureState",
    "build_own_account_fixture",
    "own_account_fixture_interfaces",
]
