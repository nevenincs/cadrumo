"""The ``modelo.workspace.inputs`` read destination.

Renders one admitted workspace session's declared fields and their
materialized values. It is a READ destination: it mounts no editing widget
of any kind, because the edit surface is a C3 concern whose authority is a
time-bounded admission this cohort does not hold. A screen that offered an
edit affordance it cannot honour would promise the operator something the
contract refuses.

Grouping follows ``ModeloWorkspaceSchemaRecordV1.record_family``, which
the assembler sets to a literal (``("casillas",)``, ``("bindings",)``,
``("formulas",)``, ``("relations",)``, ``("parameters",)``). The family is
the only coherent grouping for that facet: it carries casillas, bindings,
formulas, relations and parameters in one record set, and a casilla-only
section path is undefined over four of those five.

So an operator sees these records grouped by family, not by the modelo's
sections. The modelo's own ``CasillaDefinition.section`` is not projected
into the workspace schema facet at all, and this module does not
substitute for it: inventing a section structure the projection does not
carry would be exactly the synthesis the cohort forbids everywhere else.

Row identity is the canonical identity the producer already assigned -- a
casilla id for a scalar, a (binding, row index) pair for a repeated row --
so a row key never encodes an address the registry does not have.

Under STATIC_INSPECTION the materialization facet is ``None`` by
construction, and absence is rendered as an explicit not-measured
disposition rather than as a zero, a blank, or an empty table. That
distinction is the same one ``workspace_models`` defends one layer down:
"nothing was measured" and "the measured value is nothing" are different
answers with different operator remedies.
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
    ModeloWorkspaceRepeatedRowMaterializationRecordV1,
    ModeloWorkspaceScalarMaterializationRecordV1,
)
from .....core.i18n import tr
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from .controller import ModeloWorkspaceReadSession
from .models import ModeloWorkspaceBoundedPageV1, display_text

_COLUMN_KEYS: tuple[str, ...] = ("address", "label", "value", "input_kind")
"""The stable column order for every section table on this destination."""


def _input_kinds_by_casilla(session: ModeloWorkspaceReadSession) -> dict[str, str] | None:
    """Return each casilla's registry-declared input kind, or ``None`` if unmeasured.

    The kind comes from the canonical review record
    (``ModeloWorkReviewCasilla.declared_input_kind``), reached through the
    work-review facet's own disposition. ``None`` means this admission never
    measured it -- a STATIC_INSPECTION carries no materialized review at all
    -- and is deliberately distinct from an empty mapping, which would say
    the review was consulted and declared nothing.

    This is the registry's declaration of what a casilla IS, never a
    permission to change it. The edit surface is
    ``ModeloEditPermittedSurfaceEntryV1``, reachable only through an
    admission carrying a time-bounded lease that a read cohort does not
    hold; rendering that here would be C2 taking mutation authority it is
    defined not to have.
    """
    facet = session.projection.work_review
    if facet.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE or facet.review is None:
        return None
    return {str(casilla.casilla_id): casilla.declared_input_kind.value for casilla in facet.review.casillas}


def _family_title(record_family: tuple[str, ...]) -> str:
    """Render one schema record-family label as its disclosure title.

    Joined for display only. The label itself stays the grouping key, so two
    families that render alike still group apart.
    """
    return " / ".join(record_family) if record_family else tr("flows.modelo_workspace_inputs.section.unsectioned")


def _scalar_row(record: ModeloWorkspaceScalarMaterializationRecordV1) -> tuple[str, str]:
    """Render one materialized scalar, keyed by its canonical casilla identity."""
    scalar = record.scalar
    return (str(scalar.casilla_id), "" if scalar.value is None else str(scalar.value))


def _repeated_rows(record: ModeloWorkspaceRepeatedRowMaterializationRecordV1) -> tuple[tuple[str, str], ...]:
    """Render one repeated binding row as one display row per contained value.

    The (binding, row index) pair stays in the address rather than being
    flattened into a synthetic casilla id: a repeated row is not addressable
    as a casilla, and inventing such an address would put a key in the table
    that no registry lookup can resolve.
    """
    repeated = record.repeated_row
    return tuple(
        (
            f"{repeated.binding_id}[{repeated.row_index}].{value.casilla_id}",
            "" if value.value is None else str(value.value),
        )
        for value in repeated.values
    )


class ModeloWorkspaceInputsScreen(Screen[None]):
    """Read-only section, scalar, and repeated-row rendering for one session."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_inputs", ""),
        Binding("escape", "quit_inputs", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination renders."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-inputs-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-inputs-body", classes="cadrumo-scroll"):
            yield Static(id="workspace-inputs-values-disposition")
            yield Static(id="workspace-inputs-boundedness")

    def on_mount(self) -> None:
        """Populate the header, the value disposition, and one group per section."""
        projection = self._session.projection
        self.query_one("#workspace-inputs-header", Static).update(
            tr("flows.modelo_workspace_inputs.title", modelo=projection.target.modelo)
        )
        self._mount_values_disposition()
        self._mount_boundedness()
        self._mount_sections()

    def _mount_values_disposition(self) -> None:
        """State plainly whether this admission measured values at all."""
        banner = self.query_one("#workspace-inputs-values-disposition", Static)
        if self._session.projection.materialization_facet is None:
            banner.update(tr("flows.modelo_workspace_inputs.values_unmeasured"))
            return
        banner.remove()

    def _mount_boundedness(self) -> None:
        """Disclose a bounded page as bounded, or remove the notice entirely.

        An empty notice would read as a rendering defect, so the widget is
        removed rather than shown blank when the page IS the whole set.
        """
        notice = self.query_one("#workspace-inputs-boundedness", Static)
        completeness = self._session.page_completeness(ModeloWorkspaceFacetName.MATERIALIZATION)
        if isinstance(completeness, ModeloWorkspaceBoundedPageV1):
            notice.update(
                tr(
                    "flows.modelo_workspace_inputs.page_bounded",
                    shown=completeness.shown,
                    page_size=completeness.page_size,
                )
            )
            return
        notice.remove()

    def _mount_sections(self) -> None:
        """Mount one disclosure group per registry-declared section path."""
        body = self.query_one("#workspace-inputs-body", ContentScroll)
        labels = {
            str(record.reference): display_text(record.label).text
            for record in self._session.projection.schema_facet.records
        }
        input_kinds = _input_kinds_by_casilla(self._session)
        unmeasured = tr("flows.modelo_workspace_inputs.input_kind_unmeasured")
        rows_by_family = self._rows_by_family()
        if not rows_by_family:
            body.mount(Static(tr("flows.modelo_workspace_inputs.empty"), id="workspace-inputs-empty"))
            return
        for index, (record_family, rows) in enumerate(sorted(rows_by_family.items())):
            table = ContentDataTable(id=f"workspace-inputs-table-{index}", cursor_type="row", zebra_stripes=True)
            body.mount(DisclosureGroup(table, title=_family_title(record_family), collapsed=False))
            for column_key in _COLUMN_KEYS:
                table.add_column(tr(f"flows.modelo_workspace_inputs.column.{column_key}"), key=column_key)
            for address, value in rows:
                table.add_row(
                    address,
                    labels.get(address, ""),
                    value,
                    unmeasured if input_kinds is None else input_kinds.get(address, ""),
                    key=address,
                )

    def _rows_by_family(self) -> dict[tuple[str, ...], tuple[tuple[str, str], ...]]:
        """Group every materialized row under the section its schema record declares."""
        facet = self._session.projection.materialization_facet
        if facet is None:
            return {}
        sections = {
            str(record.reference): record.record_family for record in self._session.projection.schema_facet.records
        }
        grouped: dict[tuple[str, ...], list[tuple[str, str]]] = {}
        for record in facet.records:
            rows = (
                (_scalar_row(record),)
                if isinstance(record, ModeloWorkspaceScalarMaterializationRecordV1)
                else _repeated_rows(record)
            )
            for row in rows:
                grouped.setdefault(sections.get(row[0], ()), []).append(row)
        return {section: tuple(rows) for section, rows in grouped.items()}

    def action_quit_inputs(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceInputsScreen"]
