"""Textual proof that the export statement shows what the export result says, limits first.

Each result here is the export service's own receipt passed through the
registered public projection, exactly as a settled operation's result is, so
the screen is driven by the shape it meets in production. The receipts are
synthetic: they name no taxpayer, and their digests are placeholders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import pytest
from pydantic import ValidationError
from textual.app import App
from textual.widgets import Button, Static

from .....adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from .....adapters.persistence.profile.review_package_signing import (
    build_review_package_signing_keypair_capability,
)
from .....application.modelo.calculation_report_export import ModeloCalculationReportResult
from .....application.modelo.export import ModeloExportResult
from .....application.modelo.export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
)
from .....application.modelo.operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    ModeloExportSettledResult,
    build_modelo_export_definition,
    build_modelo_export_registration,
)
from .....application.operations.models import OperationIdentity, OperationTerminalReceipt
from .....core.calculation_report_format import CalculationReportDocumentFormat
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.modelo_export_artefact import ModeloExportArtefact
from .....core.operations import OperationEffect, OperationTerminalCondition
from .....core.period import Period
from .....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ....adapter_composition import build_modelo_export_ports
from ...components.widgets import ContentDataTable
from ..export_result import (
    EXPORT_ARTEFACT_LOCALE_KEYS,
    EXPORT_COMPLETENESS_LOCALE_KEYS,
    EXPORT_EVIDENCE_STATUS_LOCALE_KEYS,
    EXPORT_RESULT_ROW_LOCALE_KEYS,
    EXPORT_RESULT_TECHNICAL_ROW_LOCALE_KEYS,
    SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS,
    ModeloExportResultScreen,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REVISION_ID = "a" * 64
_FILE_SHA256 = "c" * 64


def _publicly_projected(settled: ModeloExportSettledResult) -> ModeloExportPublicResultV3:
    """Project a settled receipt through the projector the export registration declares."""
    registration = build_modelo_export_registration(
        build_modelo_export_definition(
            export_ports_factory=build_modelo_export_ports,
            signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
            calculation_summary_pdf_writer=write_calculation_summary_pdf,
        )
    )
    projector = registration.result_projector
    assert projector is not None
    terminal = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="e" * 64, definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID, subject_ref="b" * 64
        ),
        revision=4,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2027, 1, 20, 9, 0, tzinfo=UTC),
        result_ref="f" * 64,
    )
    projected = projector(settled, terminal)
    assert isinstance(projected, ModeloExportPublicResultV3)
    return projected


def _filing_file_receipt(
    tmp_path: Path,
    *,
    completeness_unverified: bool,
    software_identity_grade: AeatSoftwareIdentityGrade | None,
) -> ModeloExportSettledResult:
    return ModeloExportSettledResult(
        fichero_boe=ModeloExportResult(
            calculation_revision_id=_REVISION_ID,
            work_unit_id="b" * 64,
            bucket_id="bucket-operator",
            modelo="189",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            output_path=tmp_path / "modelo-189.txt",
            byte_size=500,
            file_sha256=_FILE_SHA256,
            format="fichero-boe",
            exported_at=datetime(2027, 1, 20, 9, 0, tzinfo=UTC),
            actor="operator",
            bucket_event_id="event-1",
            software_identity_grade=software_identity_grade,
            completeness_unverified=completeness_unverified,
        )
    )


def _report_receipt(
    tmp_path: Path,
    *,
    document_format: CalculationReportDocumentFormat = CalculationReportDocumentFormat.CSV,
) -> ModeloExportSettledResult:
    return ModeloExportSettledResult(
        calculation_report=ModeloCalculationReportResult(
            calculation_revision_id=_REVISION_ID,
            work_unit_id="b" * 64,
            verification_report_id=None,
            filing_record_id=None,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            document_format=document_format,
            report_language=OutputLanguage.ES,
            output_path=tmp_path / f"modelo-303-report.{document_format.value}",
            byte_size=2048,
            file_sha256=_FILE_SHA256,
            report_sha256="d" * 64,
            row_count=12,
            software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK,
            local_calculation_notice="Local calculation report.",
        )
    )


def _table_values(app: App[None]) -> dict[str, str]:
    table = app.screen.query_one("#modelo-export-result-table", ContentDataTable)
    return {str(row_key.value): str(table.get_row(row_key)[1]) for row_key in table.rows}


def _warnings(app: App[None]) -> str:
    return "\n".join(str(item.content) for item in app.screen.query_one("#modelo-export-result-warnings").query(Static))


@pytest.mark.asyncio
async def test_an_export_whose_completeness_is_unverified_says_so_in_its_facts_and_warnings(tmp_path: Path) -> None:
    """A filing file the export could not completeness-verify is never shown as finished."""
    result = _publicly_projected(
        _filing_file_receipt(tmp_path, completeness_unverified=True, software_identity_grade=None)
    )
    app = App[None]()
    closed: list[None] = []

    async with app.run_test() as pilot:
        await app.push_screen(ModeloExportResultScreen(result), closed.append)
        await pilot.pause()

        assert _table_values(app) == {
            "artefact": tr("tui.modelo.export.artefact.fichero_boe"),
            "export_format": "fichero-boe",
            "software_identity_grade": tr("tui.modelo.export.result.software_identity_grade.none"),
            "evidence_status": tr(
                "tui.modelo.export.result.evidence_status.local_export_not_official_aeat_filing_evidence"
            ),
            "completeness": tr("tui.modelo.export.result.completeness.unverified"),
            "output_path": str(tmp_path / "modelo-189.txt"),
            "byte_size": "500",
        }
        warnings = _warnings(app)
        assert tr("tui.modelo.export.result.warning.not_official") in warnings
        assert tr("tui.modelo.export.result.warning.completeness_unverified") in warnings
        assert tr("tui.modelo.export.result.warning.development_software_identity") not in warnings

        app.screen.query_one("#modelo-export-result-close", Button).press()
        await pilot.pause()

    assert closed == [None]


@pytest.mark.asyncio
async def test_a_development_identity_is_warned_and_a_verified_file_raises_no_completeness_warning(
    tmp_path: Path,
) -> None:
    """The development grade is stated twice: as the row's value and as a warning."""
    result = _publicly_projected(
        _filing_file_receipt(
            tmp_path,
            completeness_unverified=False,
            software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK,
        )
    )
    app = App[None]()

    async with app.run_test() as pilot:
        await app.push_screen(ModeloExportResultScreen(result))
        await pilot.pause()

        values = _table_values(app)
        assert values["software_identity_grade"] == tr(
            "tui.modelo.export.result.software_identity_grade.development_mock"
        )
        assert values["completeness"] == tr("tui.modelo.export.result.completeness.not_flagged")
        warnings = _warnings(app)
        assert tr("tui.modelo.export.result.warning.development_software_identity") in warnings
        assert tr("tui.modelo.export.result.warning.completeness_unverified") not in warnings

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ModeloExportResultScreen)


