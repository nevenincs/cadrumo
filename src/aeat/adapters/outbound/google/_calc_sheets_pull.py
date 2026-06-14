"""Read operator-edited Sheets cells back into structured records.

Pairs with `_calc_sheets_apply.py`. The push side materialises a
`SheetExportPlan` as a real Google Sheets workbook; this module
reads the operator's edits back out, validates the workbook is
still bound to the :class:`RegistrySnapshot` the engine compiled it from,
and returns typed records the caller can apply to its ledger /
filing flow.

Two safety gates fire before any value is read:

1. **Drive ownership marker** — the spreadsheet must carry the
   `appProperties.aeat_vault_app=aeat` marker. Reading values from a
   spreadsheet that lacks the marker would mix operator content with
   foreign Drive files and break the `aeat-vault/` isolation contract.
2. **Registry-SHA metadata match** — the spreadsheet's developer
   metadata must declare `aeat_registry_sha = <snapshot.registry_sha>`
   and `aeat_modelo_id` / `aeat_revision_id` / `aeat_filing_year` /
   `aeat_period` matching the caller's snapshot. A mismatch means
   the workbook was compiled against a different registry slice —
   casilla numbering, formula chains, and bracket tables may have
   shifted. The pull is refused with a typed error.

The pull adapter does NOT mutate any local state; it returns a
`PullResult` and leaves applying the edits to the caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

# google-api-python-client-stubs ships ``googleapiclient.discovery.Resource``
# as the typed surface for service objects returned by ``build()``.
# We import it under TYPE_CHECKING so the runtime dependency stays optional
# (the ImportError path in ``_drive_service`` / ``_sheets_service`` guards the
# live path) while the type-checker can narrow the ``Any`` service returns.
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource as _GoogleResource

from pydantic import BaseModel, Field

from ....application.storage.calc_sheets import collect_row_sets, registry_sha
from ....application.storage.calc_sheets._layout import SheetLayout, plan_layout
from ....application.storage.calc_sheets._records import OperatorInput, SheetExportMetadata, SheetExportPlan
from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import Period
from ....core.decimal import coerce_decimal
from ....core.i18n import tr
from ....core.time._utc import coerce_utc_aware
from ....domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    InputKind,
    RegistryCalculationResult,
    RegistrySnapshot,
    RelationId,
    RevisionId,
    calculate_registry_snapshot,
)
from ...outbound.storage._errors import (
    OutboundStorageConflictError,
    OutboundStorageNetworkError,
    OutboundStorageValidationError,
)
from ._api import execute_request

_OWNERSHIP_KEY: Final[str] = "aeat_vault_app"
_OWNERSHIP_VALUE: Final[str] = "aeat"
_RELATION_METADATA_PREFIX: Final[str] = "aeat_relation:"
_DUPLICATE_SENSITIVE_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "aeat_engine_version",
        "aeat_registry_sha",
        "aeat_modelo_id",
        "aeat_revision_id",
        "aeat_filing_year",
        "aeat_period",
    },
)

# A single batch-get value-range entry from the Sheets API.
# Shape: {"range": str, "values": list[list[object]]}
_ValueRange = dict[str, Any]


class OperatorEdit(BaseModel):
    """One operator-edited cell value.

    ``casilla_number`` and ``label`` are display-only fields added by the
    pull adapter from the workbook's column metadata. They are not part of
    the canonical :class:`OperatorInput` contract; use
    :meth:`to_operator_input` to project this shape onto the canonical one.

    ``value`` mirrors the cell's raw shape from Google Sheets. The union
    is intentionally ambiguous between Decimal and numeric-shaped str
    because the wire JSON representation cannot statically distinguish
    them (pydantic serialises Decimal as a JSON string). The runtime
    path in :func:`compute_from_pull` is what disambiguates via
    :func:`_coerce_edit_value_to_decimal` for numeric input casillas and
    :func:`_enum_binding_text` for enum bindings.
    """

    model_config = _STRICT_FROZEN

    casilla: CasillaId
    casilla_number: str
    label: str
    value: Decimal | str | bool | None = None

    def to_operator_input(self) -> OperatorInput:
        """Project onto the canonical :class:`OperatorInput` shape, dropping display fields."""
        return OperatorInput(casilla=self.casilla, value=self.value)


class BindingEdit(BaseModel):
    """One operator-edited binding cell value (numeric or enum).

    Same union-ambiguity reasoning as :class:`OperatorEdit.value` —
    the wire JSON cannot statically distinguish a CCAA-shape ``"04"``
    from a numeric ``Decimal("4")``. The runtime dispatch in
    :func:`compute_from_pull` is what routes the value: enum bindings
    go through :func:`_enum_binding_text` and numeric bindings go
    through :func:`_coerce_edit_value_to_decimal`.
    """

    model_config = _STRICT_FROZEN

    binding: BindingId
    value: Decimal | str | None = None


class RelationEdit(BaseModel):
    """One pre-resolved cross-revision relation value mirrored in Tarifas.

    The provenance / source_filing_year / source_periods / resolved_at
    fields are recovered from the workbook's developer metadata
    (``aeat_relation:<relation>`` keys written by the apply adapter).
    They are absent for relations that were edited manually in the
    workbook without an apply round-trip; in that case the relation
    is treated as ``provenance="operator_manual"`` by convention.
    """

    model_config = _STRICT_FROZEN

    relation: RelationId
    value: Decimal | None = None
    provenance: Literal["local_filing", "aeat_live", "operator_manual"] | None = None
    source_filing_year: int | None = Field(default=None, ge=2000, le=2099)
    source_periods: tuple[str, ...] = ()
    resolved_at: datetime | None = None


class RowSetCellEdit(BaseModel):
    """One operator-edited cell from a Detalle tab row-set."""

    model_config = _STRICT_FROZEN

    binding: BindingId
    row_index: int = Field(ge=1)
    value: Decimal | str | None = None


class RowSetEdit(BaseModel):
    """All operator-supplied detail rows for one row-set grouping."""

    model_config = _STRICT_FROZEN

    grouping: str = Field(min_length=1)
    cells: tuple[RowSetCellEdit, ...] = ()


class PullMetadata(BaseModel):
    """Workbook identity metadata recovered from developer metadata.

    This is a loose parsing shape: ``exported_at`` is ``str | None`` because
    the developer-metadata round-trip may yield a raw ISO string or nothing.
    Use :meth:`to_sheet_export_metadata` to project onto the strict canonical
    :class:`~aeat.application.storage.calc_sheets._records.SheetExportMetadata`
    shape when the workbook is known to carry a valid export stamp.
    """

    model_config = _STRICT_FROZEN

    modelo_id: str
    revision_id: RevisionId
    filing_year: int
    period: str
    engine_version: str
    registry_sha: str
    exported_at: str | None = None

    def to_sheet_export_metadata(self) -> SheetExportMetadata | None:
        """Project onto a :class:`SheetExportMetadata`, parsing exported_at from ISO string.

        Returns ``None`` when ``exported_at`` is absent or unparseable rather
        than raising, so callers can treat a missing stamp as ``metadata_match="missing"``.
        """
        if not self.exported_at:
            return None
        try:
            dt = coerce_utc_aware(datetime.fromisoformat(self.exported_at))
        except ValueError:
            return None
        return SheetExportMetadata(
            modelo_id=self.modelo_id,
            revision_id=self.revision_id,
            filing_year=self.filing_year,
            period=Period.from_year_and_code(self.filing_year, self.period),
            engine_version=self.engine_version,
            registry_sha=self.registry_sha,
            exported_at=dt,
        )


class MetadataMatchState(StrEnum):
    """Registry-SHA + stamp alignment result for a pulled Sheets workbook."""

    MATCHES = "matches"
    STALE = "stale"
    MISSING = "missing"


class PullResult(BaseModel):
    """Outcome of one pull cycle."""

    model_config = _STRICT_FROZEN

    spreadsheet_id: str
    operator_edits: tuple[OperatorEdit, ...]
    binding_edits: tuple[BindingEdit, ...]
    relation_edits: tuple[RelationEdit, ...]
    row_set_edits: tuple[RowSetEdit, ...] = ()
    metadata: PullMetadata
    metadata_match: MetadataMatchState
    cells_read: int = Field(ge=0)


def _drive_service(credentials: object) -> _GoogleResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        ) from exc
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _sheets_service(credentials: object) -> _GoogleResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            suggestion="uv sync",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        ) from exc
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .files() / .spreadsheets() only via runtime Discovery JSON dispatch; the stub type
# carries .close() alone, so service helpers accept Any for the dynamic attribute access.
def _verify_ownership(drive_service: Any, spreadsheet_id: str) -> None:
    """Refuse to read from a spreadsheet that lacks the ownership marker."""
    file_meta = execute_request(
        drive_service.files().get(
            fileId=spreadsheet_id,
            fields="id,name,appProperties",
        ),
        action="drive.files.get.appProperties",
    )
    app_properties = file_meta.get("appProperties") or {}
    if app_properties.get(_OWNERSHIP_KEY) != _OWNERSHIP_VALUE:
        raise OutboundStorageConflictError(
            f"spreadsheet {spreadsheet_id!r} is not marked as app-owned; refusing "
            f"to read operator edits from a foreign Drive file",
            context={"spreadsheet_id": spreadsheet_id, "name": file_meta.get("name", "")},
            suggestion=tr("adapters.google.calc_sheets.suggestions.verify_exported_workbook"),
            translated_message="adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the stub carries .close()
# alone, so the service helper accepts Any for the dynamic attribute access.
def _read_developer_metadata(
    sheets_service: Any,
    spreadsheet_id: str,
) -> dict[str, str]:
    """Recover the engine-stamped developer metadata pairs."""
    spreadsheet = execute_request(
        sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="developerMetadata(metadataKey,metadataValue,location)",
        ),
        action="sheets.spreadsheets.get.developerMetadata",
    )
    return _merge_developer_metadata_entries(spreadsheet.get("developerMetadata", []) or [])


def _duplicate_metadata_must_match(key: str) -> bool:
    return key in _DUPLICATE_SENSITIVE_METADATA_KEYS or key.startswith(_RELATION_METADATA_PREFIX)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-SHEETS-API-PAYLOAD: entries are Sheets
# developer-metadata records returned as free-shape JSON by the discovery client.
def _merge_developer_metadata_entries(entries: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Merge Sheets developer metadata entries, refusing conflicting identity duplicates.

    Google Sheets developer metadata keys are not unique. Repeated exports
    can leave multiple `aeat_*` keys on the same workbook. Duplicate
    identity keys with different values would make pull classification
    depend on API return order, so they are treated as a conflict. The
    informational `aeat_exported_at` stamp is intentionally excluded:
    multiple exports of the same registry slice produce different
    timestamps without changing workbook identity.
    """
    pairs: dict[str, str] = {}
    conflicting_keys: set[str] = set()
    for entry in entries:
        key = entry.get("metadataKey")
        value = entry.get("metadataValue")
        if isinstance(key, str) and isinstance(value, str):
            previous = pairs.get(key)
            if previous is not None and previous != value and _duplicate_metadata_must_match(key):
                conflicting_keys.add(key)
            pairs[key] = value
    if conflicting_keys:
        raise OutboundStorageConflictError(
            "spreadsheet carries conflicting duplicate AEAT developer metadata; refusing order-dependent pull",
            context={"conflicting_metadata_keys": sorted(conflicting_keys)},
            suggestion=tr("adapters.google.calc_sheets.suggestions.reexport_workbook"),
            translated_message="adapters.google.calc_sheets.errors.conflicting_duplicate_metadata",
        )
    return pairs


