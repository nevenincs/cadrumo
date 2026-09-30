"""What the last verification found, in the filer's words, with a way to each box.

Verification can find things that stop a declaration from being filed and
things worth a second look, and not every finding names a box. This list shows
all of them, the ones that block filing first, so a declaration never sits at
"verify" with no reason given. Enter on a finding that names a box goes to it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from .....application.modelo.work_form_models import ModeloFormCasillaAddressV1, ModeloWorkForm, address_key
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import ModeloVerificationFindingSeverity, VerificationCompletenessStatus
from ...components.theme import tokenised
from ...components.widgets import ContentDataTable
from .casilla_list import AddressKey
from .dialog_width import fit_dialog_width

_SEVERITY_MARKS: Final[Mapping[ModeloVerificationFindingSeverity, str]] = {
    ModeloVerificationFindingSeverity.BLOCKING: "▲",
    ModeloVerificationFindingSeverity.WARNING: "!",
}
_COLUMN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "mark": "tui.modelo.workbench.issues.column.kind",
    "box": "tui.modelo.workbench.review.column.box",
    "message": "tui.modelo.workbench.issues.column.message",
}
_VERDICT_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = {
    VerificationCompletenessStatus.COMPLETE: "tui.modelo.workbench.issues.verdict.complete",
    VerificationCompletenessStatus.INCOMPLETE: "tui.modelo.workbench.issues.verdict.incomplete",
    VerificationCompletenessStatus.BLOCKED: "tui.modelo.workbench.issues.verdict.blocked",
}


@dataclass(frozen=True, slots=True)
class IssueLine:
    """One finding as the filer reads it, with the box it leads to when it names one."""

    blocking: bool
    box: str
    message: str
    key: AddressKey | None


def issue_lines(form: ModeloWorkForm) -> tuple[IssueLine, ...]:
    """The form's verification findings as lines, blocking first, each rendered in the filer's language."""
    lines = []
    for issue in form.issues:
        finding = issue.finding
        key = (
            None
            if finding.casilla_id is None
            else address_key(ModeloFormCasillaAddressV1(casilla_id=finding.casilla_id))
        )
        lines.append(
            IssueLine(
                blocking=finding.severity is ModeloVerificationFindingSeverity.BLOCKING,
                box=issue.box or "·",
                message=tr(finding.message_locale_key, **finding.message_facts),
                key=key,
            )
        )
    return tuple(lines)


def verdict_text(form: ModeloWorkForm) -> str:
    """Say what the last verification concluded, or that the calculation has not been verified."""
    if form.verification is None:
        return tr("tui.modelo.workbench.issues.verdict.none")
    return tr(_VERDICT_LOCALE_KEYS[form.verification], count=len(form.issues))


class WorkbenchIssuesScreen(ModalScreen[AddressKey | None]):
    """The findings of the declaration's last verification."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchIssuesScreen #issues-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchIssuesScreen #issues-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchIssuesScreen.-narrow #issues-panel {
            width: 100%;
        }
        WorkbenchIssuesScreen #issues-title {
            text-style: bold;
            color: $primary;
        }
        WorkbenchIssuesScreen #issues-verdict {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchIssuesScreen #issues-table {
            height: 1fr;
        }
        WorkbenchIssuesScreen #issues-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, form: ModeloWorkForm) -> None:
        """Hold the form whose verification findings are listed."""
        super().__init__()
        self._form = form
        self._lines = issue_lines(form)

    @override
    def compose(self) -> ComposeResult:
        with Container(id="issues-backdrop"), Vertical(id="issues-panel"):
            yield Static(tr("tui.modelo.workbench.issues.title"), id="issues-title", markup=False)
            yield Static(verdict_text(self._form), id="issues-verdict", markup=False)
            yield ContentDataTable[str](id="issues-table", cursor_type="row", zebra_stripes=True)
            with Horizontal(id="issues-actions"):
                yield Button(tr("tui.modelo.workbench.result_diff.close"), id="issues-close", variant="primary")

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """List the findings and give the table the focus."""
        fit_dialog_width(self, self.app.size.width)
        table = self.query_one("#issues-table", ContentDataTable)
        for key, label_key in _COLUMN_LOCALE_KEYS.items():
            table.add_column(tr(label_key), key=key)
        for index, line in enumerate(self._lines):
            mark = _SEVERITY_MARKS[
                ModeloVerificationFindingSeverity.BLOCKING
                if line.blocking
                else ModeloVerificationFindingSeverity.WARNING
            ]
            words = tr(
                "tui.modelo.workbench.issues.blocking" if line.blocking else "tui.modelo.workbench.issues.warning"
            )
            table.add_row(f"{mark} {words}", line.box, line.message, key=f"issue-{index}")
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Go to the box of the chosen finding, when it names one."""
        index = str(event.row_key.value or "").removeprefix("issue-")
        if index.isdigit() and int(index) < len(self._lines):
            key = self._lines[int(index)].key
            if key is not None:
                self.dismiss(key)

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Return to the workbench."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Return to the workbench."""
        self.dismiss(None)


__all__ = ["IssueLine", "WorkbenchIssuesScreen", "issue_lines", "verdict_text"]
