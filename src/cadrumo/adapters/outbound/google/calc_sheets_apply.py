"""Live Google Sheets adapter that materialises a :class:`~application.storage.calc_sheets.SheetExportPlan`.

The adapter is the outbound boundary for
:mod:`application.storage.calc_sheets`: the engine produces a pure
:class:`~application.storage.calc_sheets.SheetExportPlan`, and this
module turns the plan into a real spreadsheet inside the operator's
``cadrumo-vault/`` Drive folder. Every Drive folder and Sheets spreadsheet the
adapter touches carries the
``appProperties.cadrumo_vault_app=cadrumo`` ownership marker so the operator's
pre-existing Drive content is isolated from app-owned artefacts.

Composition:

- Drive v3 hosts the parent folder structure
  ``cadrumo-vault/calc-sheets/{modelo}-{period}-{year}/`` and the spreadsheet
  file metadata.
- Sheets v4 reshapes the spreadsheet: tabs, cell values, formulas,
  protected ranges, and developer metadata stamping the engine
  version + registry SHA.

All Google calls route through
:func:`~adapters.outbound.google.api.execute_request`, which raises
typed :exc:`~adapters.outbound.storage.OutboundStorageError`
subclasses on Drive / Sheets failures. This adapter adds
:exc:`~adapters.outbound.storage.OutboundStorageConflictError` when it
refuses foreign Drive content.

One-way contract: this adapter is an export *mirror* only. Google
Sheets is never an authority for tax data — the workbook is a
human-readable projection of registry-grounded engine output, not
an input of record. Operator edits made in the sheet are read back
through :mod:`adapters.outbound.google.calc_sheets_pull`, which gates
every pull on the Drive ownership marker and a registry-SHA metadata match
before the caller may consume them; a workbook that fails either gate is
refused, never silently trusted. No path in this package writes Sheets content
into the local store, the registry, or an AEAT submission.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from google.auth.credentials import Credentials
    from googleapiclient._apis.drive.v3.resources import DriveResource
    from googleapiclient._apis.drive.v3.schemas import File
    from googleapiclient._apis.sheets.v4.resources import SheetsResource
    from googleapiclient._apis.sheets.v4.schemas import (
        BatchUpdateSpreadsheetRequest,
        BatchUpdateValuesRequest,
        Request,
        Spreadsheet,
        ValueRange,
    )

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, Field, NonNegativeInt

from ....application.storage.calc_sheets.records import SheetCellAddress, SheetExportPlan, SheetValueCell, TabName
from ....core.json_shapes import str_keyed_mapping, str_keyed_rows
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..storage.errors import OutboundStorageError, OutboundStorageNetworkError, OutboundStorageValidationError
from ._calc_sheets_apply_formatting import (
    build_auto_filter_requests,
    build_base_font_requests,
    build_cell_constraint_requests,
    build_column_width_requests,
    build_emphasis_format_requests,
    build_frozen_view_requests,
    build_grid_resize_requests,
    build_number_format_requests,
    build_protected_range_requests,
    build_styled_range_requests,
)
from ._calc_sheets_apply_values import (
    build_evidence_value_data,
    build_formula_data,
    build_guide_value_data,
    build_row_set_header_data,
    build_value_data,
    changed_cell_addresses,
    payload_written_addresses,
    stale_addresses,
    written_cell_values,
)
from ._calc_sheets_apply_values import (
    coerce_cell_value as coerce_cell_value,
)
from ._preconditions import google_terminal_refusal
from .api import execute_request
from .drive_entries import (
    OWNERSHIP_KEY as _OWNERSHIP_KEY,
)
from .drive_entries import (
    OWNERSHIP_VALUE as _OWNERSHIP_VALUE,
)
from .drive_entries import (
    find_owned_drive_entry,
    require_drive_entry_id,
)

_FOLDER_MIME: Final[str] = "application/vnd.google-apps.folder"
_SPREADSHEET_MIME: Final[str] = "application/vnd.google-apps.spreadsheet"


class CalcSheetsApplyPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the calculation-sheet apply adapter."""

    API_CLIENT_AVAILABLE = "google.calc_sheets.apply.api_client_available"
    ROOT_FOLDER_ID_VALID = "google.calc_sheets.apply.root_folder_id_valid"