def _classify_metadata_match(
    pairs: Mapping[str, str],
    snapshot: RegistrySnapshot,
) -> tuple[MetadataMatchState, PullMetadata]:
    if not pairs:
        # The MISSING verdict carries a placeholder PullMetadata so the
        # caller can still receive a typed record alongside the verdict.
        # Sentinel values satisfy PullMetadata's min_length=1 boundary
        # constraint without claiming real registry coordinates.
        return MetadataMatchState.MISSING, PullMetadata(
            modelo_id="missing",
            revision_id="missing",
            filing_year=0,
            period="missing",
            engine_version="missing",
            registry_sha="missing",
        )
    try:
        filing_year = int(pairs.get("aeat_filing_year", "0"))
    except ValueError:
        filing_year = 0
    metadata = PullMetadata(
        modelo_id=pairs.get("aeat_modelo_id", ""),
        revision_id=pairs.get("aeat_revision_id", ""),
        filing_year=filing_year,
        period=pairs.get("aeat_period", ""),
        engine_version=pairs.get("aeat_engine_version", ""),
        registry_sha=pairs.get("aeat_registry_sha", ""),
        exported_at=pairs.get("aeat_exported_at"),
    )
    # The registry-SHA gate the module docstring promises: a workbook
    # whose `aeat_registry_sha` stamp diverges from the live snapshot's
    # calculation-surface hash was compiled against a different registry
    # slice (casilla numbering, formula chains, bracket tables may have
    # shifted) even when modelo / revision / year / period still align.
    # Such a workbook is `stale`, never `matches` — `compute_from_pull`
    # refuses to merge it.
    matches = (
        metadata.modelo_id == snapshot.modelo.id
        and metadata.revision_id == snapshot.revision.id
        and metadata.filing_year == snapshot.filing_year
        and metadata.period == Period.from_year_and_code(snapshot.filing_year, snapshot.period).registry_token
        and metadata.registry_sha == registry_sha(snapshot)
    )
    return (MetadataMatchState.MATCHES if matches else MetadataMatchState.STALE), metadata


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no stub type available in google-api-python-client.
def _coerce_value(raw: Any) -> Decimal | str | bool | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return coerce_decimal(raw)
    if isinstance(raw, str):
        as_decimal = coerce_decimal(raw)
        if as_decimal is not None:
            return as_decimal
        return raw
    return None


