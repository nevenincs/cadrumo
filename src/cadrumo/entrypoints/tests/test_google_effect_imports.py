"""Local startup excludes Google export effects; callbacks retain their owners."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from ...adapters.outbound.storage.errors import OutboundStorageValidationError
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...application.export.google_operation import GoogleSheetsReviewPreparedPort
from ...application.export.publication_receipt import PublicationReceipt, ReadableExportAuthorization
from ...application.export.review_snapshot import ReviewSelection, ReviewSnapshot
from ...application.export.tests.review_publication_fixture import (
    EXPORTED_AT,
    PROFILE_ID,
    acceptance_authorization,
    acceptance_publication,
    acceptance_snapshot,
    completed_acceptance_receipt,
)
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...application.storage.calc_sheets.records import (
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetReviewMetadata,
)
from ...application.storage.calc_sheets.review_workbook import ReviewLabelResolver
from ...core.period import Period
from .. import google_review_operation_composition as review_composition
from .. import operation_composition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _plan() -> SheetExportPlan:
    return SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="303",
            revision_id="2026",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            engine_version="test",
            registry_sha="a" * 64,
            exported_at=EXPORTED_AT,
        ),
        guide=SheetGuideContent(title="Fixture export", paragraphs=("Synthetic forwarding fixture",)),
    )


def test_local_runtime_defers_missing_export_implementation_until_owning_callback(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[3]
    script = """
import importlib.abc
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

class MissingExportDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {
            'cadrumo.adapters.outbound.google.calc_sheets_apply',
            'cadrumo.adapters.outbound.google.managed_artifacts',
        } or fullname == 'googleapiclient' or fullname.startswith('googleapiclient.'):
            raise ModuleNotFoundError('fixture: export implementation unavailable', name=fullname)

