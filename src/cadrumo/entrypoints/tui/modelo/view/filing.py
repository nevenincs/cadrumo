"""The ``modelo.workspace.filing`` read destination.

The narrowest destination in the cohort, and deliberately so. What the
Workspace contract carries about filing is two capability rows and their
producer attribution -- nothing else. Canonical filing state and filing
history are not projected, and there is no filing-record or work-unit
history contributor among the eight producer ports, so this screen has no
honest way to show them.

The two capabilities differ in KIND, and the screen says so rather than
rendering both as one uniform "unmeasured":

``FILING_DRAFT_READINESS`` is permanently unmeasured. ``build_draft`` is
pure and stateless -- it persists nothing, emits no event and stamps no
revision field -- so there is no producer whose verdict could be read, and
calling it to see whether it raises would be the derivation the contract
forbids. That is a structural fact about the filing architecture, not a
wiring gap awaiting a fix.

``FILING_EXPORT_READINESS`` is unmeasured pending a contributor port. The
approved stamp is a ``MODELO_EXPORTED`` bucket event carrying the exact
revision id, and no contributor reads bucket-event history yet. That one
CAN become available.

Collapsing those two into one message would tell an operator that filing
readiness is uniformly unknown, when half of it is unknowable by design and
half is merely unbuilt -- two different answers with two different
remedies, which is exactly the distinction this cohort exists to preserve.

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
    ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
)
_COLUMN_KEYS: tuple[str, ...] = ("capability", "disposition", "producer", "why")

_WHY_KEYS: dict[ModeloWorkspaceCapabilityName, str] = {
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "why.draft_structural",
    ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS: "why.export_pending_port",
}


def _filing_capabilities(session: ModeloWorkspaceReadSession) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Select this destination's two capabilities from the closed denominator."""
    wanted = set(_FILING_CAPABILITIES)
    return tuple(capability for capability in session.projection.capabilities if capability.capability in wanted)


class ModeloWorkspaceFilingScreen(TypedAppAccess, Screen[None]):
    """The two filing capabilities, each with why it reads as it does."""

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
        """Populate the header, the capability table, and the two disclosures."""
        self.query_one("#workspace-filing-header", Static).update(
            tr("flows.modelo_workspace_filing.title", modelo=self._session.projection.target.modelo)
        )
        self._mount_capabilities()
        self.query_one("#workspace-filing-state-not-carried", Static).update(
            tr("flows.modelo_workspace_filing.state_not_carried")
        )
        self.query_one("#workspace-filing-handoff", Static).update(tr("flows.modelo_workspace_filing.handoff"))

    def _mount_capabilities(self) -> None:
        """Mount both filing capabilities, each beside the reason it reads as it does.

        The ``why`` column is keyed on the capability's own identity, not on
        its disposition: the two share a disposition today and will not
        always, and a reason keyed on the disposition would silently attach
        the wrong explanation the moment export becomes available.
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
