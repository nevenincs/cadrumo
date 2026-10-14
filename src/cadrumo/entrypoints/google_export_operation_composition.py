"""Compose the Google Sheets export operation's outbound transport.

The registered export reaches Google through one prepared port per profile:
the profile's Drive root folder and credentials, and the provenance service
that records every applied plan as a sync run.
"""

from __future__ import annotations

from ..adapters.outbound.google.errors import GoogleAuthClientMetadataUnavailableError
from ..adapters.outbound.storage.errors import OutboundStorageError, OutboundStorageValidationError
from ..adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ..application.export.google_operation import (
    GoogleSheetsExportAuthDependencyError,
    GoogleSheetsExportClientMissingError,
    GoogleSheetsExportPreparedPort,
    GoogleSheetsExportPreparePort,
    GoogleSheetsExportRemoteResult,
    GoogleSheetsExportRootFolderRequiredError,
    GoogleSheetsExportTokenMissingError,
)
from ..application.storage.calc_sheets.export_service import export_modelo_to_sheets
from ..application.storage.calc_sheets.records import SheetExportPlan


def build_google_sheets_export_prepare_port() -> GoogleSheetsExportPreparePort:
    """Compose the sole Google transport and mandatory sync-run provenance handoff."""

    def prepare(profile_id: str) -> GoogleSheetsExportPreparedPort:
        root_folder_id = resolve_drive_root_folder_id(profile=profile_id)
        if not root_folder_id:
            raise GoogleSheetsExportRootFolderRequiredError("Google Drive root folder is required")
        try:
            credentials = build_google_credentials(profile=profile_id)
        except GoogleAuthClientMetadataUnavailableError as exc:
            raise GoogleSheetsExportClientMissingError(str(exc)) from exc
        except OutboundStorageValidationError as exc:
            if exc.translated_message == "adapters.outbound.storage._factory.errors.google_token_missing":
                raise GoogleSheetsExportTokenMissingError(str(exc)) from exc
            raise
        except OutboundStorageError as exc:
            if exc.translated_message == "adapters.outbound.storage._factory.errors.google_auth_import_failed":
                raise GoogleSheetsExportAuthDependencyError(str(exc)) from exc
            raise

        class PreparedGoogleSheetsExport:
            def execute(self, plan: SheetExportPlan, dry_run: bool) -> GoogleSheetsExportRemoteResult:
                from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan, preview_export_plan

                if dry_run:
                    preview = preview_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
                    return GoogleSheetsExportRemoteResult(
                        dry_run=True,
                        root_folder_id=root_folder_id,
                        spreadsheet_exists=preview.spreadsheet_exists,
                        folder_id=preview.folder_id,
                        spreadsheet_id=preview.spreadsheet_id,
                        spreadsheet_url=preview.spreadsheet_url,
                        value_cells_written=len(plan.value_cells),
                        formula_cells_written=len(plan.formula_cells),
                        protected_ranges_written=len(plan.protected_ranges),
                        tab_count=len(plan.tabs),
                        ranges_to_clear=preview.ranges_to_clear,
                        value_cells_changed=preview.value_cells_changed,
                        value_cells_unchanged=preview.value_cells_unchanged,
                        formula_cells_to_write=preview.formula_cells_to_write,
                    )
                applied = export_modelo_to_sheets(
                    plan,
                    credentials=credentials,
                    root_folder_id=root_folder_id,
                    sync_run_repository=SyncRunRecordRepository(),
                    apply_export_plan=apply_export_plan,
                )
                return GoogleSheetsExportRemoteResult(
                    dry_run=False,
                    root_folder_id=root_folder_id,
                    folder_id=applied.folder_id,
                    spreadsheet_id=applied.spreadsheet_id,
                    spreadsheet_url=applied.spreadsheet_url,
                    value_cells_written=applied.value_cells_written,
                    formula_cells_written=applied.formula_cells_written,
                    protected_ranges_written=applied.protected_ranges_written,
                    tab_count=applied.tab_count,
                )

        return PreparedGoogleSheetsExport()

    return prepare


__all__ = ["build_google_sheets_export_prepare_port"]
