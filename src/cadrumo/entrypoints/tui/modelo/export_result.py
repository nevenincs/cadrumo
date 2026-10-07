"""The facts one finished Modelo export states, shown before the workspace moves on.

Every value is copied from the export's public result; nothing here classifies
or recomputes. The three facts an operator has to weigh before relying on the
file -- what it is worth as evidence, whether its completeness was verified,
and the grade of the software identity in its header -- are rows of the table,
and each one that limits the file is repeated as a warning above it, so an
incomplete or development-grade export never reads as a finished one.

A result that could not be read is said to be unreadable. Showing an empty
table instead would leave the three facts looking settled when nobody stated
them.
"""

from __future__ import annotations

from typing import ClassVar, Final, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ....application.export.calculation_review_xlsx_operation import CalculationReviewXlsxResult
from ....application.modelo.export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
)
from ....core.i18n.render import tr
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.presentation import NoticePresentation
from ....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable, NoticeBand

_EXPORT_RESULT_CSS = tokenised("""
ModeloExportResultScreen { align: center middle; }
#modelo-export-result-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: $cadrumo-modal-width;
    height: $cadrumo-modal-height;
}
#modelo-export-result-content { height: 1fr; }
#modelo-export-result-title { text-style: bold; margin: $cadrumo-space-0; }
#modelo-export-result-actions { height: auto; align-horizontal: right; margin-top: $cadrumo-stack; }
""")

#: The artefacts an export can publish, each in the operator's words. Every
#: member of the closed axis appears, so an artefact the product can publish is
#: never offered or stated as a bare token. The export control offers these and
#: the statement names the one that was published with the same words.
EXPORT_ARTEFACT_LOCALE_KEYS: Final[dict[ModeloExportArtefact, str]] = {
    ModeloExportArtefact.FICHERO_BOE: "tui.modelo.export.artefact.fichero_boe",
    ModeloExportArtefact.CALCULATION_REPORT_CSV: "tui.modelo.export.artefact.calculation_report_csv",
    ModeloExportArtefact.CALCULATION_REPORT_PDF: "tui.modelo.export.artefact.calculation_report_pdf",
    ModeloExportArtefact.CALCULATION_REVIEW_XLSX: "tui.modelo.export.artefact.calculation_review_xlsx",
}
#: Each evidence status in the operator's words. Every member appears, so a
#: status the export can state is never shown as a bare token.
EXPORT_EVIDENCE_STATUS_LOCALE_KEYS: Final[dict[ModeloExportEvidenceStatus, str]] = {
    ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE: (
        "tui.modelo.export.result.evidence_status.local_export_not_official_aeat_filing_evidence"
    ),
    ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE: (
        "tui.modelo.export.result.evidence_status.local_calculation_report_not_official_aeat_filing_evidence"
    ),
}
EXPORT_COMPLETENESS_LOCALE_KEYS: Final[dict[ModeloExportCompleteness, str]] = {
    ModeloExportCompleteness.UNVERIFIED: "tui.modelo.export.result.completeness.unverified",
    ModeloExportCompleteness.NOT_FLAGGED: "tui.modelo.export.result.completeness.not_flagged",
    ModeloExportCompleteness.NOT_ASSESSED: "tui.modelo.export.result.completeness.not_assessed",
}
#: ``None`` is the result's own answer that the layout reserves no identity
#: slot, so it has a label of its own rather than an empty cell.
SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS: Final[dict[AeatSoftwareIdentityGrade | None, str]] = {
    AeatSoftwareIdentityGrade.REVIEWED: "tui.modelo.export.result.software_identity_grade.reviewed",
    AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK: "tui.modelo.export.result.software_identity_grade.development_mock",
    None: "tui.modelo.export.result.software_identity_grade.none",
}
#: The table rows and their labels, in reading order: what was exported, what
#: it is worth, where it is.
EXPORT_RESULT_ROW_LOCALE_KEYS: Final[dict[str, str]] = {
    "artefact": "tui.modelo.export.result.label.artefact",
    "export_format": "tui.modelo.export.result.label.export_format",
    "software_identity_grade": "tui.modelo.export.result.label.software_identity_grade",
    "evidence_status": "tui.modelo.export.result.label.evidence_status",
    "completeness": "tui.modelo.export.result.label.completeness",
    "output_path": "tui.modelo.export.result.label.output_path",
    "byte_size": "tui.modelo.export.result.label.byte_size",
}
#: Traceability remains available through the explicit technical-details control.
EXPORT_RESULT_TECHNICAL_ROW_LOCALE_KEYS: Final[dict[str, str]] = {
    "calculation_revision_id": "tui.modelo.export.result.label.calculation_revision_id",
    "file_sha256": "tui.modelo.export.result.label.file_sha256",
}


