"""The ``modelo.workspace.filing`` read destination.

The narrowest destination in the cohort, and deliberately so. What the
Workspace contract carries about filing is one capability row and its
producer attribution -- nothing else. Canonical filing state and filing
history are not projected, and there is no filing-record or work-unit
history contributor among the production ports, so this screen has no
honest way to show them.

``FILING_DRAFT_READINESS`` is permanently unmeasured. ``build_draft`` is
pure and stateless -- it persists nothing, emits no event and stamps no
revision field -- so there is no producer whose verdict could be read, and
calling it to see whether it raises would be the derivation the contract
forbids. That is a structural fact about the filing architecture, not a
wiring gap awaiting a fix.

NO REMOTE SUBMISSION, and none is offered. Filing happens outside this
application by a human; this destination reports what is known and names
the handoff.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
)
from .....core.i18n.render import tr
from ...components.app_access import TypedAppAccess
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll
from .controller import ModeloWorkspaceReadSession
from .models import capability_row

_FILING_CAPABILITIES: tuple[ModeloWorkspaceCapabilityName, ...] = (
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS,
)
_COLUMN_KEYS: tuple[str, ...] = ("capability", "disposition", "producer", "why")

_WHY_KEYS: dict[ModeloWorkspaceCapabilityName, str] = {
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "why.draft_structural",
}


def _filing_capabilities(session: ModeloWorkspaceReadSession) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Select this destination's filing capability from the closed denominator."""
    wanted = set(_FILING_CAPABILITIES)
    return tuple(capability for capability in session.projection.capabilities if capability.capability in wanted)


class ModeloWorkspaceFilingScreen(TypedAppAccess, Screen[None]):
    """The filing capability beside the reason it reads as it does."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_filing", ""),
        Binding("escape", "quit_filing", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination reports on."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-filing-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-filing-body", classes="cadrumo-scroll"):
            yield Static(id="workspace-filing-state-not-carried")
            yield Static(id="workspace-filing-handoff")

    def on_mount(self) -> None:
        """Populate the header, capability table, and filing disclosures."""
        self.query_one("#workspace-filing-header", Static).update(
            tr("flows.modelo_workspace_filing.title", modelo=self._session.projection.target.modelo)
        )
        self._mount_capabilities()
        self.query_one("#workspace-filing-state-not-carried", Static).update(
            tr("flows.modelo_workspace_filing.state_not_carried")
        )
        self.query_one("#workspace-filing-handoff", Static).update(tr("flows.modelo_workspace_filing.handoff"))

    def _mount_capabilities(self) -> None:
        """Mount the filing capability beside the reason it reads as it does.

        The ``why`` column is keyed on the capability's own identity, not on
        its disposition, so the structural reason cannot be silently attached
        to a different capability.
        """
        body = self.query_one("#workspace-filing-body", ContentScroll)
        table = ContentDataTable[str](id="workspace-filing-table", cursor_type="row", zebra_stripes=True)
        body.mount(table)
        for column_key in _COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_filing.column.{column_key}"), key=column_key)
        for capability in _filing_capabilities(self._session):
            row = capability_row(capability)
            table.add_row(
                row.capability.value,
                f"{row.glyph} {row.disposition.value}",
                f"{row.producer_owner}.{row.producer}",
                tr(f"flows.modelo_workspace_filing.{_WHY_KEYS[row.capability]}"),
                key=row.capability.value,
            )

    def action_quit_filing(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceFilingScreen"]
