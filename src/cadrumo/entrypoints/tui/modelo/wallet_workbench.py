"""The workbench's door to the IVA balance dialog."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from textual.widgets import Button

from ..refusal.served import ServedRefusalV1
from .wallet import IvaWalletOpeningV1, offers_iva_wallet, wallet_opening
from .wallet_screen import ModeloIvaWalletScreen

if TYPE_CHECKING:
    from .workbench.screen import ModeloWorkbenchScreen

WALLET_DOOR_ID = "wb-wallet-door"
"""The id of the button a refusal's served balance door is drawn as."""


class WorkbenchWalletMixin:
    """Own the IVA balance journey of the modelo workbench."""

    def _offers_wallet(self: ModeloWorkbenchScreen) -> bool:
        """Whether the form served says the declaration offers the balance, and a host bound a door to read it."""
        return offers_iva_wallet(self.form) and self._wallet is not None

    def action_wallet(self: ModeloWorkbenchScreen) -> None:
        """Open the IVA balance; the key does nothing where the declaration does not offer it."""
        self._open_wallet(None)

    def _open_wallet(self: ModeloWorkbenchScreen, opening: IvaWalletOpeningV1 | None) -> None:
        form, door = self.form, self._wallet
        if form is None or door is None or not self._offers_wallet():
            return
        self.app.push_screen(ModeloIvaWalletScreen(door, form=form, opening=opening), self._wallet_closed)

    def _show_wallet_door(self: ModeloWorkbenchScreen, refusal: ServedRefusalV1 | None) -> None:
        """Offer the balance beneath a refusal that serves it as the way to put the refusal right, or take it away.

        The words are the refusal's own, and so is the recording and the period
        the door opens on; the balance opens only for the declaration the
        refusal names, and only where a host bound the door that reads it.
        """
        for stale in self.query(f"#{WALLET_DOOR_ID}"):
            stale.remove()
        opening = wallet_opening(refusal, self.form) if self._wallet is not None else None
        self._wallet_door = opening
        if opening is None:
            return
        after = next(iter(self.query("#wb-operation-refusal")), None)
        self.query_one("#wb-status").mount(
            Button(opening.words, id=WALLET_DOOR_ID, variant="primary"),
            after=after if after is not None else "#wb-notice",
        )

    def _take_wallet_door(self: ModeloWorkbenchScreen) -> None:
        """Open the balance as the refusal's door named it."""
        self._open_wallet(self._wallet_door)

    def _wallet_closed(self: ModeloWorkbenchScreen, words: str | None) -> None:
        """Read the declaration again after a recording that was stored or may have been, then say so."""
        if words is None:
            return
        self.run_worker(partial(self._wallet_read_then_say, words), group="workbench-read", exclusive=True)

    async def _wallet_read_then_say(self: ModeloWorkbenchScreen, words: str) -> None:
        await self._read()
        self._notice(words)


__all__ = ["WALLET_DOOR_ID", "WorkbenchWalletMixin"]
