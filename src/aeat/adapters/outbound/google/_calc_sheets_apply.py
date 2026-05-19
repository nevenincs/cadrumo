"""Live Google Sheets adapter that materialises a `SheetExportPlan`.

The adapter is the outbound boundary for the schema-to-sheet engine:
the engine produces a `SheetExportPlan` (a pure record), and this
module turns the plan into a real spreadsheet inside the operator's
`aeat-vault/` Drive folder. Every Drive folder and Sheets spreadsheet
the adapter touches carries the `appProperties.aeat_vault_app=aeat`
ownership marker so the operator's pre-existing Drive content is
isolated from app-owned artefacts.

Composition:

- Drive v3 hosts the parent folder structure (`aeat-vault/calc-sheets/
  {modelo}-{period}-{year}/`) and the spreadsheet file metadata.
- Sheets v4 reshapes the spreadsheet: tabs, cell values, formulas,
  protected ranges, and developer metadata stamping the engine
  version + registry SHA.

The adapter raises typed `OutboundStorageError` subclasses on Drive / Sheets
failures (e.g., `OutboundStoragePermissionError` for 401/403, `OutboundStorageNotFoundError`
for 404, `OutboundStorageConflictError` when refusing foreign Drive content),
with concrete remediation context attached.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from ....application.storage.calc_sheets import (
    SheetCellConstraint,
    SheetExportPlan,
    SheetFormulaCell,
    SheetProtectedRange,
    SheetRowSet,
    SheetValueCell,
    TabName,
)
from ....core.config import Settings as _Settings
from ...outbound.storage._errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)

_FOLDER_MIME: Final[str] = "application/vnd.google-apps.folder"
_SPREADSHEET_MIME: Final[str] = "application/vnd.google-apps.spreadsheet"
_VAULT_FOLDER_NAME: Final[str] = _Settings().aeat_google_drive_vault_folder_name
_CALC_SHEETS_FOLDER_NAME: Final[str] = "calc-sheets"
_OWNERSHIP_KEY: Final[str] = "aeat_vault_app"
_OWNERSHIP_VALUE: Final[str] = "aeat"


class CalcSheetsApplyResult(BaseModel):
    """Outcome of one apply cycle.

    Carries the spreadsheet's Drive file id, its Sheets URL, the
    `aeat-vault/calc-sheets/<...>/` Drive folder id (so the operator
    can navigate to the right place), and the count of cells / formulas
    / protected ranges actually written.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    spreadsheet_id: str = Field(min_length=1)
    spreadsheet_url: str = Field(min_length=1)
    folder_id: str = Field(min_length=1)
    value_cells_written: int = Field(ge=0)
    formula_cells_written: int = Field(ge=0)
    protected_ranges_written: int = Field(ge=0)
    row_set_headers_written: int = Field(ge=0, default=0)
    tab_count: int = Field(ge=1)


def _drive_service(credentials: object) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        ) from exc
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _sheets_service(credentials: object) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        ) from exc
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _execute(request: Any, *, action: str) -> Any:
    try:
        return request.execute()
    except OutboundStorageError:
        raise
    except Exception as exc:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
            if status in (401, 403):
                raise OutboundStoragePermissionError(
                    f"Google {action} refused (HTTP {status}): {exc}",
                    suggestion="aeat config google login",
                    context={"action": action, "status": status},
                    translated_message="adapters.google.calc_sheets.errors.api_call_refused",
                ) from exc
            if status == 404:
                raise OutboundStorageNotFoundError(
                    f"Google {action} target not found (HTTP 404): {exc}",
                    context={"action": action},
                    translated_message="adapters.google.calc_sheets.errors.api_target_not_found",
                ) from exc
        raise OutboundStorageNetworkError(
            f"Google {action} failed: {exc}",
            context={"action": action},
            translated_message="adapters.google.calc_sheets.errors.api_call_failed",
        ) from exc