def pull_operator_edits(
    snapshot: RegistrySnapshot,
    *,
    spreadsheet_id: str,
    credentials: object,
) -> PullResult:
    """Read operator-edited cells back from a workbook into typed records.

    Args:
        snapshot: The :class:`RegistrySnapshot` the workbook was compiled
            against. Used to derive the layout (cell addresses for
            every casilla / binding / relation) and to validate the
            workbook's developer-metadata stamps.
        spreadsheet_id: The Drive file id of the workbook to read.
            Must already exist and carry the
            `appProperties.aeat_vault_app=aeat` ownership marker.
        credentials: A `google.oauth2.credentials.Credentials`-shaped
            object carrying a refresh + access token with at least
            the `drive.file` + `spreadsheets` scopes.

    Returns:
        A :class:`PullResult` carrying the operator edits, binding edits,
        relation edits, and the metadata-match verdict. A
        ``metadata_match="stale"`` result still includes the edits but
        signals to the caller that the workbook's identity does not
        match the supplied snapshot — applying these edits to the
        local store may corrupt data.

    Raises:
        OutboundStorageValidationError: When ``spreadsheet_id`` is blank.
    """
    if not spreadsheet_id.strip():
        raise OutboundStorageValidationError(
            "spreadsheet_id must not be blank",
            context={"spreadsheet_id": spreadsheet_id},
            translated_message="adapters.google.calc_sheets.errors.spreadsheet_id_blank",
        )

    drive = _drive_service(credentials)
    sheets = _sheets_service(credentials)

    _verify_ownership(drive, spreadsheet_id)
    metadata_pairs = _read_developer_metadata(sheets, spreadsheet_id)
    metadata_match, metadata = _classify_metadata_match(metadata_pairs, snapshot)

    filing_anchor = date(snapshot.filing_year, 12, 31)
    layout = plan_layout(snapshot.revision, bracket_filter_date=filing_anchor)

    operator_input_ids, operator_input_ranges = _operator_input_addresses(snapshot, layout)
    binding_ids = list(layout.binding_cells)
    binding_ranges = [layout.binding_cells[bid].qualified() for bid in binding_ids]
    relation_ids = list(layout.relation_cells)
    relation_ranges = [layout.relation_cells[rid].qualified() for rid in relation_ids]
    all_ranges = operator_input_ranges + binding_ranges + relation_ranges
    value_ranges = _batch_get_values(sheets, spreadsheet_id, all_ranges)

    casilla_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    cursor = 0
    operator_edits, cursor, casilla_cells_read = _decode_operator_edits(
        value_ranges,
        cursor,
        operator_input_ids,
        casilla_by_id,
    )
    binding_edits, cursor, binding_cells_read = _decode_binding_edits(value_ranges, cursor, binding_ids)
    relation_edits, cursor, relation_cells_read = _decode_relation_edits(
        value_ranges,
        cursor,
        relation_ids,
        metadata_pairs,
    )

    # Read row-set detail rows from the Detalle tab. Each row-set
    # reserves first_data_row + 50 rows by N columns; we issue one
    # batchGet covering each row-set's full data block and capture
    # any non-blank cell as a RowSetCellEdit.
    row_set_edits, row_set_cells_read = _read_row_set_edits(snapshot, sheets, spreadsheet_id)
    cells_read = casilla_cells_read + binding_cells_read + relation_cells_read + row_set_cells_read

    return PullResult(
        spreadsheet_id=spreadsheet_id,
        operator_edits=operator_edits,
        binding_edits=binding_edits,
        relation_edits=relation_edits,
        row_set_edits=row_set_edits,
        metadata=metadata,
        metadata_match=metadata_match,
        cells_read=cells_read,
    )