@pytest.mark.asyncio
async def test_a_calculation_report_claims_no_completeness_and_names_the_filing_file_identity(
    tmp_path: Path,
) -> None:
    """A report is not a filing file: its completeness is not assessed and its grade is the filing file's."""
    result = _publicly_projected(_report_receipt(tmp_path))
    app = App[None]()

    assert result.artefact is ModeloExportArtefact.CALCULATION_REPORT_CSV

    async with app.run_test() as pilot:
        await app.push_screen(ModeloExportResultScreen(result))
        await pilot.pause()

        values = _table_values(app)
        assert values["export_format"] == "csv"
        assert values["evidence_status"] == tr(
            "tui.modelo.export.result.evidence_status.local_calculation_report_not_official_aeat_filing_evidence"
        )
        assert values["completeness"] == tr("tui.modelo.export.result.completeness.not_assessed")
        warnings = _warnings(app)
        assert tr("tui.modelo.export.result.warning.development_software_identity_of_filing_file") in warnings
        assert tr("tui.modelo.export.result.warning.development_software_identity") not in warnings


@pytest.mark.asyncio
async def test_a_calculation_summary_pdf_is_named_as_that_artefact_and_claims_what_a_report_claims(
    tmp_path: Path,
) -> None:
    """The summary PDF has its own artefact label and format, and the same limits as any calculation report."""
    result = _publicly_projected(_report_receipt(tmp_path, document_format=CalculationReportDocumentFormat.PDF))
    app = App[None]()

    assert result.artefact is ModeloExportArtefact.CALCULATION_REPORT_PDF

    async with app.run_test() as pilot:
        await app.push_screen(ModeloExportResultScreen(result))
        await pilot.pause()

        assert _table_values(app) == {
            "artefact": tr("tui.modelo.export.artefact.calculation_report_pdf"),
            "export_format": "pdf",
            "software_identity_grade": tr("tui.modelo.export.result.software_identity_grade.development_mock"),
            "evidence_status": tr(
                "tui.modelo.export.result.evidence_status.local_calculation_report_not_official_aeat_filing_evidence"
            ),
            "completeness": tr("tui.modelo.export.result.completeness.not_assessed"),
            "output_path": str(tmp_path / "modelo-303-report.pdf"),
            "byte_size": "2048",
        }
        assert tr("tui.modelo.export.artefact.calculation_report_pdf") != tr(
            "tui.modelo.export.artefact.calculation_report_csv"
        )
        warnings = _warnings(app)
        assert tr("tui.modelo.export.result.warning.not_official") in warnings
        assert tr("tui.modelo.export.result.warning.development_software_identity_of_filing_file") in warnings


