"""AeatSyncReconciliationScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from ....application.aeat_sync.workspace import AeatSyncWorkspaceReconciliationRowV1
from ....application.modelo.reconciliation_records import ModeloReconciliationDiff
from .screen_presentation import census_value, declaration_address, fit_columns, natural_identity, status_label
from .screens import AeatSyncWorkspaceScreen


class AeatSyncReconciliationScreen(AeatSyncWorkspaceScreen):
    """Reconciliation status surface without a generic mutation path."""

    zone = AeatSyncWorkspaceZone.RECONCILIATION
    HEADING_LOCALE_KEY = "tui.aeat_sync.reconciliation.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the reconciliation body."""
        super().__init__(controller, id="aeat-sync-reconciliation-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render source states, discrepancy, and application-set resolution."""
        if any(row.evidence_kind is not None for row in self.controller.projection.reconciliation):
            self._populate_comparisons(table)
            return
        taken = fit_columns(
            self.app.size.width,
            _POPULATE_ROWS_PRIMARY_COLUMNS_LOCALE_KEYS,
            _POPULATE_ROWS_PAIRED_COLUMNS_LOCALE_KEYS,
        )
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.reconciliation:
            cells = {
                "declaration": declaration_address(row),
                "local": status_label(row.local_state),
                "aeat": status_label(row.aeat_state),
                "difference": status_label(row.discrepancy_kind),
                # The resolution outranks the raw states here: it is what the
                # operator is being asked to accept or change.
                "resolution": status_label(row.reconciliation_state),
                "local_value": census_value(row.local_value),
                "aeat_value": census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=natural_identity(row, prefix="reconciliation"),
            )

    @override
    def compose_evidence(self) -> ComposeResult:
        yield Static(id="aeat-sync-reconciliation-detail", markup=False)

    @override
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        super().on_data_table_row_highlighted(event)
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-rows" and hasattr(self, "_comparison_details"):
            self.query_one("#aeat-sync-reconciliation-detail", Static).update(
                self._comparison_details.get(str(event.row_key.value), "")
            )

    def _populate_comparisons(self, table: DataTable[str]) -> None:
        """Show every diff with both values and the selected row's full provenance."""
        columns = fit_columns(
            self.app.size.width,
            _POPULATE_COMPARISONS_PRIMARY_COLUMNS_LOCALE_KEYS,
            _POPULATE_COMPARISONS_PAIRED_COLUMNS_LOCALE_KEYS,
        )
        for name, header, width in columns:
            table.add_column(header, key=name, width=width)
        self._comparison_details: dict[str, str] = {}
        for row in self.controller.projection.reconciliation:
            evidence = (
                tr("tui.aeat_sync.reconciliation.evidence.justificante")
                if row.evidence_kind is not None and row.evidence_kind.value == "justificante"
                else tr("tui.aeat_sync.reconciliation.evidence.declaration")
            )
            advisory = (
                tr("tui.aeat_sync.reconciliation.advisories_withheld", count=row.advisory_count)
                if row.advisory_count
                else "0"
            )
            for index, diff in enumerate(row.diffs or (None,)):
                cells = _comparison_cells(row, diff)
                key = f"{natural_identity(row, prefix='reconciliation')}:{row.comparison_id or 'legacy'}:{index}"
                table.add_row(*(cells[name] for name, _, _ in columns), key=key)
                self._comparison_details[key] = _comparison_details(row, diff, cells, evidence, advisory)
        self.query_one("#aeat-sync-reconciliation-detail", Static).update(
            next(iter(self._comparison_details.values()), "")
        )


def _comparison_cells(
    row: AeatSyncWorkspaceReconciliationRowV1, diff: ModeloReconciliationDiff | None
) -> dict[str, str]:
    return {
        "declaration": declaration_address(row),
        "field": (
            diff.field_name
            if diff is not None
            else tr("tui.aeat_sync.reconciliation.incomplete")
            if row.advisory_count
            else tr("tui.aeat_sync.reconciliation.matches")
        ),
        "local_value": census_value(row.local_value if diff is None else diff.work_unit_value),
        "aeat_value": census_value(row.aeat_value if diff is None else diff.evidence_value),
    }


def _comparison_details(
    row: AeatSyncWorkspaceReconciliationRowV1,
    diff: ModeloReconciliationDiff | None,
    cells: dict[str, str],
    evidence: str,
    advisory: str,
) -> str:
    details = [
        f"{cells['declaration']} | {evidence} | {row.local_observed_at}",
        cells["field"],
        f"{tr('tui.aeat_sync.column.local_value')}: {cells['local_value']}",
        f"{tr('tui.aeat_sync.column.aeat_value')}: {cells['aeat_value']}",
    ]
    if row.historical:
        details.insert(0, tr("tui.aeat_sync.reconciliation.historical"))
    details.append(
        tr("tui.aeat_sync.reconciliation.calculation_revision", revision=row.calculation_revision_id)
        if row.calculation_revision_id is not None
        else tr("tui.aeat_sync.reconciliation.calculation_revision_unknown")
    )
    if row.work_unit_id is not None and row.evidence_id is not None:
        details.append(tr("tui.aeat_sync.reconciliation.identity", work=row.work_unit_id, evidence=row.evidence_id))
    if diff is not None:
        details.extend((f"{diff.diff_kind.value}: {diff.kind}", *diff.legal_refs, *diff.source_refs))
    if row.advisory_count:
        details.append(advisory)
    return "\n".join(details)


_POPULATE_ROWS_PRIMARY_COLUMNS_LOCALE_KEYS = (
    ("declaration", "tui.aeat_sync.column.declaration", 20),
    ("resolution", "tui.aeat_sync.column.resolution", 14),
    ("difference", "tui.aeat_sync.column.difference", 14),
    ("local", "tui.aeat_sync.column.local", 10),
    ("aeat", "tui.aeat_sync.column.aeat", 10),
)


_POPULATE_ROWS_PAIRED_COLUMNS_LOCALE_KEYS = (
    ("local_value", "tui.aeat_sync.column.local_value", 16),
    ("aeat_value", "tui.aeat_sync.column.aeat_value", 16),
)


_POPULATE_COMPARISONS_PRIMARY_COLUMNS_LOCALE_KEYS = (
    ("declaration", "tui.aeat_sync.column.declaration", 18),
    ("field", "tui.aeat_sync.column.field", 16),
)


_POPULATE_COMPARISONS_PAIRED_COLUMNS_LOCALE_KEYS = (
    ("local_value", "tui.aeat_sync.column.local_value", 14),
    ("aeat_value", "tui.aeat_sync.column.aeat_value", 14),
)
