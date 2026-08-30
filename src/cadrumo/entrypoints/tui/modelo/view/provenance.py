"""The ``modelo.workspace.provenance`` read destination.

Flat bounded attribution: one row per contributing source the producer
recorded, showing which subject it fed when it named one.

NO CAUSAL EXPANSION. ``ModeloWorkspaceProvenanceRecordV1`` is
``(subject | None, calculation_source)`` and carries no depth, no parent
link and no cycle marker. A screen that arranged these rows into a tree, or
labelled any of them by depth, would author a causal claim no producer
made. The rows are an attribution list, and this destination presents them
as one.

An unattributed row is shown, never dropped. ``subject`` is ``None`` when
the underlying ``CalculationSourceRef`` names no casilla, which is the
common case today; the producer deliberately emits exactly one record for
such a ref rather than zero, so an audit reader sees every contributing
source. Hiding those rows here would undo that at the last step.

Paging is the NORMAL case, not the exception. One source reference fans out
to one record per casilla it names, so this facet can overflow without the
revision growing at all -- and row count therefore tells an operator
nothing about completeness. The boundedness notice is the only thing that
does.

The per-value provenance nested on materialization records is NOT read
here, and not because this destination prefers the facet: that nested field
is never populated by any producer, so a screen drawing on it would render
permanently empty lists. The facet is the only populated provenance
surface.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from .....application.modelo.workspace_models import ModeloWorkspaceFacetName
from .....core.i18n import tr
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll
from .controller import ModeloWorkspaceReadSession
from .models import ModeloWorkspaceBoundedPageV1

_COLUMN_KEYS: tuple[str, ...] = ("subject", "resolver", "source_ref")


class ModeloWorkspaceProvenanceScreen(Screen[None]):
    """Flat attribution rows for the current session, or an explicit not-applicable."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_provenance", ""),
        Binding("escape", "quit_provenance", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination renders."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-provenance-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-provenance-body", classes="cadrumo-scroll"):
            yield Static(id="workspace-provenance-not-applicable")
            yield Static(id="workspace-provenance-boundedness")

    def on_mount(self) -> None:
        """Refuse when the admission carries no provenance, otherwise render the rows."""
        self.query_one("#workspace-provenance-header", Static).update(
            tr("flows.modelo_workspace_provenance.title", modelo=self._session.projection.target.modelo)
        )
        if self._session.projection.provenance_facet is None:
            self._refuse_not_applicable()
            return
        self.query_one("#workspace-provenance-not-applicable", Static).remove()
        self._mount_boundedness()
        self._mount_rows()

    def _refuse_not_applicable(self) -> None:
        """State that this admission carries no provenance facet at all."""
        self.query_one("#workspace-provenance-not-applicable", Static).update(
            tr("flows.modelo_workspace_provenance.not_applicable")
        )
        self.query_one("#workspace-provenance-boundedness", Static).remove()

    def _mount_boundedness(self) -> None:
        """Disclose a bounded page, because row count cannot disclose it here.

        Removed entirely when the page IS the whole set; an empty notice
        would read as a rendering defect.
        """
        notice = self.query_one("#workspace-provenance-boundedness", Static)
        completeness = self._session.page_completeness(ModeloWorkspaceFacetName.PROVENANCE)
        if isinstance(completeness, ModeloWorkspaceBoundedPageV1):
            notice.update(
                tr(
                    "flows.modelo_workspace_provenance.page_bounded",
                    shown=completeness.shown,
                    page_size=completeness.page_size,
                )
            )
            return
        notice.remove()

    def _mount_rows(self) -> None:
        """Mount one row per attribution record, unattributed ones included."""
        facet = self._session.projection.provenance_facet
        assert facet is not None
        body = self.query_one("#workspace-provenance-body", ContentScroll)
        table = ContentDataTable(id="workspace-provenance-table", cursor_type="row", zebra_stripes=True)
        body.mount(table)
        for column_key in _COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_provenance.column.{column_key}"), key=column_key)
        unattributed = tr("flows.modelo_workspace_provenance.value.unattributed")
        for index, record in enumerate(facet.records):
            source = record.calculation_source
            table.add_row(
                unattributed if record.subject is None else str(record.subject),
                str(source.resolver_id),
                str(source.source_ref),
                key=str(index),
            )
        if not facet.records:
            body.mount(Static(tr("flows.modelo_workspace_provenance.empty"), id="workspace-provenance-empty"))

    def action_quit_provenance(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceProvenanceScreen"]
