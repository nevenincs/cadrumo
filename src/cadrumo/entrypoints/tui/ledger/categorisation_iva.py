"""Derive the IVA of the selected entry from the IVA category the operator chooses.

The operation resolves the category against the pinned authority, derives the
rate, base and amount it implies, and writes them in the same step; it has no
preview. The screen therefore reviews the request itself, the entry and the
chosen category, and shows the derived values as the result reports them.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import override

from textual.widget import Widget
from textual.widgets import Input, Static

from ....application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from ....core.i18n.render import tr
from .categorisation_common import CategorisationScreen, StagedChangeV1, action, action_row, field, heading, line
from .categorisation_doors import LedgerOperatorIvaDoorV1
from .controller import LedgerWorkspaceController


def derived_iva_text(result: LedgerOperatorIvaResult) -> str:
    """Say what the derivation concluded, including when it could not derive."""
    if result.outcome == "validation_error":
        return tr("tui.ledger.categorisation.iva.refused", messages="; ".join(result.validation_messages))
    if not result.derivable:
        return tr("tui.ledger.categorisation.iva.not_derivable", category=result.iva_category, note=result.note or "-")
    return tr(
        "tui.ledger.categorisation.iva.derived",
        category=result.iva_category,
        rate=result.iva_rate or "-",
        base=result.taxable_base or "-",
        amount=result.iva_amount or "-",
        note=result.note or "-",
    )


class LedgerIvaDeriveScreen(CategorisationScreen):
    """Choose an IVA category for the selected entry and record what it derives."""

    ENTRY_SCOPED = True

    @override
    def banner(self) -> Static:
        return line("tui.ledger.categorisation.iva.title", classes="cadrumo-banner")

    @override
    def prompt(self) -> Static:
        return line("tui.ledger.categorisation.iva.prompt")

    def __init__(self, controller: LedgerWorkspaceController, *, door: LedgerOperatorIvaDoorV1) -> None:
        """Keep the profile-bound IVA derivation door."""
        super().__init__(controller, id="ledger-categorisation-iva-screen")
        self.door = door

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.iva.heading")
        yield field("tui.ledger.categorisation.iva.category", id="categorisation-iva-category", max_length=128)
        yield action_row(action("tui.ledger.categorisation.iva.review", id="categorisation-iva-review"))

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return ("#categorisation-iva-category", "#categorisation-iva-review")

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-iva-review":
            self.stage_from(self._stage)

    def _stage(self) -> StagedChangeV1:
        category = self.query_one("#categorisation-iva-category", Input).value.strip()
        if not category:
            raise ValueError(tr("tui.ledger.categorisation.iva.category_required"))
        request = LedgerOperatorIvaRequest(
            profile_id=self.door.profile_id, transaction_id=self.target, iva_category=category
        )

        async def write() -> bool:
            result = await self.door(request)
            self.show_outcome(lambda: derived_iva_text(result))
            return result.outcome == "derived" and result.derivable

        return StagedChangeV1(
            summary=lambda: tr("tui.ledger.categorisation.iva.stage", category=request.iva_category),
            write=write,
            refreshes_workspace=True,
        )


__all__ = ["LedgerIvaDeriveScreen", "derived_iva_text"]
