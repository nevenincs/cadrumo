"""The ``modelo.workspace.results`` read destination.

Shows the CURRENT session's computed casillas -- the values a formula
produced, as distinct from the values an operator supplied, which are the
inputs destination's subject.

That distinction is admission-scoped, and this destination refuses rather
than pretends when it cannot make it. The materialization facet
(:class:`ModeloWorkspaceScalarMaterializationV1`) carries only
``casilla_id``, ``value`` and ``provenance`` -- nothing on it says whether a
casilla was computed. The distinction lives on
:class:`ModeloWorkReviewCasilla` via ``concrete_formula``, in a facet a
STATIC_INSPECTION does not carry. So under that admission this destination
cannot separate results from inputs at all, and rendering the whole facet
under a "results" heading would assert a partition it did not make.

It therefore refuses with an explicit not-applicable state under static
inspection, rather than showing the same content the inputs destination
shows at a different address. Two addresses displaying identical content
teach an operator to distrust the addresses.

Historical revisions are out of scope and unreachable, not merely unbuilt:
``resolve_graded_snapshot_result`` materializes
``work_unit.current_calculation_revision_id`` and accepts no selector for
another, so a Workspace admission can only ever describe the current
calculation. ``ModeloRevisionPick`` exists as a type but no resolve path
consumes it.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceScalarMaterializationRecordV1,
)
from .....core.i18n.render import tr
from ...components.app_access import TypedAppAccess
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll
from .controller import ModeloWorkspaceReadSession
from .models import ModeloWorkspaceBoundedPageV1

_COLUMN_KEYS: tuple[str, ...] = ("casilla", "value", "formula")


def _computed_casillas(session: ModeloWorkspaceReadSession) -> dict[str, str] | None:
    """Return each computed casilla's formula id, or ``None`` when unmeasured.

    ``None`` means this admission carries no review to partition by, which
    is a refusal condition for this destination rather than an empty result
    set. An empty MAPPING would mean the review was read and declared no
    computed casillas, which is a different and legitimate answer.
    """
    facet = session.projection.work_review
    if facet.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE or facet.review is None:
        return None
    return {
        str(casilla.casilla_id): str(casilla.concrete_formula.formula_id)
        for casilla in facet.review.casillas
        if casilla.concrete_formula is not None
    }


class ModeloWorkspaceResultsScreen(TypedAppAccess, Screen[None]):
    """Computed values for the current session, or an explicit not-applicable."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_results", ""),
        Binding("escape", "quit_results", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination renders."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-results-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-results-body", classes="cadrumo-scroll"):
            yield Static(id="workspace-results-not-applicable")
            yield Static(id="workspace-results-boundedness")

    def on_mount(self) -> None:
        """Refuse when the admission cannot partition, otherwise render the results."""
        self.query_one("#workspace-results-header", Static).update(
            tr("flows.modelo_workspace_results.title", modelo=self._session.projection.target.modelo)
        )
        computed = _computed_casillas(self._session)
        if computed is None:
            self._refuse_not_applicable()
            return
        self.query_one("#workspace-results-not-applicable", Static).remove()
        self._mount_boundedness()
        self._mount_results(computed)

    def _refuse_not_applicable(self) -> None:
        """State that this admission cannot separate results from inputs.

        A refusal, not an empty table: the screen has nothing to show
        because the partition is unavailable, which is different from
        having looked and found no computed casillas.
        """
        self.query_one("#workspace-results-not-applicable", Static).update(
            tr("flows.modelo_workspace_results.not_applicable")
        )
        self.query_one("#workspace-results-boundedness", Static).remove()

    def _mount_boundedness(self) -> None:
        """Disclose a bounded materialization page, or remove the notice."""
        notice = self.query_one("#workspace-results-boundedness", Static)
        completeness = self._session.page_completeness(ModeloWorkspaceFacetName.MATERIALIZATION)
        if isinstance(completeness, ModeloWorkspaceBoundedPageV1):
            notice.update(
                tr(
                    "flows.modelo_workspace_results.page_bounded",
                    shown=completeness.shown,
                    page_size=completeness.page_size,
                )
            )
            return
        notice.remove()

    def _mount_results(self, computed: dict[str, str]) -> None:
        """Mount one row per materialized casilla the review marks as computed."""
        body = self.query_one("#workspace-results-body", ContentScroll)
        table = ContentDataTable[str](id="workspace-results-table", cursor_type="row", zebra_stripes=True)
        body.mount(table)
        for column_key in _COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_results.column.{column_key}"), key=column_key)

        facet = self._session.projection.materialization_facet
        rows = 0
        if facet is not None:
            for record in facet.records:
                if not isinstance(record, ModeloWorkspaceScalarMaterializationRecordV1):
                    continue
                casilla_id = str(record.scalar.casilla_id)
                formula_id = computed.get(casilla_id)
                if formula_id is None:
                    continue
                value = "" if record.scalar.value is None else str(record.scalar.value)
                table.add_row(casilla_id, value, formula_id, key=casilla_id)
                rows += 1
        if rows == 0:
            body.mount(Static(tr("flows.modelo_workspace_results.empty"), id="workspace-results-empty"))

    def action_quit_results(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceResultsScreen"]
