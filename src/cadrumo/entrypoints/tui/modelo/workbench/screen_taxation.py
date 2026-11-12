"""The comparison of joint and individual filing, offered from the workbench where the form serves it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..taxation_comparison import (
    ModeloTaxationComparerV1,
    ModeloTaxationComparisonScreen,
    offers_taxation_comparison,
)

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchTaxationMixin:
    """Own the taxation comparison offer of the modelo workbench."""

    def _offers_taxation_comparison(self: ModeloWorkbenchScreen) -> bool:
        """Whether the form served says the comparison can be asked, and these actions can ask it."""
        return offers_taxation_comparison(self.form) and isinstance(self._actions, ModeloTaxationComparerV1)

    def action_compare_taxation(self: ModeloWorkbenchScreen) -> None:
        """Open the comparison of joint and individual filing; the key does nothing where it is not offered."""
        actions = self._actions
        form = self.form
        if form is None or not self._offers_taxation_comparison() or not isinstance(actions, ModeloTaxationComparerV1):
            return
        self.app.push_screen(ModeloTaxationComparisonScreen(actions.compare_taxation, form=form), self._taxation_closed)

    def _taxation_closed(self: ModeloWorkbenchScreen, casilla_id: str | None) -> None:
        """Return to the box the filer chose from a refusal's list."""
        if casilla_id is not None:
            self._go_to(("casilla", casilla_id))


__all__ = ["WorkbenchTaxationMixin"]
