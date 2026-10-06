"""Publish saved review snapshots into fresh, receipt-bound native Google Sheets.

Every content request rechecks the known profile/root/creation receipt and
current folder containment. New documents use RAW literal values, a separate
intentional-formula channel, and a baseline check before publication. Published
copies are never repopulated: external review edits stay outside local authority.
Partial and uncertain publications retain their known identities for reconciliation.
"""

from __future__ import annotations

from asyncio import CancelledError
from typing import TYPE_CHECKING

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

from ....application.export.managed_artifact_ports import AdmittedArtifact, ManagedArtifactKind, ManagedArtifactPurpose
from ....application.export.publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from ....application.storage.calc_sheets.export_tables import (
    IDENTITY_STAMP_KEYS,
    RELATION_STAMP_PREFIX,
    export_identity_stamps,
)
from ....application.storage.calc_sheets.records import (
    AnySheetExportPlan,
    SheetCellAddress,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetValueCell,
    TabName,
)
from ....application.storage.calc_sheets.workbook_cells import validate_merged_content
from ....core.external_constants import GOOGLE_DRIVE_FOLDER_MIME_TYPE
from ....core.json_shapes import str_keyed_mapping, str_keyed_rows
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..storage.errors import OutboundStorageError, OutboundStorageValidationError
from ._calc_sheets_apply_formatting import (
    build_auto_filter_requests,
    build_base_font_requests,
    build_cell_constraint_requests,
    build_column_width_requests,
    build_emphasis_format_requests,
    build_form_geometry_requests,
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
    payload_written_addresses,
    stale_addresses,
    written_cell_values,
)
from ._calc_sheets_apply_values import (
    coerce_cell_value as coerce_cell_value,
)
from ._preconditions import google_terminal_refusal
from .api import (
    GoogleRequestExecutor,
    RequestRetryPolicy,
    _ExecutableRequest,
    execute_request,
)
from .artifact_admission import managed_artifact_refusal
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
from .managed_artifacts import ManagedGoogleArtifacts

_SPREADSHEET_MIME: Final[str] = "application/vnd.google-apps.spreadsheet"


class CalcSheetsApplyPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the calculation-sheet apply adapter."""

    API_CLIENT_AVAILABLE = "google.calc_sheets.apply.api_client_available"
    ROOT_FOLDER_ID_VALID = "google.calc_sheets.apply.root_folder_id_valid"


_CLIENT_UNAVAILABLE_CONDITION: Final[str] = CalcSheetsApplyPreconditionCondition.API_CLIENT_AVAILABLE.value


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
#: The stamp vocabulary is the plan's, so the cleanup pass below recognises
#: exactly the keys the shared stamp builder emits rather than a second list of
#: them that could outlive a rename.
_RELATION_METADATA_PREFIX: Final[str] = RELATION_STAMP_PREFIX
_MANAGED_DEVELOPER_METADATA_KEYS: Final[frozenset[str]] = frozenset(IDENTITY_STAMP_KEYS)


class CalcSheetsApplyResult(BaseModel):
    """Outcome of one apply cycle.

    Returned by :func:`~adapters.outbound.google.calc_sheets_apply.apply_export_plan` after
    a :class:`~application.storage.calc_sheets.records.SheetExportPlan` has been
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
    only: it never creates a folder or a spreadsheet and never issues a
    ``batchClear`` or ``batchUpdate`` write. The three facts a dry-run promises per the decision
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