def _find_folder(
    drive: Any,
    *,
    parent_id: str,
    name: str,
) -> dict[str, Any] | None:
    # ``dict[str, Any]`` is the irreducible Google Drive API boundary
    # shape: every response from drive.files().list() / .get() returns
    # heterogeneous typed metadata (id, name, mimeType, appProperties,
    # etc.) that the google-api-python-client stubs surface as ``Any``.
    # Narrowing breaks downstream lookups by string key. Same rationale
    # as the body-side ``Any`` documented on google_drive.py and on
    # browser/session.py.
    safe_name = name.replace("'", "\\'")
    query = f"'{parent_id}' in parents and name = '{safe_name}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
    response = _execute(
        drive.files().list(q=query, fields="files(id,name,appProperties)", pageSize=10),
        action="drive.files.list",
    )
    for entry in response.get("files", []):
        existing = entry.get("appProperties") or {}
        if existing.get(_OWNERSHIP_KEY) == _OWNERSHIP_VALUE:
            return entry
        if not existing:
            # Backfill the marker on a folder we created on a previous
            # run that predated marker stamping.
            _execute(
                drive.files().update(
                    fileId=entry["id"],
                    body={"appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE}},
                    fields="id,appProperties",
                ),
                action="drive.files.update.backfill_marker",
            )
            return entry
        raise OutboundStorageConflictError(
            f"folder named {name!r} under parent {parent_id!r} exists but is not marked as "
            "app-owned; refusing to adopt foreign Drive content",
            context={"parent_id": parent_id, "name": name},
            suggestion=(
                "either delete the existing folder, stamp "
                f"appProperties.{_OWNERSHIP_KEY}={_OWNERSHIP_VALUE} on it, "
                "or choose a different Drive root"
            ),
        )
    return None


def _create_folder(
    drive: Any,
    *,
    parent_id: str,
    name: str,
) -> dict[str, Any]:
    body = {
        "name": name,
        "mimeType": _FOLDER_MIME,
        "parents": [parent_id],
        "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
    }
    return _execute(
        drive.files().create(body=body, fields="id,name,appProperties"),
        action="drive.files.create.folder",
    )


def _ensure_folder(
    drive: Any,
    *,
    parent_id: str,
    name: str,
) -> str:
    existing = _find_folder(drive, parent_id=parent_id, name=name)
    if existing is not None:
        return existing["id"]
    created = _create_folder(drive, parent_id=parent_id, name=name)
    return created["id"]


def _find_spreadsheet(
    drive: Any,
    *,
    parent_id: str,
    name: str,
) -> dict[str, Any] | None:
    safe_name = name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and name = '{safe_name}' and mimeType = '{_SPREADSHEET_MIME}' and trashed = false"
    )
    response = _execute(
        drive.files().list(q=query, fields="files(id,name,appProperties)", pageSize=10),
        action="drive.files.list.spreadsheet",
    )
    for entry in response.get("files", []):
        existing = entry.get("appProperties") or {}
        if existing.get(_OWNERSHIP_KEY) == _OWNERSHIP_VALUE:
            return entry
        if not existing:
            _execute(
                drive.files().update(
                    fileId=entry["id"],
                    body={"appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE}},
                    fields="id,appProperties",
                ),
                action="drive.files.update.backfill_marker.spreadsheet",
            )
            return entry
        raise OutboundStorageConflictError(
            f"spreadsheet {name!r} exists under parent {parent_id!r} but is not marked as "
            "app-owned; refusing to overwrite",
            context={"parent_id": parent_id, "name": name},
        )
    return None


def _create_spreadsheet(
    drive: Any,
    sheets: Any,
    *,
    parent_id: str,
    title: str,
    tab_names: Iterable[str],
) -> dict[str, Any]:
    body = {
        # Locale `en_US` keeps the formula argument separator as ",".
        # Spanish-style display formatting (1.234,56) is applied at the
        # cell numberFormat level, which is independent of the
        # workbook's parsing locale. Using `es_ES` here would force
        # `;` as the argument separator and break every `ROUND(x,2)`
        # the engine emits.
        "properties": {"title": title, "locale": "en_US"},
        "sheets": [{"properties": {"title": tab_name}} for tab_name in tab_names],
    }
    spreadsheet = _execute(
        sheets.spreadsheets().create(body=body, fields="spreadsheetId,spreadsheetUrl,sheets.properties"),
        action="sheets.spreadsheets.create",
    )
    spreadsheet_id = spreadsheet["spreadsheetId"]
    # Move the freshly created spreadsheet into the target folder and
    # stamp the ownership marker. `files.update` with `addParents` +
    # `removeParents=root` is the canonical move pattern.
    file_meta = _execute(
        drive.files().get(fileId=spreadsheet_id, fields="parents"),
        action="drive.files.get.parents",
    )
    remove_parents = ",".join(file_meta.get("parents") or [])
    _execute(
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


def _coerce_cell_value(value: Decimal | str | bool | None) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        # Sheets accepts plain floats; render the Decimal as a fixed
        # decimal string so very small/very large values do not round.
        return format(value, "f")
    return str(value)


def _build_value_data(value_cells: Iterable[SheetValueCell]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for cell in value_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[_coerce_cell_value(cell.value)]],
            }
        )
    return data