def _calc_sheets_apply_terminal_refusal(
    error: OutboundStorageError,
    condition: CalcSheetsApplyPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> OutboundStorageError:
    """Return ``error`` with this adapter's fact-only terminal verdict."""
    return google_terminal_refusal(
        error,
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


def _require_root_folder_id(root_folder_id: str) -> None:
    """Refuse an empty operator-supplied Drive root before any Google call."""
    if root_folder_id.strip():
        return
    error = OutboundStorageValidationError(
        "root_folder_id must not be blank",
        context={"root_folder_id": root_folder_id},
    )
    raise _calc_sheets_apply_terminal_refusal(
        error,
        CalcSheetsApplyPreconditionCondition.ROOT_FOLDER_ID_VALID,
        facts={"root_folder_id_present": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _vault_folder_name() -> str:
    """Read the Drive vault folder name at call time, never at import time.

    A module-scope ``Settings()`` resolves the storage root while the module
    imports; the CLI ``config`` subtree and external schema introspection
    imports this adapter, so an import-time refusal would kill the whole
    entrypoint instead of the one Drive operation that needs the setting.
    """
    from ....core.config import load_settings

    return load_settings().cadrumo_google_drive_vault_folder_name


_CALC_SHEETS_FOLDER_NAME: Final[str] = "calc-sheets"
_RELATION_METADATA_PREFIX: Final[str] = "cadrumo_relation:"
_MANAGED_DEVELOPER_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "cadrumo_engine_version",
        "cadrumo_registry_sha",
        "cadrumo_modelo_id",
        "cadrumo_revision_id",
        "cadrumo_filing_year",
        "cadrumo_period",
        "cadrumo_exported_at",
    },
)


class CalcSheetsApplyResult(BaseModel):
    """Outcome of one apply cycle.

    Returned by :func:`~adapters.outbound.google.apply_export_plan` after
    a :class:`~application.storage.calc_sheets.SheetExportPlan` has been
    materialised. Carries the spreadsheet's Drive file id, its Sheets URL, the
    ``cadrumo-vault/calc-sheets/<...>/`` Drive folder id, and the counts of value
    cells, formula cells, row-set headers, protected ranges, and tabs written
    during the apply cycle.
    """

    model_config = STRICT_FROZEN_CONFIG

    spreadsheet_id: str = Field(min_length=1)
    spreadsheet_url: str = Field(min_length=1)
    folder_id: str = Field(min_length=1)
    value_cells_written: NonNegativeInt
    formula_cells_written: NonNegativeInt
    protected_ranges_written: NonNegativeInt
    row_set_headers_written: int = Field(ge=0, default=0)
    tab_count: int = Field(ge=1)


class CalcSheetsExportPreview(BaseModel):
    """What :func:`apply_export_plan` would clear and (re)write, computed with no write call.

    Returned by :func:`preview_export_plan`, which reads Drive and Sheets state
    only: it never creates a folder or a spreadsheet, never backfills an
    ownership marker on a fresh lookup, and never issues a ``batchClear`` or
    ``batchUpdate`` write. The three facts a dry-run promises per the decision
    record: the per-tab ranges the apply would clear, how many value cells
    would actually change against the current read-back, and how many formula
    cells the apply would (unconditionally) rewrite — the live apply always
    rewrites every formula cell it carries rather than diffing formula text
    against a computed result, so this preview reports the same count rather
    than inventing a comparison the real write does not make either.

    ``folder_id``, ``spreadsheet_id`` and ``spreadsheet_url`` are ``None``
    only when no matching target exists yet: the first export for a given
    modelo, period and year has nothing on Drive to look up, so every value
    cell previews as new content and there is nothing to clear.
    """

    model_config = STRICT_FROZEN_CONFIG

    spreadsheet_exists: bool
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    ranges_to_clear: tuple[str, ...] = ()
    value_cells_changed: NonNegativeInt
    value_cells_unchanged: NonNegativeInt
    formula_cells_to_write: NonNegativeInt


def _refuse_missing_googleapiclient(exc: ImportError, service_name: str, version: str) -> NoReturn:
    """Refuse, naming the service, when the optional discovery client is absent."""
    error = OutboundStorageNetworkError(
        f"googleapiclient not importable: {exc}",
        translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
    )
    raise _calc_sheets_apply_terminal_refusal(
        error,
        CalcSheetsApplyPreconditionCondition.API_CLIENT_AVAILABLE,
        facts={
            "client_available": False,
            "dependency": "google_api_python_client",
            "service_name": service_name,
            "service_version": version,
        },
        outcome=NoRecoveryOutcome.SAFETY,
    ) from exc


# `google-api-python-client-stubs` types `build` per (service, version) LITERAL.
# The former shared factory forwarded both as variables, so no literal overload
# matched and every downstream call went untyped. Each service now spells its own
# literals, and the import/refusal preamble stays shared.
def _drive_service(credentials: Credentials) -> DriveResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        _refuse_missing_googleapiclient(exc, "drive", "v3")
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _sheets_service(credentials: Credentials) -> SheetsResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        _refuse_missing_googleapiclient(exc, "sheets", "v4")
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _find_folder(
    drive: DriveResource,
    *,
    parent_id: str,
    name: str,
) -> File | None:
    #
    # Ownership acceptance, marker backfill, foreign-content refusal,
    # query-name escaping, and entry-id validation are the shared policy in
    # ``drive_entries``; only the MIME type and the action/error text are
    # folder-specific.
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type=_FOLDER_MIME,
        list_action="drive.files.list",
        backfill_action="drive.files.update.backfill_marker",
        conflict_message=(
            f"folder named {name!r} under parent {parent_id!r} exists but is not marked as "
            "app-owned; refusing to adopt foreign Drive content"
        ),
    )


def _create_folder(
    drive: DriveResource,
    *,
    parent_id: str,
    name: str,
) -> File:
    body: File = {
        "name": name,
        "mimeType": _FOLDER_MIME,
        "parents": [parent_id],
        "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
    }
    return execute_request(
        drive.files().create(body=body, fields="id,name,appProperties"),
        action="drive.files.create.folder",
    )


def _ensure_folder(
    drive: DriveResource,
    *,
    parent_id: str,
    name: str,
) -> str:
    existing = _find_folder(drive, parent_id=parent_id, name=name)
    if existing is not None:
        return require_drive_entry_id(existing, name=name, parent_id=parent_id)
    created = _create_folder(drive, parent_id=parent_id, name=name)
    return require_drive_entry_id(created, name=name, parent_id=parent_id)


def _find_spreadsheet(
    drive: DriveResource,
    *,
    parent_id: str,
    name: str,
) -> File | None:
    # Same shared ownership/backfill/refusal policy as ``_find_folder``; only
    # the MIME type and the action/error text are spreadsheet-specific.
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type=_SPREADSHEET_MIME,
        list_action="drive.files.list.spreadsheet",
        backfill_action="drive.files.update.backfill_marker.spreadsheet",
        conflict_message=(
            f"spreadsheet {name!r} exists under parent {parent_id!r} but is not marked as "
            "app-owned; refusing to overwrite"
        ),
    )


