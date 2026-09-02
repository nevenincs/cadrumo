"""The ``modelo.workspace.overview`` read destination.

The frame for one admitted session: which workspace this is, what state it
is in, and what the producers say can be done with it. Everything shown is
copied from the projection; this screen resolves nothing and classifies
nothing.

Two disclosures carry the destination's honesty and are worth stating
plainly, because both are places where rendering the obvious thing would
assert something untrue.

The REVISION block shows coordinates, never a chronology. Workspace V1
exposes one law-selected revision plus two independently evaluated point
assertions; it has no sequence over time, so a screen presenting a timeline
would author a temporal claim no producer made.

The ACTIONS block states that the producer supplies none, rather than
rendering an empty list. An empty actions panel reads as "there is nothing
you can do"; the truth is "this producer does not say what you can do".
Those are different claims, and only the second is true --
:class:`ModeloWorkspaceCapabilityV1` and the refusal types declare
``recovery_action`` and no producer populates it, while the surrounding
application layer attaches ``ActionReference`` to comparable verdicts
routinely. So the silence here is an omission upstream, not an absence of
actions in the system, and the screen must not convert one into the other.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from .....core.i18n.render import tr
from ...components.app_access import TypedAppAccess
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from .controller import ModeloWorkspaceReadSession
from .models import capability_row

_ADDRESS_ROW_KEYS: tuple[str, ...] = ("modelo", "filing_year", "period", "work_unit", "work_state")
_REVISION_ROW_KEYS: tuple[str, ...] = ("law_selected", "requested_assertion", "stored_assertion", "review_status")
_CAPABILITY_COLUMN_KEYS: tuple[str, ...] = ("capability", "disposition", "producer")


class ModeloWorkspaceOverviewScreen(TypedAppAccess, Screen[None]):
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
            yield Static(id="workspace-overview-actions")

    def on_mount(self) -> None:
        """Populate the header, the three disclosure groups, and the action notice."""
        target = self._session.projection.target
        self.query_one("#workspace-overview-header", Static).update(
            tr("flows.modelo_workspace_overview.title", modelo=target.modelo)
        )
        self._mount_address()
        self._mount_revision()
        self._mount_capabilities()
        self._mount_actions_disclosure()

    def _mount_address(self) -> None:
        """Disclose both the natural coordinate and the exact work identity.

        The exact identity is optional on the resolved target and its two
        fields are present together or not at all, so an absent work unit
        renders its own explicit value rather than an empty cell.
        """
        target = self._session.projection.target
        absent = tr("flows.modelo_workspace_overview.value.no_work_unit")
        values = {
            "modelo": str(target.modelo),
            "filing_year": str(target.filing_year),
            "period": target.period.registry_token,
            "work_unit": absent if target.work_unit_id is None else str(target.work_unit_id),
            "work_state": absent if target.work_state is None else target.work_state.value,
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
            "law_selected": str(target.law_selected_revision_id),
            "requested_assertion": target.requested_revision_assertion.disposition.value,
            "stored_assertion": target.stored_revision_assertion.disposition.value,
            "review_status": target.review_status.value,
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
                row.capability.value,
                f"{row.glyph} {row.disposition.value}",
                f"{row.producer_owner}.{row.producer}",
                key=row.capability.value,
            )

    def _mount_actions_disclosure(self) -> None:
        """State that no producer supplies recovery actions for this reading."""
        self.query_one("#workspace-overview-actions", Static).update(
            tr("flows.modelo_workspace_overview.actions_not_carried")
        )

    def action_quit_overview(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceOverviewScreen"]