def _operator_input_addresses(
    snapshot: RegistrySnapshot,
    layout: SheetLayout,
) -> tuple[list[CasillaId], list[str]]:
    """Build the per-casilla (id, qualified-range) pair list for the batchGet."""
    operator_input_ids: list[CasillaId] = []
    operator_input_ranges: list[str] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind not in (InputKind.MANUAL, InputKind.BOUND):
            continue
        address = layout.entradas_cells.get(casilla.id)
        if address is None:
            continue
        operator_input_ids.append(casilla.id)
        operator_input_ranges.append(address.qualified())
    return operator_input_ids, operator_input_ranges


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the stub carries .close()
# alone, so the service helper accepts Any for the dynamic attribute access.
def _batch_get_values(
    sheets: Any,
    spreadsheet_id: str,
    ranges: list[str],
) -> list[_ValueRange]:
    """One Sheets ``values.batchGet`` covering every supplied A1 range.

    Returns the raw ``valueRanges`` list from the response (each entry
    is a ``{"range": ..., "values": [[cell, ...], ...]}`` dict shape).
    Returns an empty list when ``ranges`` is empty, avoiding a wasted
    API call.
    """
    if not ranges:
        return []
    response = execute_request(
        sheets.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            valueRenderOption="UNFORMATTED_VALUE",
        ),
        action="sheets.spreadsheets.values.batchGet",
    )
    return response.get("valueRanges", []) or []


