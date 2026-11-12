"""The workbench's door to the IVA balance dialog."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from .wallet import offers_iva_wallet
from .wallet_screen import ModeloIvaWalletScreen

if TYPE_CHECKING:
    from .workbench.screen import ModeloWorkbenchScreen


class WorkbenchWalletMixin:
    """Own the IVA balance journey of the modelo workbench."""

    def _offers_wallet(self: ModeloWorkbenchScreen) -> bool:
        """Whether the form served says the declaration offers the balance, and a host bound a door to read it."""
        return offers_iva_wallet(self.form) and self._wallet is not None

    def action_wallet(self: ModeloWorkbenchScreen) -> None:
        """Open the IVA balance; the key does nothing where the declaration does not offer it."""
        form, door = self.form, self._wallet
        if form is None or door is None or not self._offers_wallet():
            return
        self.app.push_screen(ModeloIvaWalletScreen(door, form=form), self._wallet_closed)

    def _wallet_closed(self: ModeloWorkbenchScreen, words: str | None) -> None:
        """Read the declaration again after a recording that was stored or may have been, then say so."""
        if words is None:
            return
        self.run_worker(partial(self._wallet_read_then_say, words), group="workbench-read", exclusive=True)

    async def _wallet_read_then_say(self: ModeloWorkbenchScreen, words: str) -> None:
        await self._read()
        self._notice(words)


__all__ = ["WorkbenchWalletMixin"]
