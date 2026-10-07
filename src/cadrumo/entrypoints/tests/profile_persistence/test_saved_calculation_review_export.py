"""Actual calculation-save custody and local review export with original form geometry."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from openpyxl import load_workbook
from pydantic import BaseModel, ValidationError

from ....adapters.outbound.google.artifact_admission import GoogleArtifactAdmission
from ....adapters.outbound.google.artifact_receipt_store import GoogleArtifactReceiptStore
from ....adapters.outbound.google.calc_sheets_apply import publish_review_plan
from ....adapters.outbound.google.managed_artifacts import ManagedGoogleArtifacts
from ....adapters.outbound.google.root_folder import ensure_root_folder
from ....adapters.outbound.google.tests.drive_files_server import drive_files_endpoint
from ....adapters.outbound.google.tests.review_sheets_server import review_sheets_endpoint
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.export.calculation_review_xlsx_operation import (
    CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
    CalculationReviewXlsxExecutionResult,
    CalculationReviewXlsxExecutor,
    CalculationReviewXlsxRequest,
    build_calculation_review_xlsx_definition,
    build_calculation_review_xlsx_registration,
)
from ....application.export.publication_receipt import PublicationReceipt, PublicationState
from ....application.export.review_snapshot import ReviewSnapshot
from ....application.modelo.calculation_actions import calculate_modelo_revision
from ....application.modelo.export_sink import ModeloExportOutputPathError
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.registry import OperationRegistry
from ....application.storage.calc_sheets.records import TabName
from ....application.storage.calc_sheets.review_labels import ReviewWorkbookLabels
from ....application.storage.calc_sheets.review_workbook import build_review_workbook
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.external_constants import OutputLanguage
from ....core.hashing import content_hash_hex
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.modelos.calculation_revision import CalculationRevision
from ...calculation_review_snapshot_composition import load_calculation_review_snapshot
from ...calculation_review_xlsx_operation_composition import build_calculation_review_xlsx_ports
from .file_flow_test_support import (
    DEFAULT_130_BINDING_VALUES,
    M130_INCOME_CASILLA,
    T1,
    T2,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _calculate(repos: Repos, *, income: str = "1000") -> CalculationRevision:
    units, calculations, _, _, events = repos
    unit = seed_work_unit(units)
    with calculation_ports_for_test(
        bucket_id=unit.bucket_id,
        work_unit_repository=units,
        calculation_repository=calculations,
        bucket_event_repository=events,
    ) as ports:
        return calculate_modelo_revision(
            unit.work_unit_id,
            casilla_inputs={M130_INCOME_CASILLA: Decimal(income)},
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=ports,
            clock=T1 if income == "1000" else T2,
        )


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        assert phase == CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        self.value = value
        assert written_at.tzinfo is not None
        return "d" * 64


class _Fence:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


def _context(request: OperationRequest[BaseModel], operation: PinnedAuthorityOperation):
    events, operands = _Events(), _Operands()
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            authority_operation=operation,
            events=events,
            operands=operands,
            cancellation=_Fence(),
        ),
    )
    return context, events, operands


def test_new_calculation_retains_original_rendering_and_exports_its_saved_form(
    repos: Repos, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = _calculate(repos)
    rendering = revision.rendering_snapshot
    assert rendering is not None
    assert rendering.registry_snapshot.snapshot_ref == revision.registry_snapshot_ref
    assert rendering.registry_digest == content_hash_hex(rendering.registry_snapshot.model_dump(mode="json"))
    with bundled_indexed_authority().operation() as operation:
        stored = repos[1].load(operation=operation).get(revision.calculation_revision_id)
        assert stored is not None and stored.rendering_snapshot is not None
        assert stored.rendering_snapshot.model_dump(mode="json") == rendering.model_dump(mode="json")

        def refuse_current_template(*args: object, **kwargs: object) -> None:
            pytest.fail("saved form export must not resolve a current authority template")

        monkeypatch.setattr(PinnedAuthorityOperation, "snapshot", refuse_current_template)
        profile_id = UUID(repos[0].bucket_id)
        baseline = load_calculation_review_snapshot(
            revision.calculation_revision_id, profile_id=profile_id, operation=operation
        )
        assert baseline.saved_form is not None
        with pytest.raises(ProfileAccessRefusedError):
            load_calculation_review_snapshot(
                revision.calculation_revision_id,
                profile_id=profile_id,
                operation=operation,
                filing_record_id="f" * 64,
            )
        assert ReviewSnapshot.model_validate_json(baseline.model_dump_json()).model_dump(
            mode="json"
        ) == baseline.model_dump(mode="json")
        payload = CalculationReviewXlsxRequest(
            profile_id=profile_id,
            calculation_revision_id=revision.calculation_revision_id,
            output_path=str(tmp_path / "borrador-130.xlsx"),
        )
        request = OperationRequest[BaseModel](
            definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=payload,
        )
        context, events, operands = _context(request, operation)
        executor = CalculationReviewXlsxExecutor(build_calculation_review_xlsx_ports)
        asyncio.run(executor.execute(request, context))
        assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
        assert isinstance(operands.value, CalculationReviewXlsxExecutionResult)
        assert operands.value.result.snapshot_digest == baseline.snapshot_digest
        assert "Modelo 130 · 2026 · 1T · Borrador" in operands.value.result.title
        workbook = load_workbook(BytesIO(Path(payload.output_path).read_bytes()), data_only=False)
        assert TabName.FORM.value in workbook.sheetnames
        values = [cell.value for row in workbook[TabName.CALCULOS.value] for cell in row]
        assert 1000 in values
        assert not any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row)
        assert not any(finding.code == "review.saved_form_layout_unavailable" for finding in baseline.findings)
        assert 1000 in [cell.value for row in workbook[TabName.FORM.value] for cell in row]
        # The registered operation remains coherent; no provider is needed to enroll it.
        definition = build_calculation_review_xlsx_definition(build_calculation_review_xlsx_ports)
        OperationRegistry(
            definitions=(definition,), public_registrations=(build_calculation_review_xlsx_registration(definition),)
        )
        prior_bytes = Path(payload.output_path).read_bytes()
        with pytest.raises(ModeloExportOutputPathError):
            asyncio.run(executor.execute(request, context))
        assert Path(payload.output_path).read_bytes() == prior_bytes


def test_new_current_calculation_does_not_replace_historical_export_values(repos: Repos) -> None:
    first = _calculate(repos)
    _calculate(repos, income="2000")
    with bundled_indexed_authority().operation() as operation:
        baseline = load_calculation_review_snapshot(
            first.calculation_revision_id, profile_id=UUID(repos[0].bucket_id), operation=operation
        )
    assert baseline.calculation_lifecycle is not None and not baseline.calculation_lifecycle.is_current_calculation
    plan = build_review_workbook(
        baseline,
        publication_id=UUID(int=1),
        exported_at=datetime(2026, 10, 7, tzinfo=UTC),
        label=ReviewWorkbookLabels(OutputLanguage.ES),
    )
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert Decimal("1000") in form_values and Decimal("2000") not in form_values
    assert not plan.formula_cells


def test_real_saved_form_uses_same_native_transport_plan_and_preserves_notes(repos: Repos, tmp_path: Path) -> None:
    revision = _calculate(repos)
    profile_id = UUID(repos[0].bucket_id)
    with bundled_indexed_authority().operation() as operation:
        baseline = load_calculation_review_snapshot(
            revision.calculation_revision_id, profile_id=profile_id, operation=operation
        )
    plan = build_review_workbook(
        baseline,
        publication_id=UUID(int=123),
        exported_at=datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
        label=ReviewWorkbookLabels(OutputLanguage.ES),
    )
    assert baseline.saved_form is not None and not plan.formula_cells
    with (
        isolated_runtime_profile(tmp_path=tmp_path / "native-receipts", bucket_id=str(profile_id)) as profile,
        drive_files_endpoint() as drive,
        review_sheets_endpoint() as sheets,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=profile_id)
        root_id = ensure_root_folder(drive.service, profile=str(profile_id), receipts=receipts)
        root = receipts.load(root_id)
        assert root is not None
        artifacts = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(drive.service, profile_id=profile_id, root=root, receipts=receipts),
            receipts=receipts,
        )
        publication = PublicationReceipt(
            publication_id=plan.metadata.publication_id,
            profile_id=profile_id,
            root=root,
            snapshot_digest=baseline.snapshot_digest,
        )
        result = publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service)
        assert result.state is PublicationState.PUBLISHED
        identifier = result.artifacts[0].artifact_id
        assert drive.created_bodies[-1]["mimeType"] == "application/vnd.google-apps.spreadsheet"
        assert drive.created_bodies[-1]["parents"] == [root_id]
        assert drive.created_bodies[-1]["name"] == plan.metadata.document_title
        assert TabName.FORM.value in sheets.tabs[identifier]
        source = next(
            cell for cell in plan.value_cells if cell.address.tab is TabName.FORM and cell.value == Decimal("1000")
        )
        assert sheets.cells[identifier][(source.address.tab.value, source.address.row, source.address.column)] == 1000
        sheets.cells[identifier][(TabName.ENTRADAS.value, 5, 2)] = "Review note"
        sheets.calls.clear()
        assert publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets.service) == result
        assert not sheets.calls
        assert sheets.cells[identifier][(TabName.ENTRADAS.value, 5, 2)] == "Review note"


def test_original_rendering_is_identity_bound_and_legacy_revision_remains_readable(repos: Repos) -> None:
    revision = _calculate(repos)
    wire = revision.model_dump(mode="json", context={"secure_calculation_revision": True})
    changed = json.loads(json.dumps(wire))
    changed["rendering_snapshot"]["authority_generation"] = "f" * 64
    with pytest.raises(ValidationError, match=r"derived|identity"):
        CalculationRevision.model_validate_json(json.dumps(changed), context={"secure_calculation_revision": True})
    changed = json.loads(json.dumps(wire))
    changed["rendering_snapshot"]["registry_digest"] = "f" * 64
    with pytest.raises(ValidationError, match="digest"):
        CalculationRevision.model_validate_json(json.dumps(changed), context={"secure_calculation_revision": True})