def _find_folder(
    drive: DriveResource,
    *,
    parent_id: str,
    name: str,
) -> File | None:
    #
    # Ownership acceptance, refusal of unmarked or foreign content,
    # query-name escaping, and entry-id validation are the shared policy in
    # ``drive_entries``; only the MIME type and the action/error text are
    # folder-specific.
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type=GOOGLE_DRIVE_FOLDER_MIME_TYPE,
        list_action="drive.files.list",
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
        "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE,
        "parents": [parent_id],
        "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
    }
    return execute_request(
        drive.files().create(body=body, fields="id,name,appProperties"),
        action="drive.files.create.folder",
        retry=RequestRetryPolicy.SINGLE_ATTEMPT,
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
    # Same shared ownership and refusal policy as ``_find_folder``; only
    # the MIME type and the action/error text are spreadsheet-specific.
    return find_owned_drive_entry(
        drive,
        parent_id=parent_id,
        name=name,
        mime_type=_SPREADSHEET_MIME,
        list_action="drive.files.list.spreadsheet",
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
) -> Spreadsheet:
    """Create an owned native file in its destination before accessing Sheets."""
    body: File = {
        "name": title,
        "mimeType": _SPREADSHEET_MIME,
        "parents": [parent_id],
        "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
    }
    created = execute_request(
        drive.files().create(body=body, fields="id"),
        action="drive.files.create.spreadsheet",
        retry=RequestRetryPolicy.SINGLE_ATTEMPT,
    )
    spreadsheet_id = created.get("id")
    if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
        raise OutboundStorageValidationError(
            "Drive spreadsheet creation returned no usable identity",
            context={"action": "drive.files.create.spreadsheet", "effect_uncertain": True},
        )
    # Locale, plan tabs and grid sizing use the normal population path.
    return execute_request(
        sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,spreadsheetUrl,sheets.properties",
        ),
        action="sheets.spreadsheets.get.created",
        retry=RequestRetryPolicy.REPLAY_SAFE,
    )


def _developer_metadata_pairs(plan: AnySheetExportPlan) -> list[tuple[str, str]]:
    """Return the shared export identity stamps this transport carries as developer metadata."""
    return list(export_identity_stamps(plan))


def _build_developer_metadata_requests(
    plan: AnySheetExportPlan,
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
    plan: AnySheetExportPlan,
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
    plan: AnySheetExportPlan,
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
            retry=RequestRetryPolicy.REPLAY_SAFE,
        )
    return spreadsheet, period_folder_id


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _force_spreadsheet_locale(
    *, sheets: Any, spreadsheet_id: str, execute: GoogleRequestExecutor = execute_request
) -> None:
    # Parse generated formulas under the engine's invariant grammar. The shared
    # formatting pass subsequently applies the Spanish display locale.
    execute(
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
        retry=RequestRetryPolicy.REPLAY_SAFE,
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _ensure_plan_tabs_and_grid(
    *,
    execute: GoogleRequestExecutor = execute_request,
    sheets: SheetsResource,
    spreadsheet: Mapping[str, Any],
    spreadsheet_id: str,
    plan: AnySheetExportPlan,
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
        result = execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=add_sheet_body,
            ),
            action="sheets.spreadsheets.batchUpdate.add_missing_tabs",
            retry=RequestRetryPolicy.REPLAY_SAFE,
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
        execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=resize_body,
            ),
            action="sheets.spreadsheets.batchUpdate.resize_grid",
            retry=RequestRetryPolicy.REPLAY_SAFE,
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
    execute: GoogleRequestExecutor = execute_request,
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
    response = execute(
        sheets.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[item.address for item in ranges],
            valueRenderOption="UNFORMATTED_VALUE",
        ),
        action="sheets.spreadsheets.values.batchGet",
        retry=RequestRetryPolicy.REPLAY_SAFE,
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
def _plan_value_payload(plan: AnySheetExportPlan) -> list[ValueRange]:
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
    execute: GoogleRequestExecutor = execute_request,
    sheets: SheetsResource,
    spreadsheet_id: str,
    plan: AnySheetExportPlan,
) -> frozenset[str]:
    """Write the plan's values and formulas, and return the addresses written.

    Returning the written set is what makes the ordering structural rather
    than a convention: :func:`_clear_stale_addresses` cannot run before this
    function, because its input does not exist until this function returns.
    """
    # Literal text, including formula-looking user input, must remain literal.
    data = _plan_value_payload(plan)
    values_body: BatchUpdateValuesRequest = {"valueInputOption": "RAW", "data": data}
    execute(
        sheets.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=values_body,
        ),
        action="sheets.spreadsheets.values.batchUpdate",
        retry=RequestRetryPolicy.REPLAY_SAFE,
    )
    formulas = build_formula_data(plan.formula_cells)
    if formulas:
        _force_spreadsheet_locale(sheets=sheets, spreadsheet_id=spreadsheet_id, execute=execute)
        execute(
            sheets.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": formulas},
            ),
            action="sheets.spreadsheets.values.batchUpdate.formulas",
            retry=RequestRetryPolicy.SINGLE_ATTEMPT,
        )
    return payload_written_addresses(data + formulas)


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
        retry=RequestRetryPolicy.REPLAY_SAFE,
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GSHEETS: untyped google-api sheets Resource (dynamic discovery build).
def _apply_plan_structural_requests(
    *,
    execute: GoogleRequestExecutor = execute_request,
    sheets: SheetsResource,
    spreadsheet_id: str,
    spreadsheet: Mapping[str, Any],
    plan: AnySheetExportPlan,
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
        + build_form_geometry_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    )
    if structural_requests:
        structural_body: BatchUpdateSpreadsheetRequest = {"requests": structural_requests}
        execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=structural_body,
            ),
            action="sheets.spreadsheets.batchUpdate.structural",
            retry=RequestRetryPolicy.REPLAY_SAFE,
        )