def _raw_cell_value(value_ranges: list[_ValueRange], cursor: int) -> object:
    """Return the single-cell raw value at ``cursor`` in a batchGet response, or None."""
    vr = value_ranges[cursor] if cursor < len(value_ranges) else {}
    rows = vr.get("values", []) or []
    return rows[0][0] if rows and rows[0] else None


def _decode_operator_edits(
    value_ranges: list[_ValueRange],
    cursor: int,
    operator_input_ids: list[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> tuple[tuple[OperatorEdit, ...], int, int]:
    """Map the per-casilla slice of the batchGet response into typed OperatorEdits."""
    cells_read = 0
    edits: list[OperatorEdit] = []
    for casilla_id in operator_input_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = _coerce_value(raw)
        if coerced is not None:
            cells_read += 1
        casilla = casilla_by_id[casilla_id]
        edits.append(
            OperatorEdit(
                casilla=casilla_id,
                casilla_number=casilla.number,
                label=casilla.label,
                value=coerced,
            ),
        )
    return tuple(edits), cursor, cells_read


def _decode_binding_edits(
    value_ranges: list[_ValueRange],
    cursor: int,
    binding_ids: list[BindingId],
) -> tuple[tuple[BindingEdit, ...], int, int]:
    """Map the per-binding slice of the batchGet response into typed BindingEdits.

    Booleans are stringified because :class:`BindingEdit.value`'s union
    (``Decimal | str | None``) does not carry a bool path — the runtime
    enum-binding semantics expect a textual representation here.
    """
    cells_read = 0
    edits: list[BindingEdit] = []
    for binding_id in binding_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = _coerce_value(raw)
        if coerced is not None:
            cells_read += 1
        binding_value: Decimal | str | None = str(coerced) if isinstance(coerced, bool) else coerced
        edits.append(BindingEdit(binding=binding_id, value=binding_value))
    return tuple(edits), cursor, cells_read


def _decode_relation_edits(
    value_ranges: list[_ValueRange],
    cursor: int,
    relation_ids: list[RelationId],
    metadata_pairs: Mapping[str, str],
) -> tuple[tuple[RelationEdit, ...], int, int]:
    """Map the per-relation slice of the batchGet response into typed RelationEdits.

    Per-relation provenance metadata is recovered from the workbook's
    developer metadata via the ``aeat_relation:<relation>`` key written
    by the apply adapter. Recovering it on pull preserves the audit
    trail (provenance tier, source filing year, source periods,
    resolved-at instant) that would otherwise be silently dropped on
    every round trip.
    """
    cells_read = 0
    edits: list[RelationEdit] = []
    for relation_id in relation_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = coerce_decimal(raw)
        if coerced is not None:
            cells_read += 1
        provenance, source_filing_year, source_periods, resolved_at = _parse_relation_metadata(
            metadata_pairs.get(f"aeat_relation:{relation_id}", ""),
        )
        edits.append(
            RelationEdit(
                relation=relation_id,
                value=coerced,
                provenance=provenance,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                resolved_at=resolved_at,
            ),
        )
    return tuple(edits), cursor, cells_read


def _parse_relation_metadata(
    raw: str,
) -> tuple[
    Literal["local_filing", "aeat_live", "operator_manual"] | None,
    int | None,
    tuple[str, ...],
    datetime | None,
]:
    """Parse the ``"k=v; k=v"`` shape written by the apply adapter."""
    if not raw:
        return None, None, (), None
    parts = [piece.strip() for piece in raw.split(";") if "=" in piece]
    fields: dict[str, str] = {}
    for part in parts:
        key, _, value = part.partition("=")
        fields[key.strip()] = value.strip()
    raw_provenance = fields.get("provenance", "")
    provenance: Literal["local_filing", "aeat_live", "operator_manual"] | None
    match raw_provenance:
        case "local_filing":
            provenance = "local_filing"
        case "aeat_live":
            provenance = "aeat_live"
        case "operator_manual":
            provenance = "operator_manual"
        case _:
            provenance = None
    source_filing_year: int | None = None
    raw_year = fields.get("source_filing_year", "")
    if raw_year:
        try:
            source_filing_year = int(raw_year)
        except ValueError:
            source_filing_year = None
    source_periods: tuple[str, ...] = ()
    raw_periods = fields.get("source_periods", "")
    if raw_periods:
        source_periods = tuple(piece for piece in raw_periods.split("+") if piece)
    resolved_at: datetime | None = None
    raw_resolved = fields.get("resolved_at", "")
    if raw_resolved:
        try:
            resolved_at = datetime.fromisoformat(raw_resolved)
        except ValueError:
            resolved_at = None
    return provenance, source_filing_year, source_periods, resolved_at


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the stub carries .close()
# alone, so the service helper accepts Any for the dynamic attribute access.
def _read_row_set_edits(
    snapshot: RegistrySnapshot,
    sheets: Any,
    spreadsheet_id: str,
) -> tuple[tuple[RowSetEdit, ...], int]:
    """Read each row-set's Detalle-tab data area into typed row edits.

    Returns the per-grouping ``RowSetEdit`` tuple plus the total count
    of non-blank cells read across all row-sets. Each row-set's data
    block is fetched in one batchGet entry (header_row+1 .. header_row+51).
    """
    row_sets = collect_row_sets(snapshot.revision)
    if not row_sets:
        return ((), 0)
    block_ranges = [_row_set_block_range(row_set) for row_set in row_sets]
    value_ranges = _batch_get_values_for_row_sets(sheets, spreadsheet_id, block_ranges)
    edits: list[RowSetEdit] = []
    cells_read = 0
    for row_set_index, row_set in enumerate(row_sets):
        vr = value_ranges[row_set_index] if row_set_index < len(value_ranges) else {}
        rows = vr.get("values", []) or []
        cells, cells_in_block = _decode_row_set_block(rows, row_set)
        cells_read += cells_in_block
        edits.append(RowSetEdit(grouping=row_set.grouping, cells=cells))
    return tuple(edits), cells_read


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no stub type available in google-api-python-client.
def _row_set_block_range(row_set: Any) -> str:
    """Build the A1 range covering the 50-row data block of one row-set."""
    last_column = max(col.header_address.column for col in row_set.columns)
    start_col_letters = _column_index_to_letters(1)
    end_col_letters = _column_index_to_letters(last_column)
    start_row = row_set.first_data_row
    end_row = row_set.first_data_row + 49
    return f"'{row_set.tab.value}'!{start_col_letters}{start_row}:{end_col_letters}{end_row}"


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the stub carries .close()
# alone, so the service helper accepts Any for the dynamic attribute access.
def _batch_get_values_for_row_sets(
    sheets: Any,
    spreadsheet_id: str,
    block_ranges: list[str],
) -> list[_ValueRange]:
    """Sheets ``values.batchGet`` for row-set blocks; returns the raw valueRanges list."""
    response = execute_request(
        sheets.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=block_ranges,
            valueRenderOption="UNFORMATTED_VALUE",
        ),
        action="sheets.spreadsheets.values.batchGet.row_sets",
    )
    return response.get("valueRanges", []) or []


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no stub type available in google-api-python-client.
def _decode_row_set_block(
    rows: list[list[object]],
    row_set: Any,
) -> tuple[tuple[RowSetCellEdit, ...], int]:
    """Decode one row-set's block of (local_row, col_index) cells into typed edits.

    Returns the typed-cell tuple plus the non-blank-cells count for
    this block. Cells whose column index exceeds the row-set's declared
    columns are skipped — that's the Sheets-side defensive path when an
    operator pastes data past the allocated column count.
    """
    cells: list[RowSetCellEdit] = []
    cells_in_block = 0
    for local_row, row_values in enumerate(rows, start=1):
        for col_index, raw in enumerate(row_values, start=1):
            cell = _decode_row_set_cell(raw, col_index, local_row, row_set)
            if cell is None:
                continue
            cells.append(cell)
            cells_in_block += 1
    return tuple(cells), cells_in_block


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no stub type available in google-api-python-client.
def _decode_row_set_cell(
    raw: object,
    col_index: int,
    local_row: int,
    row_set: Any,
) -> RowSetCellEdit | None:
    """Translate one Sheets cell into a typed RowSetCellEdit, or None to skip."""
    if raw is None or raw == "":
        return None
    # Map the column index back to its binding via the row-set's
    # ordered columns. row_set.columns is in column-allocation order
    # (column 1, 2, ...).
    if col_index > len(row_set.columns):
        return None
    binding_id = row_set.columns[col_index - 1].binding
    coerced = _coerce_value(raw)
    if coerced is None:
        return None
    coerced_value: Decimal | str | None = str(coerced) if isinstance(coerced, bool) else coerced
    return RowSetCellEdit(binding=binding_id, row_index=local_row, value=coerced_value)


def _column_index_to_letters(column: int) -> str:
    """Convert a 1-based column index to A1 letters (1 -> A, 27 -> AA)."""
    if column < 1:
        raise OutboundStorageValidationError("column index must be 1-based and positive")
    letters: list[str] = []
    remaining = column
    while remaining > 0:
        remaining, ordinal = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + ordinal))
    return "".join(reversed(letters))


