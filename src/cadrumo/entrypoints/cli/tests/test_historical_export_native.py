"""Exact historical filing selection reaches the registered worker and materializer."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import openpyxl
import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.user_profile.login_session import resolve_login_target
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....tests.cli_envelope import unwrap_schema_envelope
from ...tests.modelo_operation_test_support import seeded_modelo_verification_report
from .review_export_native_support import invoke_native_review, native_review_profile
from .runtime_profile_cli_fixture import NativeCliProfileFixture

__all__ = ["native_review_profile"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_selected_historical_filing_exports_its_retained_calculation(
    tmp_path: Path, native_review_profile: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation
) -> None:
    assert native_review_profile.label is not None
    profile_id = UUID(resolve_login_target(native_review_profile.label).bucket_id)
    revision_id, _ = seeded_modelo_verification_report(profile_id, operation=operation)
    calculations = CalculationRevisionCatalogueRepository()
    catalogue = calculations.load(operation=operation)
    revision = catalogue.get(revision_id)
    assert revision is not None
    unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert unit is not None
    now = datetime.now(UTC)
    actor = "synthetic-history-test"
    filed = revision.model_copy(
        update={"state": CalculationRevisionState.PRESENTADO, "filed_at": now, "filed_by": actor}
    )
    calculations.save(CalculationRevisionCatalogue(revisions={**catalogue.revisions, revision_id: filed}))
    filing_id = derive_filing_record_id(
        work_unit_id=unit.work_unit_id, calculation_revision_id=revision_id, filed_by=actor
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=unit.bucket_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        filed_at=now,
        filed_by=actor,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    records = ModeloRecordCatalogueRepository()
    current = records.load()
    records.save(ModeloRecordCatalogue(records={**current.records, filing_id: record}))
    output = tmp_path / "historical.xlsx"
    result = invoke_native_review(
        native_review_profile,
        [
            "app",
            "modelo",
            "filing-record",
            "export",
            filing_id,
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    publication = unwrap_schema_envelope(result.output)["publication"]
    assert publication["calculation_revision_id"] == revision_id
    assert publication["calculation_state"] == CalculationRevisionState.PRESENTADO.value
    workbook = openpyxl.load_workbook(output)
    try:
        strings = [str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value is not None]
        assert revision_id in strings
        assert not any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row)
    finally:
        workbook.close()