def apply_export_plan(plan: SheetExportPlan, *, credentials: Credentials, root_folder_id: str) -> CalcSheetsApplyResult:
    """Refuse the retired mutable-template route before any provider access.

    Native review publication requires a selected immutable snapshot and its
    runtime-admitted PublicationReceipt through publish_review_plan.
    """
    _require_root_folder_id(root_folder_id)
    raise managed_artifact_refusal("selected_review_publication_required")


def _new_target_export_preview(plan: AnySheetExportPlan) -> CalcSheetsExportPreview:
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
    plan: AnySheetExportPlan, *, credentials: Credentials, root_folder_id: str
) -> CalcSheetsExportPreview:
    """Inventory a new publication locally without reading an earlier workbook."""
    _require_root_folder_id(root_folder_id)
    return _new_target_export_preview(plan)


class _AdmittedSheetRequests:
    """One known publication's requests; no hidden Google-client retries."""

    def __init__(self, artifacts: ManagedGoogleArtifacts, artifact: AdmittedArtifact) -> None:
        self.artifacts = artifacts
        self.artifact = artifact

    def __call__[ResponseBodyT](
        self, request: _ExecutableRequest[ResponseBodyT], *, action: str, retry: RequestRetryPolicy
    ) -> ResponseBodyT:
        writes = action not in {"sheets.spreadsheets.get.publication", "sheets.spreadsheets.values.batchGet"}
        if writes and self.artifact.purpose is not ManagedArtifactPurpose.PUBLICATION:
            raise managed_artifact_refusal("read_capability_cannot_populate")
        self.artifacts.admit(self.artifact.receipt, purpose=self.artifact.purpose)
        admission = self.artifacts.admission
        if admission.before_handoff is not None:
            admission.before_handoff(action, writes=writes)
        result = execute_request(request, action=action, retry=RequestRetryPolicy.SINGLE_ATTEMPT)
        if admission.acknowledged is not None:
            admission.acknowledged(action, writes=writes)
        return result