def _create_spreadsheet(
    drive: DriveResource,
    sheets: SheetsResource,
    *,
    parent_id: str,
    title: str,
    tab_names: Iterable[str],
) -> Spreadsheet:
    body: Spreadsheet = {
        # Locale `en_US` keeps the formula argument separator as ",".
        # Spanish-style display formatting (1.234,56) is applied at the
        # cell numberFormat level, which is independent of the
        # workbook's parsing locale. Using `es_ES` here would force
        # `;` as the argument separator and break every `ROUND(x,2)`
        # the engine emits.
        "properties": {"title": title, "locale": "en_US"},
        "sheets": [{"properties": {"title": tab_name}} for tab_name in tab_names],
    }
    spreadsheet = execute_request(
        sheets.spreadsheets().create(body=body, fields="spreadsheetId,spreadsheetUrl,sheets.properties"),
        action="sheets.spreadsheets.create",
    )
    spreadsheet_id = spreadsheet.get("spreadsheetId")
    if not spreadsheet_id:
        raise OutboundStorageValidationError(
            "Sheets create returned no spreadsheetId",
            context={"parent_id": parent_id, "title": title},
        )
    # Move the freshly created spreadsheet into the target folder and
    # stamp the ownership marker. `files.update` with `addParents` +
    # `removeParents=root` is the canonical move pattern.
    file_meta = execute_request(
        drive.files().get(fileId=spreadsheet_id, fields="parents"),
        action="drive.files.get.parents",
    )
    remove_parents = ",".join(file_meta.get("parents") or [])
    execute_request(
        drive.files().update(
            fileId=spreadsheet_id,
            addParents=parent_id,
            removeParents=remove_parents or None,
            body={"appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE}},
            fields="id,parents,appProperties",
        ),
        action="drive.files.update.move_and_stamp",
    )
    return spreadsheet


def _developer_metadata_pairs(plan: SheetExportPlan) -> list[tuple[str, str]]:
    metadata = plan.metadata
    pairs: list[tuple[str, str]] = [
        ("cadrumo_engine_version", metadata.engine_version),
        ("cadrumo_registry_sha", metadata.registry_sha),
        ("cadrumo_modelo_id", metadata.modelo_id),
        ("cadrumo_revision_id", metadata.revision_id),
        ("cadrumo_filing_year", str(metadata.filing_year)),
        ("cadrumo_period", metadata.period.registry_token),
        ("cadrumo_exported_at", metadata.exported_at.isoformat()),
    ]
    if plan.relation_provenance is not None:
        for relation in plan.relation_provenance.values:
            payload = {
                "value": str(relation.value) if relation.value is not None else "",
                "provenance": relation.provenance,
                "source_modelo": relation.source_modelo or "",
                "source_filing_year": str(relation.source_filing_year)
                if relation.source_filing_year is not None
                else "",
                "source_periods": "+".join(relation.source_periods),
                "source_casilla_ids": "+".join(relation.source_casilla_ids),
                "legal_refs": "+".join(relation.legal_refs),
                "source_refs": "+".join(relation.source_refs),
                "resolved_at": relation.resolved_at.isoformat() if relation.resolved_at is not None else "",
            }
            pairs.append(
                (
                    f"cadrumo_relation:{relation.relation}",
                    "; ".join(f"{k}={v}" for k, v in payload.items() if v),
                ),
            )
    return pairs


def _build_developer_metadata_requests(
    plan: SheetExportPlan,
) -> list[Request]:
    return [
        {
            "createDeveloperMetadata": {
                "developerMetadata": {
                    "metadataKey": key,
                    "metadataValue": value,
                    "location": {"spreadsheet": True},
                    "visibility": "DOCUMENT",
                },
            },
        }
        for key, value in _developer_metadata_pairs(plan)
    ]


def _managed_developer_metadata_key(key: object) -> bool:
    return isinstance(key, str) and (
        key in _MANAGED_DEVELOPER_METADATA_KEYS or key.startswith(_RELATION_METADATA_PREFIX)
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-SHEETS-API-PAYLOAD: spreadsheet is the
# free-shape JSON payload returned by the Google Sheets API; the googleapiclient
# discovery client ships no typed model for the response.
def _build_developer_metadata_cleanup_requests(
    spreadsheet: Mapping[str, Any],
) -> list[Request]:
    """Delete previously emitted AEAT developer metadata before recreating it.

    Google Sheets developer metadata keys are not unique. Re-applying a
    workbook by repeatedly creating the same `aeat_*` keys leaves duplicate
    identity stamps whose read order is API-defined, not a stable contract.
    Delete only entries with metadata IDs the API returned and only for keys
    this adapter owns.
    """
    requests: list[Request] = []
    seen_ids: set[int] = set()
    for entry in str_keyed_rows(spreadsheet, "developerMetadata"):
        if not _managed_developer_metadata_key(entry.get("metadataKey")):
            continue
        metadata_id = entry.get("metadataId")
        if not isinstance(metadata_id, int) or metadata_id in seen_ids:
            continue
        seen_ids.add(metadata_id)
        requests.append(
            {
                "deleteDeveloperMetadata": {
                    "dataFilter": {
                        "developerMetadataLookup": {
                            "metadataId": metadata_id,
                        },
                    },
                },
            },
        )
    return requests


# ADAPTER-INTERNAL-ALIAS-RATIONALE-SHEETS-API-PAYLOAD: spreadsheet is the
# free-shape JSON payload returned by the Google Sheets API.
def _build_protected_range_cleanup_requests(
    spreadsheet: Mapping[str, Any],
    plan: SheetExportPlan,
) -> list[Request]:
    """Delete app-managed protected ranges before recreating current ranges."""
    managed_descriptions = {region.description for region in plan.protected_ranges}
    if not managed_descriptions:
        return []
    requests: list[Request] = []
    seen_ids: set[int] = set()
    for sheet in str_keyed_rows(spreadsheet, "sheets"):
        for protected in str_keyed_rows(sheet, "protectedRanges"):
            if protected.get("description") not in managed_descriptions:
                continue
            protected_range_id = protected.get("protectedRangeId")
            if not isinstance(protected_range_id, int) or protected_range_id in seen_ids:
                continue
            seen_ids.add(protected_range_id)
            requests.append({"deleteProtectedRange": {"protectedRangeId": protected_range_id}})
    return requests


# ADAPTER-INTERNAL-ALIAS-RATIONALE-SHEETS-API-PAYLOAD: spreadsheet is the
# free-shape JSON payload returned by the Google Sheets API.
def _build_structural_cleanup_requests(
    spreadsheet: Mapping[str, Any],
    plan: SheetExportPlan,
) -> list[Request]:
    return _build_developer_metadata_cleanup_requests(spreadsheet) + _build_protected_range_cleanup_requests(
        spreadsheet,
        plan,
    )


def _build_cell_note_requests(
    value_cells: Iterable[SheetValueCell],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Emit `updateCells` requests with cell notes for any value cell that has one."""
    requests: list[Request] = []
    for cell in value_cells:
        if cell.note is None:
            continue
        sheet_id = sheet_id_by_tab.get(cell.address.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": cell.address.row - 1,
                        "endRowIndex": cell.address.row,
                        "startColumnIndex": cell.address.column - 1,
                        "endColumnIndex": cell.address.column,
                    },
                    "rows": [{"values": [{"note": cell.note}]}],
                    "fields": "note",
                },
            },
        )
    return requests


def _spreadsheet_title(plan: SheetExportPlan) -> str:
    metadata = plan.metadata
    return f"AEAT {metadata.modelo_id} {metadata.period.registry_token} {metadata.filing_year}"


def _subfolder_name(plan: SheetExportPlan) -> str:
    metadata = plan.metadata
    return f"{metadata.modelo_id}-{metadata.period.registry_token}-{metadata.filing_year}"


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api drive/sheets Resource (dynamic discovery build).
def _open_or_create_plan_spreadsheet(
    *,
    drive: DriveResource,
    sheets: SheetsResource,
    plan: SheetExportPlan,
    root_folder_id: str,
    tab_titles: tuple[str, ...],
) -> tuple[Spreadsheet, str]:
    vault_folder_id = _ensure_folder(drive, parent_id=root_folder_id, name=_vault_folder_name())
    calc_folder_id = _ensure_folder(drive, parent_id=vault_folder_id, name=_CALC_SHEETS_FOLDER_NAME)
    period_folder_id = _ensure_folder(drive, parent_id=calc_folder_id, name=_subfolder_name(plan))

    title = _spreadsheet_title(plan)
    existing = _find_spreadsheet(drive, parent_id=period_folder_id, name=title)
    if existing is None:
        spreadsheet = _create_spreadsheet(
            drive,
            sheets,
            parent_id=period_folder_id,
            title=title,
            tab_names=tab_titles,
        )
    else:
        spreadsheet = execute_request(
            sheets.spreadsheets().get(
                spreadsheetId=require_drive_entry_id(existing, name=title, parent_id=period_folder_id),
                fields=(
                    "spreadsheetId,spreadsheetUrl,"
                    "developerMetadata(metadataId,metadataKey,metadataValue,location),"
                    "sheets.properties,"
                    "sheets.protectedRanges(protectedRangeId,description,range,warningOnly)"
                ),
            ),
            action="sheets.spreadsheets.get",
        )
    return spreadsheet, period_folder_id


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _force_spreadsheet_locale(*, sheets: Any, spreadsheet_id: str) -> None:
    # Force the workbook locale to `en_US` so the formula argument
    # separator stays a comma. Applies on every run so a workbook
    # created under a previous engine version (which may have used
    # `es_ES`) is corrected on the next export.
    execute_request(
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSpreadsheetProperties": {
                            "properties": {"locale": "en_US"},
                            "fields": "locale",
                        },
                    },
                ],
            },
        ),
        action="sheets.spreadsheets.batchUpdate.locale",
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _ensure_plan_tabs_and_grid(
    *,
    sheets: SheetsResource,
    spreadsheet: Mapping[str, Any],
    spreadsheet_id: str,
    plan: SheetExportPlan,
    tab_titles: tuple[str, ...],
) -> dict[str, int]:
    sheet_id_by_tab: dict[str, int] = {}
    for sheet in str_keyed_rows(spreadsheet, "sheets"):
        props = str_keyed_mapping(sheet.get("properties"))
        sheet_id_by_tab[str(props.get("title", ""))] = _as_int(props.get("sheetId"))

    # Make sure every tab the engine expects actually exists. If the
    # spreadsheet predates a new tab, add it.
    missing_tabs = [tab for tab in tab_titles if tab not in sheet_id_by_tab]
    if missing_tabs:
        add_sheet_requests: list[Request] = [{"addSheet": {"properties": {"title": tab}}} for tab in missing_tabs]
        add_sheet_body: BatchUpdateSpreadsheetRequest = {"requests": add_sheet_requests}
        result = execute_request(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=add_sheet_body,
            ),
            action="sheets.spreadsheets.batchUpdate.add_missing_tabs",
        )
        for reply in str_keyed_rows(result, "replies"):
            added = str_keyed_mapping(str_keyed_mapping(reply.get("addSheet")).get("properties"))
            sheet_id_by_tab[str(added.get("title", ""))] = _as_int(added.get("sheetId"))

    # Resize each tab so the plan fits inside the grid. Sheets'
    # default grid is 1000 rows x 26 columns; large modelos (e.g.
    # 100 with 2235 casillas in Entradas) overflow that bound on
    # the first cell write. We compute the maximum row + column
    # each tab will receive in the upcoming batchUpdate and grow
    # the grid in one structural request before any value write.
    resize_requests = build_grid_resize_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    if resize_requests:
        resize_body: BatchUpdateSpreadsheetRequest = {"requests": resize_requests}
        execute_request(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=resize_body,
            ),
            action="sheets.spreadsheets.batchUpdate.resize_grid",
        )
    return sheet_id_by_tab


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
#: Tab titles the exporter manages. A spreadsheet may carry operator-added
#: tabs; those are never read for stale content and never cleared.
_TAB_TITLES: frozenset[str] = frozenset(tab.value for tab in TabName)


@dataclass(frozen=True, slots=True)
class _OccupiedAddressRange:
    """One managed tab and its pre-resize A1 range, kept positionally aligned."""

    tab: TabName
    address: str


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets JSON response body.
def _as_int(value: object) -> int:
    """Return ``value`` as an ``int``, treating an absent or non-numeric value as 0.

    Sheets omits a count field rather than sending zero, and the two are the
    same thing for a grid dimension: nothing has been allocated yet.
    """
    return value if isinstance(value, int) else 0


def _grid_by_tab(spreadsheet: Mapping[str, Any]) -> dict[str, tuple[int, int]]:
    """Map each existing tab title to its ``(rowCount, columnCount)`` grid."""
    grid: dict[str, tuple[int, int]] = {}
    for sheet in str_keyed_rows(spreadsheet, "sheets"):
        props = str_keyed_mapping(sheet.get("properties"))
        title = str(props.get("title", ""))
        if title not in _TAB_TITLES:
            continue
        grid_props = str_keyed_mapping(props.get("gridProperties"))
        grid[title] = (_as_int(grid_props.get("rowCount")), _as_int(grid_props.get("columnCount")))
    return grid


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _occupied_addresses(
    *,
    sheets: SheetsResource,
    spreadsheet_id: str,
    grid_by_tab: Mapping[str, tuple[int, int]],
) -> frozenset[str]:
    """Return every qualified address currently holding a value.

    Each tab is read over an A1-anchored range built from its OWN grid, so
    the response block's top-left is A1 by construction and no returned
    range has to be parsed back into indices.

    The grid read is the PRE-resize one, which is the correct bound rather
    than a convenient one: the resize step only ever grows a tab, so no
    surviving value can sit outside the grid as it stood before this run.
    """
    return frozenset(_current_cell_values(sheets=sheets, spreadsheet_id=spreadsheet_id, grid_by_tab=grid_by_tab))


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _current_cell_values(
    *,
    sheets: SheetsResource,
    spreadsheet_id: str,
    grid_by_tab: Mapping[str, tuple[int, int]],
) -> dict[str, Any]:
    """Read every managed-tab cell currently holding a value, keyed by qualified address.

    The export preview needs the raw values themselves — presence alone
    cannot answer whether a write would change anything. Callers that need
    occupancy derive it from the returned mapping's keys.
    """
    ranges = _occupied_address_ranges(grid_by_tab)
    if not ranges:
        return {}
    response = execute_request(
        sheets.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[item.address for item in ranges],
            valueRenderOption="UNFORMATTED_VALUE",
        ),
        action="sheets.spreadsheets.values.batchGet",
    )
    return _current_cell_values_from_response(ranges, response)


def _occupied_address_ranges(
    grid_by_tab: Mapping[str, tuple[int, int]],
) -> tuple[_OccupiedAddressRange, ...]:
    """Build sorted managed-tab read ranges, omitting nonpositive dimensions."""
    return tuple(
        _OccupiedAddressRange(
            tab=TabName(tab),
            address=f"'{tab}'!A1:{SheetCellAddress.at(TabName(tab), rows, columns).a1}",
        )
        for tab, (rows, columns) in sorted(grid_by_tab.items())
        if tab in _TAB_TITLES and rows > 0 and columns > 0
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _current_cell_values_from_response(
    ranges: tuple[_OccupiedAddressRange, ...],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine aligned response blocks into one address-to-value mapping.

    Missing and extra response blocks are safely truncated to the requested
    ranges. Non-blank values, including ``0`` and ``False``, remain in the
    mapping so callers can use both the values and ``frozenset(values)`` as
    the occupied-address view.
    """
    values: dict[str, Any] = {}
    for address_range, value_range in zip(ranges, response.get("valueRanges", []) or [], strict=False):
        values.update(_current_cell_values_in_range(address_range.tab, value_range))
    return values


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _current_cell_values_in_range(tab: TabName, value_range: Mapping[str, Any]) -> dict[str, Any]:
    """Return one A1-anchored managed-tab response block's non-blank cells, keyed by address.

    This is the per-range primitive used by the canonical response reader;
    its mapping preserves values such as ``0`` and ``False`` for preview
    comparisons while its keys provide the occupied-address view.
    """
    values: dict[str, Any] = {}
    for row_offset, row_values in enumerate(value_range.get("values", []) or []):
        for column_offset, cell in enumerate(row_values):
            if cell == "" or cell is None:
                continue
            values[SheetCellAddress.at(tab, row_offset + 1, column_offset + 1).qualified()] = cell
    return values


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _plan_value_payload(plan: SheetExportPlan) -> list[ValueRange]:
    """Assemble every non-formula value entry the plan would write.

    Shared by :func:`_write_plan_values` (the real write) and
    :func:`preview_export_plan` (the read-only preview), so the two can never
    disagree about what counts as a plan's literal value content.
    """
    return (
        build_value_data(plan.value_cells)
        + build_guide_value_data(plan)
        + build_row_set_header_data(plan.row_sets)
        + build_evidence_value_data(plan)
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _write_plan_values(
    *,
    sheets: SheetsResource,
    spreadsheet_id: str,
    plan: SheetExportPlan,
) -> frozenset[str]:
    """Write the plan's values and formulas, and return the addresses written.

    Returning the written set is what makes the ordering structural rather
    than a convention: :func:`_clear_stale_addresses` cannot run before this
    function, because its input does not exist until this function returns.
    """
    # Write values and formulas as USER_ENTERED so Sheets parses
    # formula strings starting with "=".
    data = _plan_value_payload(plan) + build_formula_data(plan.formula_cells)
    values_body: BatchUpdateValuesRequest = {"valueInputOption": "USER_ENTERED", "data": data}
    execute_request(
        sheets.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=values_body,
        ),
        action="sheets.spreadsheets.values.batchUpdate",
    )
    return payload_written_addresses(data)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _clear_stale_addresses(
    *,
    sheets: SheetsResource,
    spreadsheet_id: str,
    occupied: frozenset[str],
    written: frozenset[str],
) -> None:
    """Clear only the cells a previous run filled that this run did not rewrite."""
    stale = stale_addresses(occupied=occupied, written=written)
    if not stale:
        return
    execute_request(
        sheets.spreadsheets()
        .values()
        .batchClear(
            spreadsheetId=spreadsheet_id,
            body={"ranges": list(stale)},
        ),
        action="sheets.spreadsheets.values.batchClear",
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _apply_plan_structural_requests(
    *,
    sheets: SheetsResource,
    spreadsheet_id: str,
    spreadsheet: Mapping[str, Any],
    plan: SheetExportPlan,
    sheet_id_by_tab: Mapping[str, int],
) -> None:
    # Apply structural metadata: protected ranges + developer
    # metadata for engine + registry identity + cell-level
    # constraint validation rules + cell notes carrying the
    # constraint and its legal grounding.
    cleanup_requests = _build_structural_cleanup_requests(spreadsheet, plan)
    structural_requests = (
        cleanup_requests
        + _build_developer_metadata_requests(plan)
        + build_protected_range_requests(plan.protected_ranges, sheet_id_by_tab=sheet_id_by_tab)
        + build_cell_constraint_requests(plan.cell_constraints, sheet_id_by_tab=sheet_id_by_tab)
        + _build_cell_note_requests(plan.value_cells, sheet_id_by_tab=sheet_id_by_tab)
        # Base font first, then role styling (fills/bold/colour) wins on overlap,
        # then number formats, emphasis, widths, freezes, filters.
        + build_base_font_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
        + build_styled_range_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
        + build_number_format_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
        + build_emphasis_format_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
        + build_column_width_requests(plan.column_widths, sheet_id_by_tab=sheet_id_by_tab)
        + build_frozen_view_requests(plan.frozen_views, sheet_id_by_tab=sheet_id_by_tab)
        + build_auto_filter_requests(plan.auto_filters, sheet_id_by_tab=sheet_id_by_tab)
    )
    if structural_requests:
        structural_body: BatchUpdateSpreadsheetRequest = {"requests": structural_requests}
        execute_request(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=structural_body,
            ),
            action="sheets.spreadsheets.batchUpdate.structural",
        )


def apply_export_plan(
    plan: SheetExportPlan,
    *,
    credentials: Credentials,
    root_folder_id: str,
) -> CalcSheetsApplyResult:
    """Materialise a :class:`~application.storage.calc_sheets.SheetExportPlan` as a Google Sheets workbook.

    The adapter is idempotent at the spreadsheet level: applying the
    same plan twice updates the same spreadsheet rather than creating
    a duplicate, provided the per-period subfolder + spreadsheet
    title remain stable.

    Args:
        plan: The pure
            :class:`~application.storage.calc_sheets.SheetExportPlan`
            produced by
            :func:`~application.storage.calc_sheets.build_export_plan`.
        credentials: A ``google.oauth2.credentials.Credentials``-shaped
            object carrying refresh + access tokens with at least the
            ``drive.file`` + ``spreadsheets`` scopes.
        root_folder_id: The operator's Drive root folder id (the same
            folder
            :class:`~adapters.outbound.storage._google_drive.GoogleDriveProvider`
            uses for the ciphertext mirror).

    Returns:
        A :class:`~adapters.outbound.google.CalcSheetsApplyResult` with
        the spreadsheet location and write counts surfaced by
        ``aeat config google sync calc export``.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`:
            When the supplied ``root_folder_id`` is blank.
        :exc:`~adapters.outbound.storage.OutboundStorageError`: When
            Drive or Sheets rejects the request, quota is exhausted, the target
            is missing, or the adapter refuses foreign Drive content.
    """
    _require_root_folder_id(root_folder_id)

    drive = _drive_service(credentials)
    sheets = _sheets_service(credentials)
    tab_titles = tuple(tab.value for tab in TabName)
    spreadsheet, period_folder_id = _open_or_create_plan_spreadsheet(
        drive=drive,
        sheets=sheets,
        plan=plan,
        root_folder_id=root_folder_id,
        tab_titles=tab_titles,
    )

    spreadsheet_id = spreadsheet.get("spreadsheetId")
    spreadsheet_url = spreadsheet.get("spreadsheetUrl")
    if not spreadsheet_id or not spreadsheet_url:
        raise OutboundStorageValidationError(
            "Sheets get returned no spreadsheet identity",
            context={
                "spreadsheet_id_present": str(bool(spreadsheet_id)),
                "spreadsheet_url_present": str(bool(spreadsheet_url)),
            },
        )
    _force_spreadsheet_locale(sheets=sheets, spreadsheet_id=spreadsheet_id)
    sheet_id_by_tab = _ensure_plan_tabs_and_grid(
        sheets=sheets,
        spreadsheet=spreadsheet,
        spreadsheet_id=spreadsheet_id,
        plan=plan,
        tab_titles=tab_titles,
    )
    # Write first, then clear only what the write did not replace. The
    # previous order -- clear every tab, then write -- left a window in
    # which an interruption between two unprotected API calls emptied the
    # operator's workbook outright. Sheets offers no transaction spanning
    # values.batchClear and values.batchUpdate, so the fix is ordering: a
    # run interrupted at any point now leaves the workbook holding either
    # the old content or the new, never nothing.
    occupied = _occupied_addresses(
        sheets=sheets,
        spreadsheet_id=spreadsheet_id,
        grid_by_tab=_grid_by_tab(spreadsheet),
    )
    written = _write_plan_values(sheets=sheets, spreadsheet_id=spreadsheet_id, plan=plan)
    _clear_stale_addresses(
        sheets=sheets,
        spreadsheet_id=spreadsheet_id,
        occupied=occupied,
        written=written,
    )
    _apply_plan_structural_requests(
        sheets=sheets,
        spreadsheet_id=spreadsheet_id,
        spreadsheet=spreadsheet,
        plan=plan,
        sheet_id_by_tab=sheet_id_by_tab,
    )

    return CalcSheetsApplyResult(
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        folder_id=period_folder_id,
        value_cells_written=len(plan.value_cells),
        formula_cells_written=len(plan.formula_cells),
        protected_ranges_written=len(plan.protected_ranges),
        row_set_headers_written=sum(len(rs.columns) for rs in plan.row_sets),
        tab_count=len(tab_titles),
    )


def _new_target_export_preview(plan: SheetExportPlan) -> CalcSheetsExportPreview:
    """Preview a plan against a target with nothing on Drive to look up yet.

    Every value cell previews as new content and there is nothing to clear,
    because a real apply against this target would create the folder chain
    and the spreadsheet rather than diff against an existing one.
    """
    return CalcSheetsExportPreview(
        spreadsheet_exists=False,
        ranges_to_clear=(),
        value_cells_changed=len(written_cell_values(_plan_value_payload(plan))),
        value_cells_unchanged=0,
        formula_cells_to_write=len(plan.formula_cells),
    )


def preview_export_plan(
    plan: SheetExportPlan,
    *,
    credentials: Credentials,
    root_folder_id: str,
) -> CalcSheetsExportPreview:
    """Preview what :func:`apply_export_plan` would clear and (re)write, writing nothing.

    Resolves the same ``cadrumo-vault/calc-sheets/{modelo}-{period}-{year}/``
    target :func:`apply_export_plan` resolves, through the SAME read-only
    lookup (:func:`_find_folder` / :func:`_find_spreadsheet`) — never the
    create path — so a preview cannot disagree with a real apply about which
    spreadsheet it is describing. No folder or spreadsheet is created, and
    neither ``values.batchClear`` nor ``values.batchUpdate`` nor
    ``spreadsheets.batchUpdate`` is ever called.

    A target that does not yet exist previews via
    :func:`_new_target_export_preview`: every cell is new content and there is
    nothing to clear, because creating the target to answer the question would
    be exactly the write a preview exists to avoid.

    Args:
        plan: The pure :class:`~application.storage.calc_sheets.SheetExportPlan`
            a real apply would materialise.
        credentials: Same shape :func:`apply_export_plan` accepts.
        root_folder_id: The operator's Drive root folder id.

    Returns:
        A :class:`CalcSheetsExportPreview` describing what a real apply would
        touch.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`:
            When ``root_folder_id`` is blank, or an app-owned Drive entry
            carries no usable id.
        :exc:`~adapters.outbound.storage.OutboundStorageError`: When Drive or
            Sheets rejects a read request, or the adapter finds a same-named
            Drive entry that is not app-owned — the same refusal a real apply
            would raise at the same lookup.
    """
    _require_root_folder_id(root_folder_id)

    drive = _drive_service(credentials)
    sheets = _sheets_service(credentials)

    vault_folder = _find_folder(drive, parent_id=root_folder_id, name=_vault_folder_name())
    if vault_folder is None:
        return _new_target_export_preview(plan)
    vault_folder_id = require_drive_entry_id(vault_folder, name=_vault_folder_name(), parent_id=root_folder_id)

    calc_folder = _find_folder(drive, parent_id=vault_folder_id, name=_CALC_SHEETS_FOLDER_NAME)
    if calc_folder is None:
        return _new_target_export_preview(plan)
    calc_folder_id = require_drive_entry_id(calc_folder, name=_CALC_SHEETS_FOLDER_NAME, parent_id=vault_folder_id)

    period_folder_name = _subfolder_name(plan)
    period_folder = _find_folder(drive, parent_id=calc_folder_id, name=period_folder_name)
    if period_folder is None:
        return _new_target_export_preview(plan)
    period_folder_id = require_drive_entry_id(period_folder, name=period_folder_name, parent_id=calc_folder_id)

    title = _spreadsheet_title(plan)
    existing = _find_spreadsheet(drive, parent_id=period_folder_id, name=title)
    if existing is None:
        return _new_target_export_preview(plan)
    spreadsheet_id = require_drive_entry_id(existing, name=title, parent_id=period_folder_id)

    spreadsheet = execute_request(
        sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,spreadsheetUrl,sheets.properties",
        ),
        action="sheets.spreadsheets.get.preview",
    )
    spreadsheet_url = str(spreadsheet.get("spreadsheetUrl", ""))
    current_values = _current_cell_values(
        sheets=sheets,
        spreadsheet_id=spreadsheet_id,
        grid_by_tab=_grid_by_tab(spreadsheet),
    )
    occupied = frozenset(current_values)

    value_payload = _plan_value_payload(plan)
    formula_payload = build_formula_data(plan.formula_cells)
    written = payload_written_addresses(value_payload + formula_payload)
    ranges_to_clear = stale_addresses(occupied=occupied, written=written)

    target_values = written_cell_values(value_payload)
    changed = changed_cell_addresses(target=target_values, current=current_values)

    return CalcSheetsExportPreview(
        spreadsheet_exists=True,
        folder_id=period_folder_id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url or None,
        ranges_to_clear=ranges_to_clear,
        value_cells_changed=len(changed),
        value_cells_unchanged=len(target_values) - len(changed),
        formula_cells_to_write=len(plan.formula_cells),
    )


__all__ = [
    "CalcSheetsApplyResult",
    "CalcSheetsExportPreview",
    "apply_export_plan",
    "preview_export_plan",
]