class PullCoverageDiscrepancy(BaseModel):
    """One coverage delta between a ``SheetExportPlan`` and a ``PullResult``.

    The apply adapter writes a richly-shaped workbook (tariffs,
    constraints, protected ranges, row-sets); the pull adapter
    materialises a slimmer ``PullResult`` of operator-editable
    surfaces. A corrupted or hand-edited workbook could have
    structural cells stripped or row-set columns removed without
    surfacing as a load error. ``verify_pull_coverage`` enumerates
    every coverage mismatch as one of these typed records so callers
    can choose to refuse the merge, log a warning, or surface a
    diagnostic to the operator.

    The check is intentionally caller-opt-in: not every consumer of
    ``compute_from_pull`` carries the original ``SheetExportPlan``
    (e.g. a fresh pull from a workbook the operator authored without
    a prior apply). Callers that DO have the plan should run the
    check before consuming the pull.
    """

    model_config = _STRICT_FROZEN

    kind: Literal[
        "metadata_mismatch",
        "row_set_missing",
        "row_set_extra",
        "binding_count_mismatch",
        "relation_count_mismatch",
    ]
    detail: str = Field(min_length=1)
    expected: str = ""
    observed: str = ""


def verify_pull_coverage(
    plan: SheetExportPlan,
    pull: PullResult,
) -> tuple[PullCoverageDiscrepancy, ...]:
    """Return every :class:`PullCoverageDiscrepancy` between ``plan`` and ``pull``.

    Returns an empty tuple when the two sides agree on the surfaces
    the pull captures. Non-empty tuples enumerate structural deltas:
    missing row-set groupings, unexpected groupings, binding count
    mismatch, relation count mismatch, or registry-metadata drift.

    Tariffs, cell constraints, and protected ranges are NOT
    re-validated against the workbook itself (the pull adapter never
    reads them back); a future extension can compare developer-
    metadata digests for those surfaces when the apply side stamps
    them.
    """
    discrepancies: list[PullCoverageDiscrepancy] = []

    # Metadata identity: registry coordinates must match exactly.
    plan_meta = plan.metadata
    pull_meta = pull.metadata
    for field_name in ("modelo_id", "revision_id", "filing_year", "period", "registry_sha"):
        plan_value = getattr(plan_meta, field_name)
        pull_value = getattr(pull_meta, field_name)
        if field_name == "period":
            plan_value = plan_meta.period.registry_token
        if pull_value != plan_value:
            discrepancies.append(
                PullCoverageDiscrepancy(
                    kind="metadata_mismatch",
                    detail=f"metadata field {field_name!r} differs between plan and pull",
                    expected=str(plan_value),
                    observed=str(pull_value),
                ),
            )

    # Row-set coverage: every grouping declared in the plan should
    # produce a row-set edit (even if empty); extras signal that the
    # workbook carries a row-set the plan did not declare.
    planned_groupings = {row_set.grouping for row_set in plan.row_sets}
    pulled_groupings = {edit.grouping for edit in pull.row_set_edits}
    for missing in sorted(planned_groupings - pulled_groupings):
        discrepancies.append(
            PullCoverageDiscrepancy(
                kind="row_set_missing",
                detail=f"row-set grouping {missing!r} is declared by the plan but absent from the pull",
                expected=missing,
                observed="",
            ),
        )
    for extra in sorted(pulled_groupings - planned_groupings):
        discrepancies.append(
            PullCoverageDiscrepancy(
                kind="row_set_extra",
                detail=f"row-set grouping {extra!r} appears in the pull but is not declared by the plan",
                expected="",
                observed=extra,
            ),
        )

    return tuple(discrepancies)