def refuse_actions(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
        raise AssertionError('import-only test attempted an active effect')

sys.addaudithook(refuse_actions)
sys.meta_path.insert(0, MissingExportDependencies())
import cadrumo.entrypoints.runtime.main

for name in (
    'cadrumo.adapters.outbound.google.calc_sheets_apply',
    'cadrumo.adapters.outbound.google._calc_sheets_apply_values',
    'cadrumo.adapters.outbound.google._calc_sheets_apply_formatting',
    'cadrumo.adapters.outbound.google.managed_artifacts',
):
    assert name not in sys.modules, name
assert not any(name == 'googleapiclient' or name.startswith('googleapiclient.') for name in sys.modules)

from datetime import UTC, datetime
from cadrumo.application.storage.calc_sheets.records import SheetExportMetadata, SheetExportPlan, SheetGuideContent
from cadrumo.core.period import Period
from cadrumo.entrypoints import operation_composition

operation_composition.resolve_drive_root_folder_id = lambda **kwargs: 'fixture-root'
operation_composition.build_google_credentials = lambda **kwargs: object()
prepared = operation_composition._google_sheets_export_prepare_port()('fixture-profile')
plan = SheetExportPlan(
    metadata=SheetExportMetadata(
        modelo_id='303', revision_id='2026', filing_year=2026,
        period=Period.from_year_and_code(2026, '1T'), engine_version='test', registry_sha='a' * 64,
        exported_at=datetime(2026, 10, 5, 14, tzinfo=UTC),
    ),
    guide=SheetGuideContent(title='Fixture export', paragraphs=('Synthetic dependency fixture',)),
)
try:
    prepared.execute(plan, True)
except ModuleNotFoundError as error:
    assert error.name == 'cadrumo.adapters.outbound.google.calc_sheets_apply'
else:
    raise AssertionError('missing export implementation was reported as success')
assert not Path(sys.argv[2]).exists()
"""
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
        }
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned finite import-only fixture
        [sys.executable, "-I", "-B", "-c", script, str(source), str(tmp_path / "storage")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("dry_run", [False, True])
def test_prepared_export_forwards_current_adapter_and_normalizes_result(
    monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    from ...adapters.outbound.google import calc_sheets_apply

    credentials = object()
    sync_repository = object()
    plan = _plan()
    calls: list[str] = []
    monkeypatch.setattr(operation_composition, "resolve_drive_root_folder_id", lambda **kwargs: "fixture-root")
    monkeypatch.setattr(operation_composition, "build_google_credentials", lambda **kwargs: credentials)
    monkeypatch.setattr(operation_composition, "SyncRunRecordRepository", lambda: sync_repository)

    def preview(actual_plan: SheetExportPlan, *, credentials: object, root_folder_id: str):
        assert actual_plan is plan
        assert credentials is credential_marker
        assert root_folder_id == "fixture-root"
        calls.append("preview")
        return calc_sheets_apply.CalcSheetsExportPreview(
            spreadsheet_exists=False,
            value_cells_changed=7,
            value_cells_unchanged=3,
            formula_cells_to_write=2,
        )

    def apply(actual_plan: SheetExportPlan, **kwargs: object):
        assert actual_plan is plan
        assert kwargs == {
            "credentials": credentials,
            "root_folder_id": "fixture-root",
            "sync_run_repository": sync_repository,
            "apply_export_plan": calc_sheets_apply.apply_export_plan,
        }
        calls.append("apply")
        return calc_sheets_apply.CalcSheetsApplyResult(
            folder_id="fixture-root",
            spreadsheet_id="fixture-sheet",
            spreadsheet_url="https://example.invalid/fixture-sheet",
            value_cells_written=11,
            formula_cells_written=12,
            protected_ranges_written=13,
            tab_count=2,
        )

    credential_marker = credentials
    monkeypatch.setattr(calc_sheets_apply, "preview_export_plan", preview)
    monkeypatch.setattr(operation_composition, "export_modelo_to_sheets", apply)
    prepared = operation_composition._google_sheets_export_prepare_port()(str(PROFILE_ID))
    result = prepared.execute(plan, dry_run)
    assert result.dry_run is dry_run
    assert result.root_folder_id == "fixture-root"
    if dry_run:
        assert calls == ["preview"]
        assert result.value_cells_changed == 7
        assert result.value_cells_unchanged == 3
        assert result.formula_cells_to_write == 2
        assert result.value_cells_written == len(plan.value_cells)
    else:
        assert calls == ["apply"]
        assert result.spreadsheet_id == "fixture-sheet"
        assert result.value_cells_written == 11
        assert result.formula_cells_written == 12
        assert result.protected_ranges_written == 13
        assert result.tab_count == 2


def test_prepared_export_preserves_application_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = OutboundStorageValidationError("fixture refusal")
    monkeypatch.setattr(operation_composition, "resolve_drive_root_folder_id", lambda **kwargs: "fixture-root")
    monkeypatch.setattr(operation_composition, "build_google_credentials", lambda **kwargs: object())
    monkeypatch.setattr(operation_composition, "SyncRunRecordRepository", object)

    def refuse(*args: object, **kwargs: object) -> None:
        raise marker

    monkeypatch.setattr(operation_composition, "export_modelo_to_sheets", refuse)
    prepared = operation_composition._google_sheets_export_prepare_port()(str(PROFILE_ID))
    with pytest.raises(OutboundStorageValidationError) as caught:
        prepared.execute(_plan(), False)
    assert caught.value is marker


def test_review_publish_forwards_canonical_transport_and_custody_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    from ...adapters.outbound.google import api, calc_sheets_apply
    from ...adapters.outbound.google.managed_artifacts import ManagedGoogleArtifacts

    snapshot = acceptance_snapshot()
    publication = acceptance_publication(snapshot)
    authorization = acceptance_authorization(publication)
    completed = completed_acceptance_receipt(publication)
    credentials, drive, sheets = object(), object(), object()
    repository = SecureObjectRepository.__new__(SecureObjectRepository)
    calls: list[str] = []

    def handoff(action: str, *, writes: bool = False) -> None:
        raise AssertionError("forwarding should not perform a provider handoff")

    def acknowledged(action: str, *, writes: bool = False) -> None:
        raise AssertionError("forwarding should not report a provider acknowledgement")

    def commit[ResultT](save: Callable[[], ResultT], *, changed: Callable[[ResultT], bool]) -> ResultT:
        raise AssertionError("forwarding should not write receipt custody")

    def publish_plan(
        plan: SheetExportPlan[SheetReviewMetadata],
        *,
        publication: PublicationReceipt,
        artifacts: ManagedGoogleArtifacts,
        sheets: object,
    ) -> PublicationReceipt:
        assert plan.metadata.publication_id == publication.publication_id
        assert artifacts.admission.profile_id == PROFILE_ID
        assert artifacts.admission.root is publication.root
        assert artifacts.admission.drive is drive
        assert artifacts.admission.before_handoff is handoff
        assert artifacts.admission.acknowledged is acknowledged
        assert artifacts.receipts._commit is commit
        assert artifacts.receipts._repository is repository
        assert sheets is sheet_marker
        calls.append("publish_plan")
        return completed

    def publish_review(
        actual_snapshot: ReviewSnapshot,
        *,
        selection: ReviewSelection,
        publication: PublicationReceipt,
        authorization: ReadableExportAuthorization,
        prepared: GoogleSheetsReviewPreparedPort,
        exported_at: datetime,
        label: ReviewLabelResolver,
    ) -> PublicationReceipt:
        assert actual_snapshot is snapshot
        assert selection is snapshot.selection
        assert authorization is authorization_marker
        assert exported_at == EXPORTED_AT
        plan = SheetExportPlan[SheetReviewMetadata](
            metadata=SheetReviewMetadata(
                kind="calculation",
                snapshot_digest=snapshot.snapshot_digest,
                publication_id=publication.publication_id,
                title="Fixture review",
                exported_at=exported_at,
            ),
            guide=SheetGuideContent(title="Fixture review", paragraphs=("Synthetic forwarding fixture",)),
        )
        return prepared.execute(plan, publication)

    sheet_marker, authorization_marker = sheets, authorization
    monkeypatch.setattr(review_composition, "build_google_credentials", lambda **kwargs: credentials)
    monkeypatch.setattr(review_composition, "secure_object_repository_for_bucket", lambda profile: repository)
    monkeypatch.setattr(review_composition, "now", lambda: EXPORTED_AT)
    monkeypatch.setattr(api, "drive_v3_service", lambda *args, **kwargs: drive)
    monkeypatch.setattr(api, "sheets_v4_service", lambda *args, **kwargs: sheets)
    monkeypatch.setattr(calc_sheets_apply, "publish_review_plan", publish_plan)
    monkeypatch.setattr(review_composition, "publish_google_review", publish_review)
    ports = review_composition.build_google_review_ports(profile_id=PROFILE_ID, operation=unread_authority_operation())
    result = ports.publish(
        snapshot, publication, authorization, commit=commit, before_handoff=handoff, acknowledged=acknowledged
    )
    assert result is completed
    assert calls == ["publish_plan"]
