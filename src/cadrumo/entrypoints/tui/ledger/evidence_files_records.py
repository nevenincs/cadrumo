"""Evidence records: list, view, correct and remove the profile's invoice evidence.

The list is the registered evidence query, one page at a time; a chosen record
is read through the evidence view. A correction or a removal is staged from the
selected record with its current values and sent only after the operator
confirms it on the write step. Only the document's own file name is shown,
never the folder it came from.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Static

from ....application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateField,
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateRequest,
)
from ....application.ledger.evidence_read_operation import (
    LedgerEvidenceAutomationRecordProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceRecordProjection,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from ....core.i18n.render import tr
from ..components.language import localized, repaint_tables
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController
from .evidence_files_common import (
    EvidenceFilesPager,
    EvidenceFilesToolScreen,
    blank_to_none,
    paging_controls,
    paint_paging,
    short_identity,
    shown,
)
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .evidence_files_review import LedgerEvidenceFilesReviewScreen
from .evidence_files_write import (
    EvidenceFilesOutcomeV1,
    EvidenceFilesReviewV1,
    EvidenceFilesSubmitV1,
    EvidenceFilesWordingV1,
    LedgerEvidenceFilesWriteScreen,
)
from .workspace_presentation import door_refusal_text, ledger_workspace_page
from .workspace_screen import LedgerWorkspaceScreen

_EDITABLE_FIELDS: Final[tuple[LedgerEvidenceUpdateField, ...]] = (
    "supplier",
    "invoice_number",
    "invoice_date",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "notes",
)
_FIELD_LOCALE_KEYS: Final[dict[LedgerEvidenceUpdateField, str]] = {
    "supplier": "tui.ledger.evidence_files.field.supplier",
    "invoice_number": "tui.ledger.evidence_files.field.invoice_number",
    "invoice_date": "tui.ledger.evidence_files.field.invoice_date",
    "taxable_base": "tui.ledger.evidence_files.field.taxable_base",
    "iva_rate": "tui.ledger.evidence_files.field.iva_rate",
    "iva_amount": "tui.ledger.evidence_files.field.iva_amount",
    "notes": "tui.ledger.evidence_files.field.notes",
}
_STAGE_BUTTONS: Final = ("evidence-files-review-update", "evidence-files-review-remove", "evidence-files-open-review")


def _input_id(field: LedgerEvidenceUpdateField) -> str:
    return f"evidence-files-field-{field.replace('_', '-')}"


def _field_label(field: LedgerEvidenceUpdateField) -> str:
    return tr(_FIELD_LOCALE_KEYS[field])


def evidence_field_value(
    source: LedgerEvidenceRecordProjection | LedgerEvidenceUpdatePatch, field: LedgerEvidenceUpdateField
) -> str | None:
    """One correctable field of a record or a patch; an empty text is no value."""
    match field:
        case "supplier":
            value = source.supplier
        case "invoice_number":
            value = source.invoice_number
        case "invoice_date":
            value = source.invoice_date
        case "taxable_base":
            value = source.taxable_base
        case "iva_rate":
            value = source.iva_rate
        case "iva_amount":
            value = source.iva_amount
        case "notes":
            value = source.notes
    return value or None


def _current_value(record: LedgerEvidenceRecordProjection, field: LedgerEvidenceUpdateField) -> str | None:
    return evidence_field_value(record, field)


class LedgerEvidenceFilesRecordsScreen(EvidenceFilesToolScreen):
    """The profile's evidence records, one page at a time, with correction and removal."""

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEvidenceFilesDoorsV1,
        *,
        selected_id: str | None = None,
    ) -> None:
        """Open over the injected doors, restoring ``selected_id`` once the list is read."""
        super().__init__(controller, doors, id="ledger-evidence-files-records-screen")
        self.records: EvidenceFilesPager[LedgerEvidenceAutomationRecordProjection] = EvidenceFilesPager()
        self.selected_id = selected_id
        self.selected: LedgerEvidenceRecordProjection | None = None
        self.filter_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(tr("tui.ledger.evidence_files.records.title"), "tui.ledger.evidence_files.records.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.records.prompt"), markup=False),
                "tui.ledger.evidence_files.records.prompt",
            )
            yield localized(
                Input(placeholder=tr("tui.ledger.evidence_files.records.filter"), id="evidence-files-filter"),
                "tui.ledger.evidence_files.records.filter",
            )
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(tr("tui.ledger.evidence_files.records.search"), id="evidence-files-search"),
                    "tui.ledger.evidence_files.records.search",
                )
                yield localized(
                    Button(tr("tui.ledger.evidence_files.records.all"), id="evidence-files-all"),
                    "tui.ledger.evidence_files.records.all",
                )
            yield ContentDataTable[str](id="evidence-files-records", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-records")
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="evidence-files-detail", classes="evidence-files-detail", markup=False)
            yield localized(
                Static(tr("tui.ledger.evidence_files.records.edit_heading"), classes="cadrumo-heading", markup=False),
                "tui.ledger.evidence_files.records.edit_heading",
            )
            yield localized(
                Static(tr("tui.ledger.evidence_files.records.edit_hint"), markup=False),
                "tui.ledger.evidence_files.records.edit_hint",
            )
            for field in _EDITABLE_FIELDS:
                yield localized(Static(_field_label(field), markup=False), _FIELD_LOCALE_KEYS[field])
                yield Input(id=_input_id(field))
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(tr("tui.ledger.evidence_files.records.review_update"), id="evidence-files-review-update"),
                    "tui.ledger.evidence_files.records.review_update",
                )
                yield localized(
                    Button(tr("tui.ledger.evidence_files.records.review_remove"), id="evidence-files-review-remove"),
                    "tui.ledger.evidence_files.records.review_remove",
                )
            yield localized(
                Button(tr("tui.ledger.evidence_files.records.open_review"), id="evidence-files-open-review"),
                "tui.ledger.evidence_files.records.open_review",
            )

    def on_mount(self) -> None:
        """Show the shell, then read the first page off the event loop."""
        self._paint()
        self._set_selected_controls()
        self.start(self._load)

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        repaint_tables(self, self._paint)
        if self.selected is not None:
            self._show_detail(self.selected)

    def _paint(self) -> None:
        self.populate_navigation()
        self._paint_records()

    def _paint_records(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-records", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence_files.column.record"), key="record")
        table.add_column(tr("tui.ledger.evidence_files.column.file"), key="file")
        table.add_column(tr("tui.ledger.evidence_files.column.supplier"), key="supplier")
        table.add_column(tr("tui.ledger.evidence_files.column.invoice"), key="invoice")
        table.add_column(tr("tui.ledger.evidence_files.column.date"), key="date")
        for row in self.records.page():
            table.add_row(
                short_identity(row.evidence_id),
                shown(row.source_file_name),
                shown(row.supplier),
                shown(row.invoice_number),
                shown(row.invoice_date),
                key=row.evidence_id,
            )
        selected = next(
            (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_id), None
        )
        if selected is not None:
            table.move_cursor(row=selected, animate=False)
        paint_paging(self, "evidence-files-records", self.records)

    async def _load(self) -> None:
        self.status(tr("tui.ledger.evidence_files.loading"))
        result = await self.ask(
            self.doors.query(LedgerEvidenceQueryRequest(profile_id=self.doors.profile_id, evidence_id=self.filter_id))
        )
        if result is None:
            return
        self.records.load(result.rows)
        if self.selected_id is not None and all(row.evidence_id != self.selected_id for row in result.rows):
            self._forget_selection()
        if self.selected_id is not None:
            index = next(index for index, row in enumerate(result.rows) if row.evidence_id == self.selected_id)
            self.records.offset = index - index % self.records.page_size
        self._paint_records()
        self._show_load_status(result.count)
        if self.selected_id is not None:
            await self._view(self.selected_id)

    def _show_load_status(self, count: int) -> None:
        if count == 0:
            key = (
                "tui.ledger.evidence_files.records.none_found"
                if self.filter_id is not None
                else "tui.ledger.evidence_files.records.empty"
            )
            self.status(tr(key))
        else:
            self.status("")

    async def _view(self, evidence_id: str) -> None:
        result = await self.ask(
            self.doors.view(LedgerEvidenceViewRequest(profile_id=self.doors.profile_id, evidence_id=evidence_id))
        )
        if result is None:
            return
        if not isinstance(result.outcome, LedgerEvidenceViewSuccess):
            self._forget_selection()
            self.refuse(tr("tui.ledger.evidence_files.records.gone"))
            return
        record = result.outcome.record
        self.selected_id = record.evidence_id
        self.selected = record
        self._show_detail(record)
        for field in _EDITABLE_FIELDS:
            self.query_one(f"#{_input_id(field)}", Input).value = _current_value(record, field) or ""
        self._set_selected_controls()

    def _file_name(self, evidence_id: str) -> str:
        row = next((item for item in self.records.items if item.evidence_id == evidence_id), None)
        return shown(None if row is None else row.source_file_name)

    def _show_detail(self, record: LedgerEvidenceRecordProjection) -> None:
        self.query_one("#evidence-files-detail", Static).update(
            "\n".join(
                (
                    tr(
                        "tui.ledger.evidence_files.records.detail.identity",
                        record=short_identity(record.evidence_id),
                        file=self._file_name(record.evidence_id),
                        kind=record.media_kind.value,
                    ),
                    tr(
                        "tui.ledger.evidence_files.records.detail.invoice",
                        supplier=shown(record.supplier),
                        number=shown(record.invoice_number),
                        date=shown(record.invoice_date),
                    ),
                    tr(
                        "tui.ledger.evidence_files.records.detail.amounts",
                        base=shown(record.taxable_base),
                        rate=shown(record.iva_rate),
                        iva=shown(record.iva_amount),
                    ),
                    tr("tui.ledger.evidence_files.records.detail.notes", notes=shown(record.notes)),
                    tr(
                        "tui.ledger.evidence_files.records.detail.dates",
                        added=record.created_at.date().isoformat(),
                        updated=record.updated_at.date().isoformat(),
                    ),
                )
            )
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Read the chosen record through the evidence view."""
        if self.handle_navigation_selection(event):
            return
        if event.data_table.id != "evidence-files-records" or event.row_key.value is None:
            return
        evidence_id = str(event.row_key.value)
        if self.start(lambda: self._view(evidence_id)):
            self.selected_id = evidence_id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Search, page, or stage a correction or removal of the selected record."""
        match event.button.id:
            case "evidence-files-search":
                self.filter_id = blank_to_none(self.query_one("#evidence-files-filter", Input).value)
                self.records.offset = 0
                self.start(self._load)
            case "evidence-files-all":
                self.filter_id = None
                self.query_one("#evidence-files-filter", Input).value = ""
                self.records.offset = 0
                self.start(self._load)
            case "evidence-files-records-previous":
                self.records.previous()
                self._paint_records()
            case "evidence-files-records-next":
                self.records.next()
                self._paint_records()
            case "evidence-files-review-update":
                self._stage_update()
            case "evidence-files-review-remove":
                self._stage_remove()
            case "evidence-files-open-review":
                self._open_review()
            case _:
                return

    def _origin(self, selected_id: str | None) -> Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]:
        doors = self.doors

        def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
            return LedgerEvidenceFilesRecordsScreen(controller, doors, selected_id=selected_id)

        return build

    def _stage_update(self) -> None:
        record = self.selected
        if self.busy or record is None:
            self.refuse(tr("tui.ledger.evidence_files.records.choose_record"))
            return
        changes: dict[LedgerEvidenceUpdateField, str] = {}
        for field in _EDITABLE_FIELDS:
            entered = blank_to_none(self.query_one(f"#{_input_id(field)}", Input).value)
            if entered is not None and entered != _current_value(record, field):
                changes[field] = entered
        if not changes:
            self.refuse(tr("tui.ledger.evidence_files.records.no_change"))
            return
        try:
            request = LedgerEvidenceUpdateRequest(
                profile_id=self.doors.profile_id,
                evidence_id=record.evidence_id,
                patch=LedgerEvidenceUpdatePatch.model_validate(changes),
                patch_fields=tuple(changes),
            )
        except ValidationError as error:
            self.refuse(door_refusal_text(error))
            return
        file_name = self._file_name(record.evidence_id)
        current = {field: _current_value(record, field) for field in changes}

        def review() -> tuple[str, ...]:
            return (
                tr(
                    "tui.ledger.evidence_files.records.stage.update",
                    record=short_identity(record.evidence_id),
                    file=file_name,
                ),
                *(
                    tr(
                        "tui.ledger.evidence_files.records.stage.change",
                        field=_field_label(field),
                        current=shown(current[field]),
                        new=value,
                    )
                    for field, value in changes.items()
                ),
            )

        doors = self.doors

        async def submit() -> EvidenceFilesWordingV1:
            result = await doors.update(request)
            key = (
                "tui.ledger.evidence_files.records.outcome.updated"
                if result.bucket_event_ids
                else "tui.ledger.evidence_files.records.outcome.unchanged"
            )
            return lambda: EvidenceFilesOutcomeV1(lines=(tr(key, record=short_identity(result.record.evidence_id)),))

        self._open_write(
            lambda: tr("tui.ledger.evidence_files.records.update_title"), review, submit, destructive=False
        )

    def _stage_remove(self) -> None:
        record = self.selected
        if self.busy or record is None:
            self.refuse(tr("tui.ledger.evidence_files.records.choose_record"))
            return
        request = LedgerEvidenceRemoveRequest(profile_id=self.doors.profile_id, evidence_id=record.evidence_id)
        file_name = self._file_name(record.evidence_id)

        def review() -> tuple[str, ...]:
            return (
                tr(
                    "tui.ledger.evidence_files.records.stage.remove",
                    record=short_identity(record.evidence_id),
                    file=file_name,
                    supplier=shown(record.supplier),
                    number=shown(record.invoice_number),
                ),
            )

        doors = self.doors

        async def submit() -> EvidenceFilesWordingV1:
            result = await doors.remove(request)
            removed = short_identity(result.record.evidence_id)
            return lambda: EvidenceFilesOutcomeV1(
                lines=(tr("tui.ledger.evidence_files.records.outcome.removed", record=removed),)
            )

        self.selected_id = None
        self._open_write(lambda: tr("tui.ledger.evidence_files.records.remove_title"), review, submit, destructive=True)

    def _open_write(
        self,
        title: Callable[[], str],
        review: EvidenceFilesReviewV1,
        submit: EvidenceFilesSubmitV1,
        *,
        destructive: bool,
    ) -> None:
        replace_workspace_body(
            self.app,
            LedgerEvidenceFilesWriteScreen(
                self.controller,
                title=title,
                review=review,
                destructive=destructive,
                submit=submit,
                origin=self._origin(self.selected_id),
                origin_area=self.back_area,
            ),
        )

    def _open_review(self) -> None:
        if self.busy or self.selected is None:
            self.refuse(tr("tui.ledger.evidence_files.records.choose_record"))
            return
        screen = LedgerEvidenceFilesReviewScreen(self.controller, self.doors, reference=self.selected.evidence_id)
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)

    def _set_selected_controls(self) -> None:
        chosen = self.selected is not None
        for field in _EDITABLE_FIELDS:
            self.query_one(f"#{_input_id(field)}", Input).disabled = not chosen
        for button_id in _STAGE_BUTTONS:
            self.query_one(f"#{button_id}", Button).disabled = not chosen

    def _forget_selection(self) -> None:
        self.selected_id = None
        self.selected = None
        self.query_one("#evidence-files-detail", Static).update("")
        for field in _EDITABLE_FIELDS:
            self.query_one(f"#{_input_id(field)}", Input).value = ""
        self._set_selected_controls()

    @override
    def clear_private_view(self) -> None:
        self.records.clear()
        self._forget_selection()
        self._paint_records()


__all__ = ["LedgerEvidenceFilesRecordsScreen", "evidence_field_value"]