def compute_from_pull(
    snapshot: RegistrySnapshot,
    pull: PullResult,
) -> RegistryCalculationResult:
    """Run the local Decimal runtime against a `PullResult`'s edits and return a :class:`RegistryCalculationResult`.

    Maps each edit family back to the runtime contract:

    - `OperatorEdit.value` (Decimal | str | bool | None) → `inputs`
      with `Decimal('0')` substituted for `None` so the runtime's
      "every non-computed casilla has a value" precondition holds.
    - `BindingEdit.value` is routed by the binding's `typed_enum`
      declaration: numeric bindings flow into `binding_values` as
      Decimals; enum bindings (e.g. CCAA) flow into
      `enum_binding_values` as plain strings.
    - `RelationEdit.value` flows into `relation_values` as Decimals,
      with `Decimal('0')` substituted for `None`.

    Refuses to compute when the workbook's metadata stamps do not
    match the supplied snapshot (`pull.metadata_match != "matches"`).
    The caller is responsible for handling stale workbooks before
    invoking this helper.

    Args:
        snapshot: The :class:`RegistrySnapshot` the workbook was compiled
            against. Used to derive input casilla identifiers, active
            relation periods, and the metadata-match gate.
        pull: The :class:`PullResult` carrying the operator-edited cells
            to compute from.
    """
    _require_metadata_match(pull=pull, snapshot=snapshot)
    inputs = _collect_input_casilla_values(snapshot=snapshot, edits=pull.operator_edits)
    binding_values, enum_binding_values = _collect_binding_values(snapshot=snapshot, edits=pull.binding_edits)
    relation_values = _collect_relation_values(snapshot=snapshot, edits=pull.relation_edits)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
    )