def export_result_values(result: ModeloExportPublicResultV3 | CalculationReviewXlsxResult) -> dict[str, str]:
    """Return each row's displayed value, copied from the result and named in the operator's words."""
    if isinstance(result, CalculationReviewXlsxResult):
        return {
            "calculation_revision_id": result.calculation_revision_id,
            "artefact": tr(EXPORT_ARTEFACT_LOCALE_KEYS[ModeloExportArtefact.CALCULATION_REVIEW_XLSX]),
            "export_format": f"XLSX · {result.title}",
            "software_identity_grade": tr(SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS[None]),
            "evidence_status": tr(
                EXPORT_EVIDENCE_STATUS_LOCALE_KEYS[
                    ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
                ]
            ),
            "completeness": tr(f"application.storage.calc_sheets.review.labels.status_{result.review_status.value}"),
            "output_path": result.output_path,
            "byte_size": str(result.byte_size),
            "file_sha256": result.file_sha256,
        }
    return {
        "calculation_revision_id": result.calculation_revision_id,
        "artefact": tr(EXPORT_ARTEFACT_LOCALE_KEYS[result.artefact]),
        "export_format": result.export_format,
        "software_identity_grade": tr(SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS[result.software_identity_grade]),
        "evidence_status": tr(EXPORT_EVIDENCE_STATUS_LOCALE_KEYS[result.evidence_status]),
        "completeness": tr(EXPORT_COMPLETENESS_LOCALE_KEYS[result.completeness]),
        "output_path": result.output_path,
        "byte_size": str(result.byte_size),
        "file_sha256": result.file_sha256,
    }


def export_result_warnings(
    result: ModeloExportPublicResultV3 | CalculationReviewXlsxResult | None,
) -> tuple[NoticePresentation, ...]:
    """Return every limit the result states on the file, most fundamental first.

    No export is official AEAT evidence, so that warning is always present. The
    development identity and an unverified completeness are added only when the
    result states them.
    """
    if result is None:
        return (NoticePresentation(severity="warning", message=tr("tui.modelo.export.result.unavailable")),)
    warnings = [NoticePresentation(severity="warning", message=tr("tui.modelo.export.result.warning.not_official"))]
    if isinstance(result, CalculationReviewXlsxResult):
        warnings.append(
            NoticePresentation(
                severity="warning",
                message=tr(f"application.storage.calc_sheets.review.labels.status_{result.review_status.value}"),
            )
        )
        return tuple(warnings)
    if result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK:
        # A report carries no header of its own: the grade is the one the
        # filing file for its modelo would stamp, and the warning says so.
        warnings.append(
            NoticePresentation(
                severity="warning",
                message=tr("tui.modelo.export.result.warning.development_software_identity")
                if result.artefact is ModeloExportArtefact.FICHERO_BOE
                else tr("tui.modelo.export.result.warning.development_software_identity_of_filing_file"),
            )
        )
    receipt = result.fichero_boe
    if receipt is not None and receipt.domiciliation_cutoff_unverified:
        warnings.append(
            NoticePresentation(severity="warning", message=tr("tui.modelo.export.result.warning.cutoff_unverified"))
        )
    if result.completeness is ModeloExportCompleteness.UNVERIFIED:
        warnings.append(
            NoticePresentation(
                severity="warning", message=tr("tui.modelo.export.result.warning.completeness_unverified")
            )
        )
    return tuple(warnings)


