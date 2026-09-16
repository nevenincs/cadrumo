"""The ``modelo.workspace.overview`` read destination.

The frame for one admitted session: which workspace this is, what state it
is in, and what the producers say can be done with it. Everything shown is
copied from the projection; this screen resolves nothing and classifies
nothing.

Everything on the page leads with the operator's words: dispositions,
assertions, review status and work state are named, never shown as their
transport tokens. Producer attribution and raw identifiers -- the work unit,
the law-selected revision, each capability's ``owner.producer`` -- stay
reachable in a collapsed technical-details group, because they answer
"which code said so", not "what does this mean for me".

Two disclosures carry the destination's honesty and are worth stating
plainly, because both are places where rendering the obvious thing would
assert something untrue.

The REVISION block shows coordinates, never a chronology. Workspace V1
exposes one law-selected revision plus two independently evaluated point
assertions; it has no sequence over time, so a screen presenting a timeline
would author a temporal claim no producer made.

The ACTIONS line says in one plain sentence that this page suggests no
next steps yet, rather than rendering an empty list. An empty actions panel reads as "there is nothing
you can do"; the truth is "this producer does not say what you can do".
Those are different claims, and only the second is true --
:class:`ModeloWorkspaceCapabilityV1` and the refusal types declare
``recovery_action`` and no producer populates it, while the surrounding
application layer attaches ``ActionReference`` to comparable verdicts
routinely. So the silence here is an omission upstream, not an absence of
actions in the system, and the screen must not convert one into the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Static

from .....core.i18n.render import tr
from ...components.account_chrome import AccountChromeScreen
from ...components.app_access import TypedAppAccess
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from .controller import ModeloWorkspaceReadSession
from .models import (
    assertion_label,
    capability_label,
    capability_row,
    disposition_label,
    review_status_label,
    work_state_label,
)
from .technical_details import TechnicalDetailRowV1, mount_technical_details, producer_row

if TYPE_CHECKING:
    from .models import ModeloWorkspaceDestinationIdV1

_ADDRESS_ROW_KEYS: tuple[str, ...] = ("modelo", "filing_year", "period", "work_state")
_REVISION_ROW_KEYS: tuple[str, ...] = ("requested_assertion", "stored_assertion", "review_status")
_CAPABILITY_COLUMN_KEYS: tuple[str, ...] = ("capability", "disposition")
_OTHER_DESTINATIONS: tuple[str, ...] = ("inputs", "results", "verification", "provenance", "filing")


class ModeloWorkspaceOverviewScreen(TypedAppAccess, AccountChromeScreen):
    """Address, revision coordinates, status, and the capability denominator."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_overview", ""),
        Binding("escape", "quit_overview", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination frames."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-overview-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-overview-body", classes="cadrumo-scroll"):
            yield Static(
                tr("tui.modelo.destination.heading"),
                classes="cadrumo-heading cadrumo-heading-lead",
                markup=False,
            )
            yield ContentDataTable[str](id="workspace-overview-destinations", cursor_type="row", zebra_stripes=True)
            yield Static(id="workspace-overview-actions")

    def on_mount(self) -> None:
        """Populate the header, the destination list, the disclosure groups, and the action notice."""
        target = self._session.projection.target
        self.query_one("#workspace-overview-header", Static).update(
            tr("flows.modelo_workspace_overview.title", modelo=target.modelo)
        )
        self._mount_destinations()
        self._mount_address()
        self._mount_revision()
        self._mount_capabilities()
        self._mount_actions_disclosure()
        self._mount_technical_details()

    def _mount_destinations(self) -> None:
        """List the declaration's other read pages; this page is the way into them.

        The pages had routes but nothing on screen led to them, so a
        declaration opened on its overview and went no further.
        """
        table = self.query_one("#workspace-overview-destinations", ContentDataTable)
        table.add_column(tr("tui.modelo.destination.column"), key="destination")
        for destination in _OTHER_DESTINATIONS:
            table.add_row(tr(f"tui.modelo.destination.{destination}"), key=f"modelo.workspace.{destination}")
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected page over this one; leaving it returns here."""
        if event.data_table.id != "workspace-overview-destinations" or event.row_key.value is None:
            return
        # Imported here: the route table imports this module for its own page.
        from ..routes import resolve_destination

        destination = cast("ModeloWorkspaceDestinationIdV1", str(event.row_key.value))
        self.app.push_screen(resolve_destination(destination)(self._session))

    def _mount_address(self) -> None:
        """Disclose the natural coordinate and the work state.

        The work state is optional on the resolved target, so an absent work
        unit renders its own explicit value rather than an empty cell. The
        exact work identity is a raw identifier and sits in the technical
        details.
        """
        target = self._session.projection.target
        absent = tr("flows.modelo_workspace_overview.value.no_work_unit")
        values = {
            "modelo": str(target.modelo),
            "filing_year": str(target.filing_year),
            "period": target.period.registry_token,
            "work_state": absent if target.work_state is None else work_state_label(target.work_state),
        }
        self._mount_label_table("address", _ADDRESS_ROW_KEYS, values)

    def _mount_revision(self) -> None:
        """Disclose the revision COORDINATES, never a chronology.

        The two assertions are shown by their own disposition rather than by
        their value: ``NOT_PRESENT`` is a real answer meaning nobody asserted
        a revision, and showing it as a blank would read as a missing value
        instead of an absent claim.
        """
        target = self._session.projection.target
        values = {
            "requested_assertion": assertion_label(target.requested_revision_assertion.disposition),
            "stored_assertion": assertion_label(target.stored_revision_assertion.disposition),
            "review_status": review_status_label(target.review_status),
        }
        self._mount_label_table("revision", _REVISION_ROW_KEYS, values)

    def _mount_label_table(self, group: str, row_keys: tuple[str, ...], values: dict[str, str]) -> None:
        """Mount one two-column label/value table inside its own disclosure group."""
        body = self.query_one("#workspace-overview-body", ContentScroll)
        table = ContentDataTable[str](id=f"workspace-overview-{group}-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr(f"flows.modelo_workspace_overview.section.{group}"), collapsed=False)
        )
        table.add_column(tr("flows.modelo_workspace_overview.column.field"), key="field")
        table.add_column(tr("flows.modelo_workspace_overview.column.value"), key="value")
        for row_key in row_keys:
            table.add_row(tr(f"flows.modelo_workspace_overview.label.{row_key}"), values[row_key], key=row_key)

    def _mount_capabilities(self) -> None:
        """Mount the complete capability denominator, each row with its own glyph.

        Every capability appears exactly once because the projection
        guarantees it; the screen does not filter to the interesting ones. A
        capability omitted from the display would be indistinguishable from
        one the producer never answered.
        """
        body = self.query_one("#workspace-overview-body", ContentScroll)
        table = ContentDataTable[str](id="workspace-overview-capability-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_overview.section.capabilities"), collapsed=False)
        )
        for column_key in _CAPABILITY_COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_overview.column.{column_key}"), key=column_key)
        for capability in self._session.projection.capabilities:
            row = capability_row(capability)
            table.add_row(
                capability_label(row.capability), disposition_label(row.disposition), key=row.capability.value
            )

    def _mount_actions_disclosure(self) -> None:
        """Say plainly that this page suggests no next steps yet."""
        self.query_one("#workspace-overview-actions", Static).update(
            tr("flows.modelo_workspace_overview.actions_not_carried")
        )

    def _mount_technical_details(self) -> None:
        """Keep the raw identities and producer attribution, collapsed.

        Each capability's producer is listed under the capability's own name,
        so the attribution the table above no longer shows is one key away.
        """
        target = self._session.projection.target
        rows: list[TechnicalDetailRowV1] = [
            (
                "work_unit",
                tr("flows.modelo_workspace_overview.label.work_unit"),
                tr("flows.modelo_workspace_overview.value.no_work_unit")
                if target.work_unit_id is None
                else str(target.work_unit_id),
            ),
            (
                "law_selected",
                tr("flows.modelo_workspace_overview.label.law_selected"),
                str(target.law_selected_revision_id),
            ),
        ]
        rows.extend(producer_row(capability_row(capability)) for capability in self._session.projection.capabilities)
        mount_technical_details(
            self.query_one("#workspace-overview-body", ContentScroll), rows, id="workspace-overview-technical-table"
        )

    def action_quit_overview(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceOverviewScreen"]