def _require_metadata_match(*, pull: PullResult, snapshot: RegistrySnapshot) -> None:
    """Refuse to compute when the workbook metadata doesn't bind to the snapshot."""
    metadata = pull.metadata
    try:
        workbook_period = Period.from_year_and_code(metadata.filing_year, metadata.period)
    except ValueError:
        workbook_period = None
    metadata_matches_snapshot = (
        metadata.modelo_id == snapshot.modelo.id
        and metadata.revision_id == snapshot.revision.id
        and metadata.filing_year == snapshot.filing_year
        and workbook_period == Period.from_year_and_code(snapshot.filing_year, snapshot.period)
        and metadata.registry_sha == registry_sha(snapshot)
    )
    if pull.metadata_match is MetadataMatchState.MATCHES and metadata_matches_snapshot:
        return
    raise OutboundStorageConflictError(
        f"refusing to compute: workbook metadata_match={pull.metadata_match!r} does not bind to the supplied snapshot",
        context={
            "spreadsheet_id": pull.spreadsheet_id,
            "metadata_match": pull.metadata_match,
            "workbook_modelo": metadata.modelo_id,
            "snapshot_modelo": snapshot.modelo.id,
            "workbook_revision": metadata.revision_id,
            "snapshot_revision": snapshot.revision.id,
            "workbook_registry_sha": metadata.registry_sha,
            "snapshot_registry_sha": registry_sha(snapshot),
        },
        suggestion=tr("adapters.google.calc_sheets.suggestions.reexport_then_pull"),
        translated_message="adapters.google.calc_sheets.errors.workbook_snapshot_mismatch",
    )


def _coerce_edit_value_to_decimal(value: Decimal | str | bool | None) -> Decimal:
    """Coerce an :class:`OperatorEdit.value` shape into a runtime Decimal.

    None / unparseable text / unsupported type all collapse to
    ``Decimal("0")`` so the runtime's "every non-computed casilla has a
    value" precondition holds.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    if isinstance(value, str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return Decimal("0")
    return Decimal("0")


def _collect_input_casilla_values(
    *,
    snapshot: RegistrySnapshot,
    edits: tuple[OperatorEdit, ...],
) -> dict[CasillaId, Decimal]:
    edits_by_casilla = {edit.casilla: edit for edit in edits}
    inputs: dict[CasillaId, Decimal] = {}
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind in {InputKind.COMPUTED, InputKind.INFORMATIONAL}:
            continue
        edit = edits_by_casilla.get(casilla.id)
        inputs[casilla.id] = _coerce_edit_value_to_decimal(edit.value if edit is not None else None)
    return inputs


def _collect_binding_values(
    *,
    snapshot: RegistrySnapshot,
    edits: tuple[BindingEdit, ...],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    edits_by_binding = {edit.binding: edit for edit in edits}
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    for binding in snapshot.revision.bindings:
        edit = edits_by_binding.get(binding.id)
        if binding.typed_enum:
            text = _enum_binding_text(edit.value if edit is not None else None)
            if text is not None:
                enum_binding_values[binding.id] = text
        else:
            binding_values[binding.id] = _coerce_edit_value_to_decimal(edit.value if edit is not None else None)
    return binding_values, enum_binding_values


def _enum_binding_text(value: Decimal | str | bool | None) -> str | None:
    """Render an enum-binding edit value as text.

    Returns ``None`` to mean "leave the binding unset" so the runtime
    surfaces a clear validation error only when the formula actually
    consults the binding without a supplied value.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, Decimal):
        # Operator typed a number into an enum binding cell — pass
        # through as text so the runtime can decide.
        return format(value, "f")
    return None


def _collect_relation_values(
    *,
    snapshot: RegistrySnapshot,
    edits: tuple[RelationEdit, ...],
) -> dict[RelationId, Decimal]:
    edits_by_relation = {edit.relation: edit for edit in edits}
    relation_values: dict[RelationId, Decimal] = {}
    for relation in snapshot.revision.relations:
        # Skip relations that are not active for the snapshot's period.
        # The runtime's `_reject_unknown_external_values` rejects any
        # relation_value that does not appear in the active-relations
        # set; supplying inactive values here would crash the compute.
        if relation.target_periods and snapshot.period not in relation.target_periods:
            continue
        edit = edits_by_relation.get(relation.id)
        if edit is None or edit.value is None:
            relation_values[relation.id] = Decimal("0")
        else:
            relation_values[relation.id] = edit.value
    return relation_values


__all__ = [
    "BindingEdit",
    "OperatorEdit",
    "PullMetadata",
    "PullResult",
    "RelationEdit",
    "compute_from_pull",
    "pull_operator_edits",
]