class ModeloExportResultScreen(ModalScreen[None]):
    """State one finished export's facts until the operator closes them."""

    DEFAULT_CSS = _EXPORT_RESULT_CSS
    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False), Binding("t", "technical", "", show=False)]

    def __init__(self, result: ModeloExportPublicResultV3 | CalculationReviewXlsxResult | None) -> None:
        """Hold the resolved result, or ``None`` when it could not be read."""
        super().__init__()
        self._result = result
        self._technical = False

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="modelo-export-result-dialog"):
            with VerticalScroll(id="modelo-export-result-content"):
                yield Static(tr("tui.modelo.export.result.title"), id="modelo-export-result-title", markup=False)
                yield NoticeBand(export_result_warnings(self._result), id="modelo-export-result-warnings")
                if self._result is not None:
                    yield ContentDataTable[str](id="modelo-export-result-table", cursor_type="row", zebra_stripes=True)
            with Horizontal(id="modelo-export-result-actions"):
                if self._result is not None:
                    yield Button(tr("tui.modelo.workbench.issues.technical"), id="modelo-export-result-technical")
                yield Button(tr("tui.modelo.export.result.close"), id="modelo-export-result-close")

    def on_mount(self) -> None:
        """Fill the ordinary facts and make closing the primary keyboard action."""
        result = self._result
        if result is not None:
            table = self.query_one("#modelo-export-result-table", ContentDataTable)
            table.add_column(tr("flows.modelo_workspace_overview.column.field"), key="field")
            table.add_column(tr("flows.modelo_workspace_overview.column.value"), key="value")
            self._render_rows()
        self.query_one("#modelo-export-result-close", Button).focus()

    def _render_rows(self) -> None:
        result = self._result
        if result is None:
            return
        table = self.query_one("#modelo-export-result-table", ContentDataTable)
        table.clear()
        values = export_result_values(result)
        rows = dict(EXPORT_RESULT_ROW_LOCALE_KEYS)
        if self._technical:
            rows.update(EXPORT_RESULT_TECHNICAL_ROW_LOCALE_KEYS)
        for row_key, label_key in rows.items():
            table.add_row(tr(label_key), values[row_key], key=row_key)
        receipt = result.fichero_boe if isinstance(result, ModeloExportPublicResultV3) else None
        account = None if receipt is None else receipt.selected_account
        if account is not None:
            table.add_row(
                tr(f"tui.modelo.export.result.label.{account.role.value}_account"),
                account.own_account_id or tr("tui.modelo.export.result.account_in_filing"),
                key="selected_account",
            )

    def action_technical(self) -> None:
        """Reveal or hide the calculation identity and exact exported-file digest."""
        if self._result is not None:
            self._technical = not self._technical
            self._render_rows()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close the statement; the export itself is already settled."""
        if event.button.id == "modelo-export-result-close":
            self.dismiss(None)
        elif event.button.id == "modelo-export-result-technical":
            self.action_technical()

    def action_close(self) -> None:
        """Close the statement from the keyboard."""
        self.dismiss(None)


__all__ = [
    "EXPORT_ARTEFACT_LOCALE_KEYS",
    "EXPORT_COMPLETENESS_LOCALE_KEYS",
    "EXPORT_EVIDENCE_STATUS_LOCALE_KEYS",
    "EXPORT_RESULT_ROW_LOCALE_KEYS",
    "EXPORT_RESULT_TECHNICAL_ROW_LOCALE_KEYS",
    "SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS",
    "ModeloExportResultScreen",
    "export_result_values",
    "export_result_warnings",
]
