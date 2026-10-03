"""What an apply or a recalculation changed, told apart by why it changed.

After the filer's changes are applied, or the declaration is recalculated, the
workbench compares the form it showed before with the one it reads after and
lists every box that now reads differently, in three groups: the filer's own
changes, figures the calculation produced, and values that came from the
filer's records or other sources. Anything else that moved is listed as another
change, never hidden. Enter on a line goes to its box.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloWorkForm,
    address_key,
)
from .....application.modelo.work_form_service import ModeloFormValueChangeV1
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.theme import tokenised
from ...components.widgets import ContentDataTable
from .casilla_list_models import AddressKey, CasillaListEntry
from .casilla_list_values import value_text
from .dialog_width import fit_dialog_width


class ResultGroup(StrEnum):
    """Why a box reads differently after the operation."""

    YOURS = "yours"
    CALCULATED = "calculated"
    SOURCED = "sourced"
    OTHER = "other"


_CALCULATED_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.CALCULATED, ModeloFormOrigin.CALCULATION_FAILED, ModeloFormOrigin.NOT_CALCULATED_YET}
)
_SOURCED_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET}
)
_COLUMN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "why": "tui.modelo.workbench.result_diff.column.why",
    "box": "tui.modelo.workbench.review.column.box",
    "concept": "tui.modelo.workbench.review.column.concept",
    "before": "tui.modelo.workbench.review.column.before",
    "after": "tui.modelo.workbench.review.column.after",
}


@dataclass(frozen=True, slots=True)
class ResultLine:
    """One box that reads differently, with why and how it read before and after."""

    key: AddressKey
    group: ResultGroup
    box: str
    concept: str
    before: str
    after: str


def _group(change: ModeloFormValueChangeV1, yours: frozenset[AddressKey]) -> ResultGroup:
    if address_key(change.address) in yours:
        return ResultGroup.YOURS
    if change.after_origin in _CALCULATED_ORIGINS:
        return ResultGroup.CALCULATED
    if change.after_origin in _SOURCED_ORIGINS:
        return ResultGroup.SOURCED
    return ResultGroup.OTHER


def _shown(
    field: ModeloFormField | None, value: ModeloFormScalar, origin: ModeloFormOrigin | None, language: OutputLanguage
) -> str:
    if field is None or origin is None:
        return tr("tui.modelo.workbench.result_diff.not_shown")
    return value_text(CasillaListEntry(field.model_copy(update={"value": value, "origin": origin})), language)


def result_lines(
    changes: tuple[ModeloFormValueChangeV1, ...],
    *,
    before: ModeloWorkForm,
    after: ModeloWorkForm,
    yours: frozenset[AddressKey],
    language: OutputLanguage,
) -> tuple[ResultLine, ...]:
    """Every changed box, grouped by why it changed and in reading order within each group."""
    earlier = {address_key(field.address): field for field in before.fields()}
    later = {address_key(field.address): field for field in after.fields()}
    lines = []
    for change in changes:
        key = address_key(change.address)
        lines.append(
            ResultLine(
                key=key,
                group=_group(change, yours),
                box=change.box or "·",
                concept=change.label.text,
                before=_shown(earlier.get(key), change.before, change.before_origin, language),
                after=_shown(later.get(key), change.after, change.after_origin, language),
            )
        )
    order = list(ResultGroup)
    return tuple(sorted(lines, key=lambda line: order.index(line.group)))


class WorkbenchResultScreen(ModalScreen[AddressKey | None]):
    """The boxes an apply or a recalculation changed, and why."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchResultScreen #result-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchResultScreen #result-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchResultScreen.-narrow #result-panel {
            width: 100%;
        }
        WorkbenchResultScreen #result-title {
            text-style: bold;
            color: $primary;
        }
        WorkbenchResultScreen #result-summary {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchResultScreen #result-table {
            height: 1fr;
        }
        WorkbenchResultScreen #result-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, lines: tuple[ResultLine, ...]) -> None:
        """Hold the changed boxes, grouped."""
        super().__init__()
        self._lines = lines

    @override
    def compose(self) -> ComposeResult:
        counts = {group: sum(1 for line in self._lines if line.group is group) for group in ResultGroup}
        summary = " · ".join(
            tr(f"tui.modelo.workbench.result_diff.count.{group.value}", count=count)
            for group, count in counts.items()
            if count
        )
        with Container(id="result-backdrop"), Vertical(id="result-panel"):
            yield Static(
                tr("tui.modelo.workbench.result_diff.title", count=len(self._lines)), id="result-title", markup=False
            )
            yield Static(summary, id="result-summary", markup=False)
            yield ContentDataTable[str](id="result-table", cursor_type="row", zebra_stripes=True)
            with Horizontal(id="result-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="result-close", variant="primary")

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """List the changed boxes and give the table the focus."""
        fit_dialog_width(self, self.app.size.width)
        table = self.query_one("#result-table", ContentDataTable)
        for key, label_key in _COLUMN_LOCALE_KEYS.items():
            table.add_column(tr(label_key), key=key)
        for index, line in enumerate(self._lines):
            table.add_row(
                tr(f"tui.modelo.workbench.result_diff.group.{line.group.value}"),
                line.box,
                line.concept,
                line.before,
                line.after,
                key=f"line-{index}",
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Go to the box of the chosen line."""
        row = str(event.row_key.value or "")
        index = row.removeprefix("line-")
        if index.isdigit() and int(index) < len(self._lines):
            self.dismiss(self._lines[int(index)].key)

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Return to the workbench where it was."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Return to the workbench where it was."""
        self.dismiss(None)


__all__ = ["ResultGroup", "ResultLine", "WorkbenchResultScreen", "result_lines"]