def _build_formula_data(formula_cells: Iterable[SheetFormulaCell]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for cell in formula_cells:
        data.append(
            {
                "range": cell.address.qualified(),
                "values": [[f"={cell.formula}"]],
            }
        )
    return data


def _build_row_set_header_data(row_sets: Iterable[SheetRowSet]) -> list[dict[str, Any]]:
    """Emit Detalle-tab header cells declaring each row-set column.

    The engine reserves a header row + data area per row-set. This writer
    materialises the header labels so an operator opening the spreadsheet
    sees the per-record column titles ready to receive their tipo-2
    detail rows (perceptores on 190, foreign assets on 720, etc.).
    """

    data: list[dict[str, Any]] = []
    for row_set in row_sets:
        for column in row_set.columns:
            data.append(
                {
                    "range": column.header_address.qualified(),
                    "values": [[column.header_label]],
                }
            )
    return data


def _build_grid_resize_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Compute one `updateSheetProperties` request per tab that needs
    to grow beyond Sheets' default 1000-row / 26-column grid to hold
    the plan's value + formula cells.

    The function inspects every `SheetCellAddress` in the plan, finds
    the maximum row and column per tab, and emits a resize request
    when either exceeds the default. Tabs already wide enough get no
    request (Sheets accepts cell writes silently within the existing
    grid bound). Resizes always *grow*; we never shrink, so a tab the
    operator has manually expanded keeps its operator-set bound.
    """

    default_rows = 1000
    default_columns = 26
    # Generous headroom in case the operator pastes additional notes
    # below the engine's emitted rows; one extra row per 10 keeps
    # the grid from looking visually full.
    row_headroom = 50

    max_row: dict[str, int] = {}
    max_col: dict[str, int] = {}

    def bump(tab_value: str, row: int, column: int) -> None:
        if max_row.get(tab_value, 0) < row:
            max_row[tab_value] = row
        if max_col.get(tab_value, 0) < column:
            max_col[tab_value] = column

    for vcell in plan.value_cells:
        bump(vcell.address.tab.value, vcell.address.row, vcell.address.column)
    for fcell in plan.formula_cells:
        bump(fcell.address.tab.value, fcell.address.row, fcell.address.column)
    # Guide tab content is written via _build_guide_value_data which
    # extends a few rows past the title; reserve a generous floor.
    bump("Guía", 1 + len(plan.guide.paragraphs) + 10, 4)
    # Reserve grid space for each row-set on the Detalle tab. Each
    # row-set occupies header_row + 50 reserved data rows + 1 gap,
    # so the worst case is the last row-set's first_data_row + 50.
    for row_set in plan.row_sets:
        last_data_row = row_set.first_data_row + 50
        column_count = len(row_set.columns)
        bump(row_set.tab.value, last_data_row, column_count)

    requests: list[dict[str, Any]] = []
    for tab_value, max_r in max_row.items():
        sheet_id = sheet_id_by_tab.get(tab_value)
        if sheet_id is None:
            continue
        target_rows = max(max_r + row_headroom, default_rows)
        target_cols = max(max_col.get(tab_value, 1), default_columns)
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "rowCount": target_rows,
                            "columnCount": target_cols,
                        },
                    },
                    "fields": "gridProperties.rowCount,gridProperties.columnCount",
                }
            }
        )
    return requests


def _build_protected_range_requests(
    protected: Iterable[SheetProtectedRange],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for region in protected:
        sheet_id = sheet_id_by_tab.get(region.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": region.start_row - 1,
                            "endRowIndex": region.end_row,
                            "startColumnIndex": region.start_column - 1,
                            "endColumnIndex": region.end_column,
                        },
                        "description": region.description,
                        "warningOnly": False,
                        "editors": {"users": []},
                    }
                }
            }
        )
    return requests


def _build_cell_constraint_requests(
    constraints: Iterable[SheetCellConstraint],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Translate `SheetCellConstraint` records into Sheets API requests.

    Emits two requests per constrained cell:

    1. A `setDataValidation` request with a `condition` block that
       enforces the sign / min / max bounds. Sheets shows its own
       validation banner when an operator types an out-of-range
       value, and (with `strict = True`) refuses the input.
    2. An `updateCells` request that writes a `note` to the cell
       describing the constraint and the legal references that
       justify it. Operators see the grounding even before they
       attempt invalid input.
    """

    requests: list[dict[str, Any]] = []
    for constraint in constraints:
        sheet_id = sheet_id_by_tab.get(constraint.address.tab.value)
        if sheet_id is None:
            continue
        condition = _condition_for_constraint(constraint)
        if condition is None:
            continue
        cell_range = {
            "sheetId": sheet_id,
            "startRowIndex": constraint.address.row - 1,
            "endRowIndex": constraint.address.row,
            "startColumnIndex": constraint.address.column - 1,
            "endColumnIndex": constraint.address.column,
        }
        requests.append(
            {
                "setDataValidation": {
                    "range": cell_range,
                    "rule": {
                        "condition": condition,
                        "inputMessage": _input_message_for_constraint(constraint),
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            }
        )
        requests.append(
            {
                "updateCells": {
                    "range": cell_range,
                    "rows": [{"values": [{"note": _input_message_for_constraint(constraint)}]}],
                    "fields": "note",
                }
            }
        )
    return requests


def _condition_for_constraint(constraint: SheetCellConstraint) -> dict[str, Any] | None:
    """Resolve the tightest Sheets `BooleanCondition` for a constraint.

    Sheets supports `NUMBER_BETWEEN`, `NUMBER_GREATER_THAN_EQ`,
    `NUMBER_LESS_THAN_EQ`. We pick the strictest combination that
    matches the constraint's sign + range bounds.
    """

    lower = constraint.min_value
    upper = constraint.max_value
    if constraint.sign == "non_negative":
        floor = Decimal("0")
        lower = floor if lower is None else max(lower, floor)
    elif constraint.sign == "non_positive":
        ceiling = Decimal("0")
        upper = ceiling if upper is None else min(upper, ceiling)
    if lower is not None and upper is not None:
        return {
            "type": "NUMBER_BETWEEN",
            "values": [
                {"userEnteredValue": format(lower, "f")},
                {"userEnteredValue": format(upper, "f")},
            ],
        }
    if lower is not None:
        return {
            "type": "NUMBER_GREATER_THAN_EQ",
            "values": [{"userEnteredValue": format(lower, "f")}],
        }
    if upper is not None:
        return {
            "type": "NUMBER_LESS_THAN_EQ",
            "values": [{"userEnteredValue": format(upper, "f")}],
        }
    return None


def _input_message_for_constraint(constraint: SheetCellConstraint) -> str:
    parts: list[str] = []
    if constraint.sign == "non_negative":
        parts.append("≥ 0")
    elif constraint.sign == "non_positive":
        parts.append("≤ 0")
    if constraint.min_value is not None:
        parts.append(f"≥ {format(constraint.min_value, 'f')}")
    if constraint.max_value is not None:
        parts.append(f"≤ {format(constraint.max_value, 'f')}")
    bounds = " ∧ ".join(parts) if parts else "any"
    refs = ", ".join(constraint.legal_refs)
    return f"Casilla {constraint.casilla}: {bounds}. Refs: {refs}."


def _build_developer_metadata_requests(
    plan: SheetExportPlan,
) -> list[dict[str, Any]]:
    metadata = plan.metadata
    pairs: list[tuple[str, str]] = [
        ("aeat_engine_version", metadata.engine_version),
        ("aeat_registry_sha", metadata.registry_sha),
        ("aeat_modelo_id", metadata.modelo_id),
        ("aeat_revision_id", metadata.revision_id),
        ("aeat_filing_year", str(metadata.filing_year)),
        ("aeat_period", metadata.period),
        ("aeat_exported_at", metadata.exported_at.isoformat()),
    ]
    if plan.relation_provenance is not None:
        for relation in plan.relation_provenance.values:
            if relation.value is None and relation.provenance == "operator_manual":
                continue
            payload = {
                "value": str(relation.value) if relation.value is not None else "",
                "provenance": relation.provenance,
                "source_filing_year": str(relation.source_filing_year)
                if relation.source_filing_year is not None
                else "",
                "source_periods": "+".join(relation.source_periods),
                "resolved_at": relation.resolved_at.isoformat() if relation.resolved_at is not None else "",
            }
            pairs.append(
                (
                    f"aeat_relation:{relation.relation}",
                    "; ".join(f"{k}={v}" for k, v in payload.items() if v),
                )
            )
    return [
        {
            "createDeveloperMetadata": {
                "developerMetadata": {
                    "metadataKey": key,
                    "metadataValue": value,
                    "location": {"spreadsheet": True},
                    "visibility": "DOCUMENT",
                }
            }
        }
        for key, value in pairs
    ]


def _build_cell_note_requests(
    value_cells: Iterable[SheetValueCell],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Emit `updateCells` requests with cell notes for any value cell that has one."""

    requests: list[dict[str, Any]] = []
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
                }
            }
        )
    return requests


def _build_guide_value_data(plan: SheetExportPlan) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = [
        {"range": f"'{TabName.GUIDE.value}'!A1", "values": [[plan.guide.title]]},
    ]
    for index, paragraph in enumerate(plan.guide.paragraphs, start=3):
        data.append({"range": f"'{TabName.GUIDE.value}'!A{index}", "values": [[paragraph]]})
    metadata = plan.metadata
    base_row = 3 + len(plan.guide.paragraphs) + 2
    stamps = (
        ("Modelo", metadata.modelo_id),
        ("Revisión", metadata.revision_id),
        ("Período", f"{metadata.period} / {metadata.filing_year}"),
        ("Motor", metadata.engine_version),
        ("Registry SHA", metadata.registry_sha),
        ("Exportado", metadata.exported_at.isoformat()),
    )
    for offset, (label, value) in enumerate(stamps):
        data.append(
            {
                "range": f"'{TabName.GUIDE.value}'!A{base_row + offset}",
                "values": [[label, value]],
            }
        )
    return data


def _spreadsheet_title(plan: SheetExportPlan) -> str:
    metadata = plan.metadata
    return f"AEAT {metadata.modelo_id} {metadata.period} {metadata.filing_year}"


def _subfolder_name(plan: SheetExportPlan) -> str:
    metadata = plan.metadata
    return f"{metadata.modelo_id}-{metadata.period}-{metadata.filing_year}"


def apply_export_plan(
    plan: SheetExportPlan,
    *,
    credentials: object,
    root_folder_id: str,
) -> CalcSheetsApplyResult:
    """Materialise a `SheetExportPlan` as a real Google Sheets workbook.

    The adapter is idempotent at the spreadsheet level: applying the
    same plan twice updates the same spreadsheet rather than creating
    a duplicate, provided the per-period subfolder + spreadsheet
    title remain stable.

    Args:
        plan: The pure `SheetExportPlan` produced by the engine.
        credentials: A `google.oauth2.credentials.Credentials`-shaped
            object carrying refresh + access tokens with at least the
            `drive.file` + `spreadsheets` scopes.
        root_folder_id: The operator's Drive root folder id (the same
            folder `GoogleDriveProvider` uses for the ciphertext mirror).

    Returns:
        A `CalcSheetsApplyResult` with the spreadsheet's id and URL.

    Raises:
        OutboundStoragePermissionError: The Drive scope grant is insufficient
            (HTTP 401 / 403 mapped from `googleapiclient.errors.HttpError`).
        OutboundStorageNotFoundError: The supplied root folder id does not exist
            or is not visible to the operator (HTTP 404).
        OutboundStorageConflictError: A folder or spreadsheet matching the
            engine's target name exists but is not marked as app-owned.
        OutboundStorageNetworkError: A transport or unmapped HTTP failure.
        OutboundStorageValidationError: The plan is internally inconsistent or
            the supplied `root_folder_id` is blank.
    """

    if not root_folder_id.strip():
        raise OutboundStorageValidationError(
            "root_folder_id must not be blank",
            context={"root_folder_id": root_folder_id},
        )

    drive = _drive_service(credentials)
    sheets = _sheets_service(credentials)

    vault_folder_id = _ensure_folder(drive, parent_id=root_folder_id, name=_VAULT_FOLDER_NAME)
    calc_folder_id = _ensure_folder(drive, parent_id=vault_folder_id, name=_CALC_SHEETS_FOLDER_NAME)
    period_folder_id = _ensure_folder(drive, parent_id=calc_folder_id, name=_subfolder_name(plan))

    title = _spreadsheet_title(plan)
    existing = _find_spreadsheet(drive, parent_id=period_folder_id, name=title)
    tab_titles = tuple(tab.value for tab in TabName)
    if existing is None:
        spreadsheet = _create_spreadsheet(
            drive,
            sheets,
            parent_id=period_folder_id,
            title=title,
            tab_names=tab_titles,
        )
    else:
        spreadsheet = _execute(
            sheets.spreadsheets().get(
                spreadsheetId=existing["id"],
                fields="spreadsheetId,spreadsheetUrl,sheets.properties",
            ),
            action="sheets.spreadsheets.get",
        )

    spreadsheet_id = spreadsheet["spreadsheetId"]
    spreadsheet_url = spreadsheet["spreadsheetUrl"]

    # Force the workbook locale to `en_US` so the formula argument
    # separator stays a comma. Applies on every run so a workbook
    # created under a previous engine version (which may have used
    # `es_ES`) is corrected on the next export.
    _execute(
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSpreadsheetProperties": {
                            "properties": {"locale": "en_US"},
                            "fields": "locale",
                        }
                    }
                ]
            },
        ),
        action="sheets.spreadsheets.batchUpdate.locale",
    )

    sheet_id_by_tab: dict[str, int] = {}
    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties") or {}
        sheet_id_by_tab[str(props.get("title", ""))] = int(props.get("sheetId", 0))

    # Make sure every tab the engine expects actually exists. If the
    # spreadsheet predates a new tab, add it.
    missing_tabs = [tab for tab in tab_titles if tab not in sheet_id_by_tab]
    if missing_tabs:
        add_sheet_requests = [{"addSheet": {"properties": {"title": tab}}} for tab in missing_tabs]
        result = _execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": add_sheet_requests},
            ),
            action="sheets.spreadsheets.batchUpdate.add_missing_tabs",
        )
        for reply in result.get("replies", []):
            added = reply.get("addSheet", {}).get("properties") or {}
            sheet_id_by_tab[str(added.get("title", ""))] = int(added.get("sheetId", 0))

    # Resize each tab so the plan fits inside the grid. Sheets'
    # default grid is 1000 rows x 26 columns; large modelos (e.g.
    # 100 with 2235 casillas in Entradas) overflow that bound on
    # the first cell write. We compute the maximum row + column
    # each tab will receive in the upcoming batchUpdate and grow
    # the grid in one structural request before any value write.
    resize_requests = _build_grid_resize_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    if resize_requests:
        _execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": resize_requests},
            ),
            action="sheets.spreadsheets.batchUpdate.resize_grid",
        )

    # Clear every tab the engine will (re)populate so a re-apply is
    # not contaminated by leftover values from the previous run.
    clear_ranges = [f"'{tab}'" for tab in tab_titles]
    _execute(
        sheets.spreadsheets()
        .values()
        .batchClear(
            spreadsheetId=spreadsheet_id,
            body={"ranges": clear_ranges},
        ),
        action="sheets.spreadsheets.values.batchClear",
    )

    # Write values and formulas as USER_ENTERED so Sheets parses
    # formula strings starting with "=".
    value_data = (
        _build_value_data(plan.value_cells) + _build_guide_value_data(plan) + _build_row_set_header_data(plan.row_sets)
    )
    formula_data = _build_formula_data(plan.formula_cells)
    update_body = {
        "valueInputOption": "USER_ENTERED",
        "data": value_data + formula_data,
    }
    _execute(
        sheets.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=update_body,
        ),
        action="sheets.spreadsheets.values.batchUpdate",
    )

    # Apply structural metadata: protected ranges + developer
    # metadata for engine + registry identity + cell-level
    # constraint validation rules + cell notes carrying the
    # constraint and its legal grounding.
    metadata_requests = _build_developer_metadata_requests(plan)
    protected_requests = _build_protected_range_requests(
        plan.protected_ranges,
        sheet_id_by_tab=sheet_id_by_tab,
    )
    constraint_requests = _build_cell_constraint_requests(
        plan.cell_constraints,
        sheet_id_by_tab=sheet_id_by_tab,
    )
    note_requests = _build_cell_note_requests(
        plan.value_cells,
        sheet_id_by_tab=sheet_id_by_tab,
    )
    structural_requests = metadata_requests + protected_requests + constraint_requests + note_requests
    if structural_requests:
        _execute(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": structural_requests},
            ),
            action="sheets.spreadsheets.batchUpdate.structural",
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


__all__ = [
    "CalcSheetsApplyResult",
    "apply_export_plan",
]