def publish_review_plan(
    plan: SheetExportPlan[SheetReviewMetadata],
    *,
    publication: PublicationReceipt,
    artifacts: ManagedGoogleArtifacts,
    sheets: SheetsResource,
) -> PublicationReceipt:
    """Create a fresh review copy and retain every acknowledged publication checkpoint.

    Completed retries return the recorded identity after admission without
    repopulation. Partial or uncertain publications require reconciliation.
    The caller supplies runtime-admitted transport and encrypted commit custody.
    """
    validate_merged_content(plan)
    if (
        publication.profile_id != artifacts.admission.profile_id
        or publication.root != artifacts.admission.root
        or plan.metadata.publication_id != publication.publication_id
        or plan.metadata.snapshot_digest != publication.snapshot_digest
    ):
        raise managed_artifact_refusal("publication_binding_mismatch")
    retained = artifacts.receipts.load_publication(publication.publication_id)
    name = f"{plan.metadata.title} [{publication.publication_id}]"
    if retained is not None:
        if (
            retained.profile_id != publication.profile_id
            or retained.root != publication.root
            or retained.snapshot_digest != publication.snapshot_digest
            or retained.package_digest != publication.package_digest
            or retained.predecessor_publication_id != publication.predecessor_publication_id
        ):
            raise managed_artifact_refusal("publication_replay_binding_mismatch")
        if retained.state is not PublicationState.PUBLISHED:
            raise managed_artifact_refusal("publication_requires_reconciliation", uncertain=True)
        for receipt in retained.artifacts:
            artifacts.admit(receipt, purpose=ManagedArtifactPurpose.ADMISSION)
        return retained
    if publication.state is not PublicationState.PREPARED:
        raise managed_artifact_refusal("new_publication_not_prepared")
    artifacts.receipts.save_publication(publication, previous=None)
    checkpoint = publication
    artifact = None
    failure = PublicationFailure.ADMISSION
    try:
        parent = artifacts.admit(publication.root, purpose=ManagedArtifactPurpose.PUBLICATION)
        artifact = artifacts.create(
            parent, name=name, kind=ManagedArtifactKind.REVIEW_SHEET, publication_id=publication.publication_id
        )
        failure = PublicationFailure.CUSTODY
        created = checkpoint.advance(PublicationState.REMOTE_CREATED, artifacts=(artifact,))
        artifacts.receipts.save_publication(created, previous=checkpoint)
        checkpoint = created
        failure = PublicationFailure.POPULATION
        writes = _AdmittedSheetRequests(
            artifacts, artifacts.admit(artifact, purpose=ManagedArtifactPurpose.PUBLICATION)
        )
        spreadsheet = writes(
            sheets.spreadsheets().get(
                spreadsheetId=artifact.artifact_id, fields="spreadsheetId,spreadsheetUrl,sheets.properties"
            ),
            action="sheets.spreadsheets.get.publication",
            retry=RequestRetryPolicy.SINGLE_ATTEMPT,
        )
        _force_spreadsheet_locale(sheets=sheets, spreadsheet_id=artifact.artifact_id, execute=writes)
        sheet_ids = _ensure_plan_tabs_and_grid(
            sheets=sheets,
            spreadsheet=spreadsheet,
            spreadsheet_id=artifact.artifact_id,
            plan=plan,
            tab_titles=tuple(tab.value for tab in plan.tabs),
            execute=writes,
        )
        # This identity was just created by this publication. Remove only its
        # provider-supplied default tabs after all planned tabs exist; never
        # apply this cleanup to a retained or previously published document.
        default_tabs: list[Request] = [
            {"deleteSheet": {"sheetId": identifier}}
            for title, identifier in sheet_ids.items()
            if title not in {tab.value for tab in plan.tabs}
        ]
        if default_tabs:
            writes(
                sheets.spreadsheets().batchUpdate(spreadsheetId=artifact.artifact_id, body={"requests": default_tabs}),
                action="sheets.spreadsheets.batchUpdate.remove_default_tabs",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
        _write_plan_values(sheets=sheets, spreadsheet_id=artifact.artifact_id, plan=plan, execute=writes)
        _apply_plan_structural_requests(
            sheets=sheets,
            spreadsheet_id=artifact.artifact_id,
            spreadsheet=spreadsheet,
            plan=plan,
            sheet_id_by_tab=sheet_ids,
            execute=writes,
        )
        failure = PublicationFailure.CUSTODY
        populated = checkpoint.advance(PublicationState.POPULATED)
        artifacts.receipts.save_publication(populated, previous=checkpoint)
        checkpoint = populated
        failure = PublicationFailure.INTEGRITY
        reads = _AdmittedSheetRequests(
            artifacts, artifacts.admit(artifact, purpose=ManagedArtifactPurpose.BASELINE_VERIFICATION)
        )
        structure = reads(
            sheets.spreadsheets().get(spreadsheetId=artifact.artifact_id, fields="sheets.properties"),
            action="sheets.spreadsheets.get.publication",
            retry=RequestRetryPolicy.SINGLE_ATTEMPT,
        )
        expected = written_cell_values(
            build_value_data(
                cell
                for cell in plan.value_cells
                if (cell.address.tab is not TabName.ENTRADAS and cell.role != "operator_input")
                or cell.role == "source_value"
            )
        )
        current: dict[str, object] = {}
        addresses = tuple(expected)
        # Fixed exported baseline cells only. Never inspect editable review
        # notes/scenarios, unused grid cells, or an earlier publication.
        for offset in range(0, len(addresses), 100):
            batch = addresses[offset : offset + 100]
            response = reads(
                sheets.spreadsheets()
                .values()
                .batchGet(
                    spreadsheetId=artifact.artifact_id, ranges=list(batch), valueRenderOption="UNFORMATTED_VALUE"
                ),
                action="sheets.spreadsheets.values.batchGet",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
            blocks = response.get("valueRanges", [])
            if len(blocks) != len(batch):
                raise managed_artifact_refusal("publication_baseline_response_incomplete")
            for address, block in zip(batch, blocks, strict=True):
                values = block.get("values", [])
                current[address] = values[0][0] if values and values[0] else ""
        actual_tabs = tuple(
            str(str_keyed_mapping(item.get("properties")).get("title", ""))
            for item in str_keyed_rows(structure, "sheets")
        )
        if actual_tabs != tuple(tab.value for tab in plan.tabs) or any(
            current.get(address, "") != value for address, value in expected.items()
        ):
            raise managed_artifact_refusal("publication_baseline_mismatch")
        artifacts.admit(artifact, purpose=ManagedArtifactPurpose.BASELINE_VERIFICATION)
        failure = PublicationFailure.CUSTODY
        verified = checkpoint.advance(PublicationState.VERIFIED)
        artifacts.receipts.save_publication(verified, previous=checkpoint)
        checkpoint = verified
        published = checkpoint.advance(PublicationState.PUBLISHED)
        artifacts.receipts.save_publication(published, previous=checkpoint)
        return published
    except BaseException as error:
        # Creation may have been acknowledged before a postcheck failed. Preserve
        # the exact local receipt instead of losing it from the failure journal.
        if artifact is None:
            attempt = artifacts.receipts.creation_attempt(
                parent=publication.root,
                name=name,
                kind=ManagedArtifactKind.REVIEW_SHEET,
                publication_id=publication.publication_id,
            )
            if attempt is None:
                # Admission failed before any creation intent or content call.
                # Retain PREPARED; do not invent an uncertain remote creation.
                raise
            artifact = attempt.receipt
        incomplete = checkpoint.advance(
            PublicationState.UNCERTAIN if artifact is None else PublicationState.PARTIAL,
            artifacts=() if artifact is None else (artifact,),
            failure=(
                PublicationFailure.CANCELLED
                if isinstance(error, CancelledError)
                else PublicationFailure.CREATE_UNKNOWN
                if artifact is None
                else failure
            ),
        )
        try:
            artifacts.receipts.save_publication(incomplete, previous=checkpoint)
        except Exception as custody_error:
            error.add_note(
                "The incomplete publication checkpoint could not be persisted; retained custody needs reconciliation."
            )
            raise error from custody_error
        raise