@pytest.mark.asyncio
async def test_an_unreadable_result_is_stated_rather_than_shown_as_an_empty_table() -> None:
    """Without a result the three facts are unknown, and the screen says exactly that."""
    app = App[None]()

    async with app.run_test() as pilot:
        await app.push_screen(ModeloExportResultScreen(None))
        await pilot.pause()

        assert not app.screen.query("#modelo-export-result-table")
        warnings = [str(item.content) for item in app.screen.query_one("#modelo-export-result-warnings").query(Static)]
        assert len(warnings) == 1
        assert tr("tui.modelo.export.result.unavailable") in warnings[0]
        assert str(app.screen.query_one("#modelo-export-result-title", Static).content) == tr(
            "tui.modelo.export.result.title"
        )
        await pilot.press("t")
        assert not app.screen.query("#modelo-export-result-table")


@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("report", [False, True], ids=["filing-file", "report"])
async def test_export_identifiers_are_revealed_only_by_deliberate_technical_details(
    tmp_path: Path, language: OutputLanguage, report: bool
) -> None:
    """Keep ordinary export facts visible while both controls toggle exact traceability."""
    result = _publicly_projected(
        _report_receipt(tmp_path)
        if report
        else _filing_file_receipt(tmp_path, completeness_unverified=False, software_identity_grade=None)
    )
    with override_settings(cadrumo_output_language=language.value):
        app = App[None]()
        async with app.run_test() as pilot:
            await app.push_screen(ModeloExportResultScreen(result))
            await pilot.pause()
            ordinary = _table_values(app)
            assert "calculation_revision_id" not in ordinary and "file_sha256" not in ordinary
            assert _REVISION_ID not in ordinary.values() and _FILE_SHA256 not in ordinary.values()
            assert ordinary["output_path"] == result.output_path
            assert ordinary["completeness"] == tr(EXPORT_COMPLETENESS_LOCALE_KEYS[result.completeness])
            await pilot.press("t")
            await pilot.pause()
            detailed = _table_values(app)
            assert detailed["calculation_revision_id"] == _REVISION_ID
            assert detailed["file_sha256"] == _FILE_SHA256
            assert {key: detailed[key] for key in ordinary} == ordinary
            app.screen.query_one("#modelo-export-result-technical", Button).press()
            await pilot.pause()
            assert _table_values(app) == ordinary


def test_a_settled_export_names_exactly_one_receipt(tmp_path: Path) -> None:
    """A settlement with no receipt, or with both, is refused rather than projected."""
    filing = _filing_file_receipt(tmp_path, completeness_unverified=False, software_identity_grade=None).fichero_boe
    report = _report_receipt(tmp_path).calculation_report

    with pytest.raises(ValidationError, match="exactly one receipt"):
        ModeloExportSettledResult()
    with pytest.raises(ValidationError, match="exactly one receipt"):
        ModeloExportSettledResult(fichero_boe=filing, calculation_report=report)


@pytest.mark.parametrize(
    ("members", "keys"),
    [
        (set(ModeloExportArtefact), EXPORT_ARTEFACT_LOCALE_KEYS),
        (set(ModeloExportEvidenceStatus), EXPORT_EVIDENCE_STATUS_LOCALE_KEYS),
        (set(ModeloExportCompleteness), EXPORT_COMPLETENESS_LOCALE_KEYS),
        ({*AeatSoftwareIdentityGrade, None}, SOFTWARE_IDENTITY_GRADE_LOCALE_KEYS),
    ],
)
def test_every_stated_fact_has_a_label(members: set[Enum | None], keys: dict[object, str]) -> None:
    """A member added to a result vocabulary must be named, not shown as a bare token."""
    assert set(keys) == members


def test_every_public_result_fact_has_a_row() -> None:
    """Each field the result states about the file is a row.

    The version and handoff flag are not facts about the file, and the carried
    artefact receipts are the complete records the rows above summarise.
    """
    stated = set(ModeloExportPublicResultV3.model_fields) - {
        "result_version",
        "handoff_required",
        "fichero_boe",
        "calculation_report",
    }

    ordinary = set(EXPORT_RESULT_ROW_LOCALE_KEYS)
    technical = set(EXPORT_RESULT_TECHNICAL_ROW_LOCALE_KEYS)
    assert ordinary.isdisjoint(technical)
    assert ordinary | technical == stated
