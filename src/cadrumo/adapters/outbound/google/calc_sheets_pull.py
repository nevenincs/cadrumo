"""Read operator-edited Sheets cells back into structured records.

Pairs with :mod:`~adapters.outbound.google.calc_sheets_apply`. The export
side materialises a
:class:`~application.storage.calc_sheets.SheetExportPlan` as a real Google
Sheets workbook; this module reads the operator's edits back out, validates the
workbook is still bound to the
:class:`~domain.calculations.registry.RegistrySnapshot` the engine
compiled it from, and returns typed records the caller can inspect, compute
from, or assemble into ledger / filing inputs.

Two safety gates fire before any value is read:

1. **Drive ownership marker** — the spreadsheet must carry the
   ``appProperties.cadrumo_vault_app=cadrumo`` marker. Reading values from a
   spreadsheet that lacks the marker would mix operator content with
   foreign Drive files and break the ``cadrumo-vault/`` isolation contract.
2. **Registry-SHA and layout-engine metadata match** — the spreadsheet's developer
   metadata must declare ``cadrumo_registry_sha = <snapshot.registry_sha>``
   and ``cadrumo_modelo_id`` / ``cadrumo_revision_id`` / ``cadrumo_filing_year`` /
   ``cadrumo_period`` / ``cadrumo_engine_version`` matching the caller's snapshot
   and live layout compiler. A mismatch means the workbook was compiled
   against a different registry slice or coordinate layout — casilla
   identity/layout, formula chains, and bracket tables may have shifted.
   The pull is refused with a typed error before coordinates are read.

The pull adapter does NOT mutate any local state; it returns a
:class:`~adapters.outbound.google.PullResult` and leaves applying the
edits to the caller.

See Also:
    :func:`~adapters.outbound.google.pull_operator_edits` reads the
    workbook,
    :func:`~adapters.outbound.google.compute_from_pull` maps a matching
    pull into
    :class:`~domain.calculations.registry.RegistryCalculationResult`, and
    :func:`~adapters.outbound.google.calc_sheets_pull_coverage.verify_pull_coverage`
    compares a pull against its source
    :class:`~application.storage.calc_sheets.SheetExportPlan` when the
    caller still has that plan.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

# google-api-python-client-stubs ships ``googleapiclient.discovery.Resource``
# as the typed surface for service objects returned by ``build()``.
# We import it under TYPE_CHECKING so the runtime dependency stays optional
# (the ImportError path in ``_drive_service`` / ``_sheets_service`` guards the
# live path) while the type-checker can narrow the ``Any`` service returns.
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource as _GoogleResource

from pydantic import TypeAdapter, ValidationError

from ....application.storage.calc_sheets._engine import CALC_SHEETS_ENGINE_VERSION, collect_row_sets, registry_sha
from ....application.storage.calc_sheets._layout import SheetLayout, plan_layout
from ....application.storage.calc_sheets._records import column_index_to_letters
from ....core.casilla_id import CasillaId
from ....core.decimal.coercion import coerce_decimal, coerce_finite_european_decimal
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.casilla_membership import (
    casillas_by_id,
    undeclared_casilla_ids,
)
from ....domain.calculations.registry.formula_runtime import (
    RegistryCalculationResult,
    calculate_registry_snapshot,
)
from ....domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    ModeloId,
    RelationId,
    SourceRefId,
)
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.period import calculation_filing_date
from ..storage.errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageValidationError,
)
from ._preconditions import google_terminal_refusal
from .api import execute_request
from .calc_sheets_pull_records import (
    BindingEdit as _BindingEdit,
)
from .calc_sheets_pull_records import (
    MetadataMatchState as _MetadataMatchState,
)
from .calc_sheets_pull_records import (
    OperatorEdit as _OperatorEdit,
)
from .calc_sheets_pull_records import (
    PullMetadata as _PullMetadata,
)
from .calc_sheets_pull_records import (
    PullResult as _PullResult,
)
from .calc_sheets_pull_records import (
    RelationEdit as _RelationEdit,
)
from .calc_sheets_pull_records import (
    RowSetCellEdit as _RowSetCellEdit,
)
from .calc_sheets_pull_records import (
    RowSetEdit as _RowSetEdit,
)
from .calc_sheets_pull_records import (
    ValueRange as _ValueRange,
)

_OWNERSHIP_KEY: Final[str] = "cadrumo_vault_app"
_OWNERSHIP_VALUE: Final[str] = "cadrumo"
_RELATION_METADATA_PREFIX: Final[str] = "cadrumo_relation:"
_DUPLICATE_SENSITIVE_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "cadrumo_engine_version",
        "cadrumo_registry_sha",
        "cadrumo_modelo_id",
        "cadrumo_revision_id",
        "cadrumo_filing_year",
        "cadrumo_period",
    },
)
_LEGAL_REFS_ADAPTER = TypeAdapter(tuple[LegalRefId, ...])
_SOURCE_REFS_ADAPTER = TypeAdapter(tuple[SourceRefId, ...])


class CalcSheetsPullPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the calculation-sheet pull adapter."""

    API_CLIENT_AVAILABLE = "google.calc_sheets.pull.api_client_available"
    SPREADSHEET_ID_VALID = "google.calc_sheets.pull.spreadsheet_id_valid"
    OWNERSHIP_METADATA_VALID = "google.calc_sheets.pull.ownership_metadata_valid"
    OWNERSHIP_ALIGNED = "google.calc_sheets.pull.ownership_aligned"
    DEVELOPER_METADATA_LIST_VALID = "google.calc_sheets.pull.developer_metadata_list_valid"
    DEVELOPER_METADATA_ENTRY_VALID = "google.calc_sheets.pull.developer_metadata_entry_valid"
    DEVELOPER_METADATA_CONSISTENT = "google.calc_sheets.pull.developer_metadata_consistent"
    SNAPSHOT_ALIGNED = "google.calc_sheets.pull.snapshot_aligned"
    RELATION_LEGAL_REFS_VALID = "google.calc_sheets.pull.relation_legal_refs_valid"
    RELATION_SOURCE_REFS_VALID = "google.calc_sheets.pull.relation_source_refs_valid"
    EDIT_VALUE_FINITE = "google.calc_sheets.pull.edit_value_finite"
    EDIT_CASILLA_DECLARED = "google.calc_sheets.pull.edit_casilla_declared"
    EDIT_CASILLA_INPUT = "google.calc_sheets.pull.edit_casilla_input"


def _calc_sheets_pull_terminal_refusal(
    error: OutboundStorageError,
    condition: CalcSheetsPullPreconditionCondition,
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


def _drive_service(credentials: object) -> _GoogleResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        error = OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.API_CLIENT_AVAILABLE,
            facts={
                "client_available": False,
                "dependency": "google_api_python_client",
                "service_name": "drive",
                "service_version": "v3",
            },
            outcome=NoRecoveryOutcome.SAFETY,
        ) from exc
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _sheets_service(credentials: object) -> _GoogleResource:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        error = OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            translated_message="adapters.google.calc_sheets.errors.googleapiclient_not_importable",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.API_CLIENT_AVAILABLE,
            facts={
                "client_available": False,
                "dependency": "google_api_python_client",
                "service_name": "sheets",
                "service_version": "v4",
            },
            outcome=NoRecoveryOutcome.SAFETY,
        ) from exc
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .files() / .spreadsheets() only via runtime Discovery JSON dispatch; the published
# typing surface carries .close() alone, so service helpers accept Any for the dynamic
# attribute access.
# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: runtime discovery Resource.
def _verify_ownership(drive_service: Any, spreadsheet_id: str) -> None:
    """Refuse to read from a spreadsheet that lacks the ownership marker."""
    file_meta = execute_request(
        drive_service.files().get(
            fileId=spreadsheet_id,
            fields="id,name,appProperties",
        ),
        action="drive.files.get.appProperties",
    )
    raw_app_properties = file_meta.get("appProperties")
    if raw_app_properties is not None and not isinstance(raw_app_properties, Mapping):
        error = OutboundStorageValidationError(
            "spreadsheet appProperties must be a mapping when present",
            context={"spreadsheet_id": spreadsheet_id, "app_properties_type": type(raw_app_properties).__name__},
            translated_message="adapters.google.calc_sheets.errors.ownership_metadata_invalid",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.OWNERSHIP_METADATA_VALID,
            facts={"spreadsheet_id": spreadsheet_id, "ownership_metadata_mapping": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    app_properties = raw_app_properties or {}
    if app_properties.get(_OWNERSHIP_KEY) != _OWNERSHIP_VALUE:
        error = OutboundStorageConflictError(
            f"spreadsheet {spreadsheet_id!r} is not marked as app-owned; refusing "
            f"to read operator edits from a foreign Drive file",
            context={"spreadsheet_id": spreadsheet_id, "name": file_meta.get("name", "")},
            translated_message="adapters.google.calc_sheets.errors.foreign_spreadsheet_not_owned",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.OWNERSHIP_ALIGNED,
            facts={"spreadsheet_id": spreadsheet_id, "ownership_aligned": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the published typing
# surface carries .close() alone, so the service helper accepts Any for the dynamic
# attribute access.
# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: runtime discovery Resource.
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
    raw_entries = spreadsheet.get("developerMetadata")
    if raw_entries is None:
        return _merge_developer_metadata_entries(())
    if not isinstance(raw_entries, list):
        error = OutboundStorageValidationError(
            "spreadsheet developerMetadata must be a list when present",
            context={"spreadsheet_id": spreadsheet_id, "developer_metadata_type": type(raw_entries).__name__},
            translated_message="adapters.google.calc_sheets.errors.developer_metadata_invalid",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.DEVELOPER_METADATA_LIST_VALID,
            facts={"spreadsheet_id": spreadsheet_id, "developer_metadata_list_valid": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    return _merge_developer_metadata_entries(raw_entries)


def _duplicate_metadata_must_match(key: str) -> bool:
    return key in _DUPLICATE_SENSITIVE_METADATA_KEYS or key.startswith(_RELATION_METADATA_PREFIX)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-SHEETS-API-PAYLOAD: entries are Sheets
# developer-metadata records returned as free-shape JSON by the discovery client.
def _merge_developer_metadata_entries(entries: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Merge Sheets developer metadata entries, refusing conflicting identity duplicates.

    Google Sheets developer metadata keys are not unique. Repeated exports
    can leave multiple `cadrumo_*` keys on the same workbook. Duplicate
    identity keys with different values would make pull classification
    depend on API return order, so they are treated as a conflict. The
    informational `cadrumo_exported_at` stamp is intentionally excluded:
    multiple exports of the same registry slice produce different
    timestamps without changing workbook identity.
    """
    pairs: dict[str, str] = {}
    conflicting_keys: set[str] = set()
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            error = OutboundStorageValidationError(
                "spreadsheet developer metadata entry must be a mapping",
                context={"metadata_entry_index": entry_index, "entry_type": type(entry).__name__},
                translated_message="adapters.google.calc_sheets.errors.developer_metadata_invalid",
            )
            raise _calc_sheets_pull_terminal_refusal(
                error,
                CalcSheetsPullPreconditionCondition.DEVELOPER_METADATA_ENTRY_VALID,
                facts={"metadata_entry_index": entry_index, "metadata_entry_mapping": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            )
        key = entry.get("metadataKey")
        value = entry.get("metadataValue")
        if isinstance(key, str) and isinstance(value, str):
            previous = pairs.get(key)
            if previous is not None and previous != value and _duplicate_metadata_must_match(key):
                conflicting_keys.add(key)
            pairs[key] = value
    if conflicting_keys:
        error = OutboundStorageConflictError(
            "spreadsheet carries conflicting duplicate Cadrumo developer metadata; refusing order-dependent pull",
            context={"conflicting_metadata_keys": sorted(conflicting_keys)},
            translated_message="adapters.google.calc_sheets.errors.conflicting_duplicate_metadata",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.DEVELOPER_METADATA_CONSISTENT,
            facts={"conflicting_metadata_key_count": len(conflicting_keys), "metadata_consistent": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    return pairs


def _classify_metadata_match(
    pairs: Mapping[str, str],
    snapshot: RegistrySnapshot,
) -> tuple[_MetadataMatchState, _PullMetadata]:
    if not pairs:
        # The MISSING verdict carries a placeholder PullMetadata so the
        # caller can still receive a typed record alongside the verdict.
        # Sentinel values satisfy PullMetadata's min_length=1 boundary
        # constraint without claiming real registry coordinates.
        return _MetadataMatchState.MISSING, _PullMetadata(
            modelo_id="missing",
            revision_id="missing",
            filing_year=0,
            period="missing",
            engine_version="missing",
            registry_sha="missing",
        )
    try:
        filing_year = int(pairs.get("cadrumo_filing_year", "0"))
    except ValueError:
        filing_year = 0
    metadata = _PullMetadata(
        modelo_id=pairs.get("cadrumo_modelo_id", ""),
        revision_id=pairs.get("cadrumo_revision_id", ""),
        filing_year=filing_year,
        period=pairs.get("cadrumo_period", ""),
        engine_version=pairs.get("cadrumo_engine_version", ""),
        registry_sha=pairs.get("cadrumo_registry_sha", ""),
        exported_at=pairs.get("cadrumo_exported_at"),
    )
    # The registry-SHA and layout-engine gates ensure a workbook compiled
    # against a different registry slice or compiler is never matched. Such
    # a workbook may have different casilla or tariff coordinates even where
    # modelo, revision, year, and period all align.
    matches = (
        metadata.modelo_id == snapshot.modelo.id
        and metadata.revision_id == snapshot.revision.id
        and metadata.filing_year == snapshot.filing_year
        and metadata.period == Period.from_year_and_code(snapshot.filing_year, snapshot.period).registry_token
        and metadata.engine_version == CALC_SHEETS_ENGINE_VERSION
        and metadata.registry_sha == registry_sha(snapshot)
    )
    return (_MetadataMatchState.MATCHES if matches else _MetadataMatchState.STALE), metadata


def _require_matching_metadata(
    *,
    spreadsheet_id: str,
    metadata_match: _MetadataMatchState,
    metadata: _PullMetadata,
    snapshot: RegistrySnapshot,
) -> None:
    """Refuse a workbook that cannot bind to the live snapshot and layout.

    The pull entrypoint invokes this immediately after developer-metadata
    readback, before ``plan_layout`` derives an A1 coordinate. Reusing the
    guard from ``compute_from_pull`` blocks a fabricated matching verdict from
    bypassing the layout-version contract.
    """
    try:
        workbook_period = Period.from_year_and_code(metadata.filing_year, metadata.period)
    except ValueError:
        workbook_period = None
    metadata_binds_snapshot = (
        metadata.modelo_id == snapshot.modelo.id
        and metadata.revision_id == snapshot.revision.id
        and metadata.filing_year == snapshot.filing_year
        and workbook_period == Period.from_year_and_code(snapshot.filing_year, snapshot.period)
        and metadata.engine_version == CALC_SHEETS_ENGINE_VERSION
        and metadata.registry_sha == registry_sha(snapshot)
    )
    if metadata_match is _MetadataMatchState.MATCHES and metadata_binds_snapshot:
        return
    error = OutboundStorageConflictError(
        "refusing to read: "
        f"workbook metadata_match={metadata_match!r} does not bind to the supplied snapshot and layout",
        context={
            "spreadsheet_id": spreadsheet_id,
            "metadata_match": metadata_match,
            "workbook_modelo": metadata.modelo_id,
            "snapshot_modelo": snapshot.modelo.id,
            "workbook_revision": metadata.revision_id,
            "snapshot_revision": snapshot.revision.id,
            "workbook_engine_version": metadata.engine_version,
            "expected_engine_version": CALC_SHEETS_ENGINE_VERSION,
            "workbook_registry_sha": metadata.registry_sha,
            "snapshot_registry_sha": registry_sha(snapshot),
        },
        translated_message="adapters.google.calc_sheets.errors.workbook_snapshot_mismatch",
    )
    raise _calc_sheets_pull_terminal_refusal(
        error,
        CalcSheetsPullPreconditionCondition.SNAPSHOT_ALIGNED,
        facts={
            "spreadsheet_id": spreadsheet_id,
            "metadata_match": metadata_match.value,
            "snapshot_aligned": False,
        },
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no precise static type is available in google-api-python-client.
def _coerce_value(raw: Any) -> Decimal | str | bool | None:
    """Type one raw worksheet cell, keeping an unreadable amount as its own text.

    Both ``values.batchGet`` calls in this module pin
    ``valueRenderOption="UNFORMATTED_VALUE"``, so Sheets returns a numeric cell
    as an int or float and only a cell the operator forced to plain text arrives
    as a string. That string is the operator's own writing, which is why it goes
    to the extraction contract rather than to
    :func:`~core.decimal.coerce_decimal`: the tolerant coercer resolves the
    ambiguous Spanish ``1.000`` to one euro, while
    :func:`~core.decimal.coerce_finite_european_decimal` yields no value for it
    and the cell stays a string for the caller to refuse — the same judgement
    ``_coerce_edit_value_to_decimal`` already applies to a spreadsheet edit
    further down this module, over the same workbook.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return coerce_decimal(raw)
    if isinstance(raw, str):
        as_decimal = coerce_finite_european_decimal(raw)
        if as_decimal is not None:
            return as_decimal
        return raw
    return None


def pull_operator_edits(
    snapshot: RegistrySnapshot,
    *,
    spreadsheet_id: str,
    credentials: object,
) -> _PullResult:
    """Read operator-edited cells back from a workbook into typed records.

    This is the readback entrypoint behind ``aeat config google sync calc
    pull``. It verifies the Drive ownership marker, reads developer metadata,
    classifies metadata against ``snapshot``, reads operator/binding/relation
    cells plus Detalle row-set blocks, and returns a
    :class:`~adapters.outbound.google.PullResult`.

    Args:
        snapshot: The
            :class:`~domain.calculations.registry.RegistrySnapshot` the
            workbook was compiled against. Used to derive the layout (cell
            addresses for every casilla / binding / relation) and to validate
            the workbook's developer-metadata stamps.
        spreadsheet_id: The Drive file id of the workbook to read.
            Must already exist and carry the
            ``appProperties.cadrumo_vault_app=cadrumo`` ownership marker.
        credentials: A ``google.oauth2.credentials.Credentials``-shaped
            object carrying a refresh + access token with at least
            the ``drive.file`` + ``spreadsheets`` scopes.

    Returns:
        A :class:`~adapters.outbound.google.PullResult` carrying the
        operator edits, binding edits, relation edits, and the metadata-match
        verdict. A non-matching stamp is refused before the live layout is
        derived, so no operator cells are read under coordinates that may have
        shifted since export.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`:
            When ``spreadsheet_id`` is blank.
        :exc:`~adapters.outbound.storage.OutboundStorageError`: When
            Drive or Sheets rejects the request, the target is missing, quota
            is exhausted, or the workbook fails the app-owned marker gate.
    """
    if not spreadsheet_id.strip():
        error = OutboundStorageValidationError(
            "spreadsheet_id must not be blank",
            context={"spreadsheet_id": spreadsheet_id},
            translated_message="adapters.google.calc_sheets.errors.spreadsheet_id_blank",
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.SPREADSHEET_ID_VALID,
            facts={"spreadsheet_id_present": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )

    drive = _drive_service(credentials)
    sheets = _sheets_service(credentials)

    _verify_ownership(drive, spreadsheet_id)
    metadata_pairs = _read_developer_metadata(sheets, spreadsheet_id)
    metadata_match, metadata = _classify_metadata_match(metadata_pairs, snapshot)
    _require_matching_metadata(
        spreadsheet_id=spreadsheet_id,
        metadata_match=metadata_match,
        metadata=metadata,
        snapshot=snapshot,
    )

    filing_anchor = (
        calculation_filing_date(snapshot.filing_period)
        if snapshot.filing_period is not None
        else date(snapshot.filing_year, 12, 31)
    )
    layout = plan_layout(snapshot.revision, bracket_filter_date=filing_anchor)

    operator_input_ids, operator_input_ranges = _operator_input_addresses(snapshot, layout)
    binding_ids = list(layout.binding_cells)
    binding_ranges = [layout.binding_cells[bid].qualified() for bid in binding_ids]
    relation_ids = list(layout.relation_cells)
    relation_ranges = [layout.relation_cells[rid].qualified() for rid in relation_ids]
    all_ranges = operator_input_ranges + binding_ranges + relation_ranges
    value_ranges = _batch_get_values(sheets, spreadsheet_id, all_ranges)

    casilla_by_id = casillas_by_id(snapshot.revision)
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

    return _PullResult(
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
# .spreadsheets() only via runtime Discovery JSON dispatch; the published typing
# surface carries .close() alone, so the service helper accepts Any for the dynamic
# attribute access.
# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: runtime discovery Resource.
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
) -> tuple[tuple[_OperatorEdit, ...], int, int]:
    """Map the per-casilla slice of the batchGet response into typed OperatorEdits."""
    cells_read = 0
    edits: list[_OperatorEdit] = []
    for casilla_id in operator_input_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = _coerce_value(raw)
        if coerced is not None:
            cells_read += 1
        casilla = casilla_by_id[casilla_id]
        edits.append(
            _OperatorEdit(
                casilla_id=casilla_id,
                display_number=casilla.number,
                label=casilla.label,
                value=coerced,
            ),
        )
    return tuple(edits), cursor, cells_read


def _decode_binding_edits(
    value_ranges: list[_ValueRange],
    cursor: int,
    binding_ids: list[BindingId],
) -> tuple[tuple[_BindingEdit, ...], int, int]:
    """Map the per-binding slice of the batchGet response into typed BindingEdits.

    Booleans are stringified because
    :attr:`~adapters.outbound.google.calc_sheets_pull_records.BindingEdit.value`
    (``Decimal | str | None``) does not carry a bool path — the runtime
    enum-binding semantics expect a textual representation here.
    """
    cells_read = 0
    edits: list[_BindingEdit] = []
    for binding_id in binding_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = _coerce_value(raw)
        if coerced is not None:
            cells_read += 1
        binding_value: Decimal | str | None = str(coerced) if isinstance(coerced, bool) else coerced
        edits.append(_BindingEdit(binding=binding_id, value=binding_value))
    return tuple(edits), cursor, cells_read


def _decode_relation_edits(
    value_ranges: list[_ValueRange],
    cursor: int,
    relation_ids: list[RelationId],
    metadata_pairs: Mapping[str, str],
) -> tuple[tuple[_RelationEdit, ...], int, int]:
    """Map the per-relation slice of the batchGet response into typed RelationEdits.

    Per-relation provenance metadata is recovered from the workbook's
    developer metadata via the ``cadrumo_relation:<relation>`` key written
    by the apply adapter. Recovering it on pull preserves the audit
    trail (provenance tier, source filing year, source periods,
    resolved-at instant) that would otherwise be silently dropped on
    every round trip.
    """
    cells_read = 0
    edits: list[_RelationEdit] = []
    for relation_id in relation_ids:
        raw = _raw_cell_value(value_ranges, cursor)
        cursor += 1
        coerced = coerce_decimal(raw)
        if coerced is not None:
            cells_read += 1
        (
            provenance,
            source_modelo,
            source_filing_year,
            source_periods,
            source_casilla_ids,
            legal_refs,
            source_refs,
            resolved_at,
        ) = _parse_relation_metadata(
            metadata_pairs.get(f"cadrumo_relation:{relation_id}", ""),
        )
        edits.append(
            _RelationEdit(
                relation=relation_id,
                value=coerced,
                provenance=provenance,
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                source_casilla_ids=source_casilla_ids,
                legal_refs=legal_refs,
                source_refs=source_refs,
                resolved_at=resolved_at,
            ),
        )
    return tuple(edits), cursor, cells_read


def _parse_relation_metadata(
    raw: str,
) -> tuple[
    Literal["local_filing", "aeat_live", "operator_manual"] | None,
    ModeloId | None,
    int | None,
    tuple[str, ...],
    tuple[CasillaId, ...],
    tuple[LegalRefId, ...],
    tuple[SourceRefId, ...],
    datetime | None,
]:
    """Parse the ``"k=v; k=v"`` shape written by the apply adapter."""
    if not raw:
        return None, None, None, (), (), (), (), None
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
    source_modelo: ModeloId | None = fields.get("source_modelo") or None
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
    source_casilla_ids: tuple[CasillaId, ...] = ()
    raw_casilla_ids = fields.get("source_casilla_ids", "")
    if raw_casilla_ids:
        source_casilla_ids = tuple(piece for piece in raw_casilla_ids.split("+") if piece)
    legal_refs: tuple[LegalRefId, ...] = ()
    raw_legal_refs = fields.get("legal_refs", "")
    if raw_legal_refs:
        legal_refs = _validated_relation_legal_refs(raw_legal_refs)
    source_refs: tuple[SourceRefId, ...] = ()
    raw_source_refs = fields.get("source_refs", "")
    if raw_source_refs:
        source_refs = _validated_relation_source_refs(raw_source_refs)
    resolved_at: datetime | None = None
    raw_resolved = fields.get("resolved_at", "")
    if raw_resolved:
        try:
            resolved_at = datetime.fromisoformat(raw_resolved)
        except ValueError:
            resolved_at = None
    return (
        provenance,
        source_modelo,
        source_filing_year,
        source_periods,
        source_casilla_ids,
        legal_refs,
        source_refs,
        resolved_at,
    )


def _relation_ref_tokens(raw: str) -> tuple[str, ...]:
    return tuple(piece for piece in raw.split("+") if piece)


def _validated_relation_legal_refs(raw: str) -> tuple[LegalRefId, ...]:
    try:
        return _LEGAL_REFS_ADAPTER.validate_python(_relation_ref_tokens(raw))
    except ValidationError as exc:
        error = OutboundStorageValidationError(
            "relation metadata legal_refs contains malformed registry legal reference ids",
            context={"metadata_key": "legal_refs", "metadata_value": raw},
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.RELATION_LEGAL_REFS_VALID,
            facts={"legal_refs_valid": False, "metadata_key": "legal_refs", "metadata_value": raw},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc


def _validated_relation_source_refs(raw: str) -> tuple[SourceRefId, ...]:
    try:
        return _SOURCE_REFS_ADAPTER.validate_python(_relation_ref_tokens(raw))
    except ValidationError as exc:
        error = OutboundStorageValidationError(
            "relation metadata source_refs contains malformed registry source reference ids",
            context={"metadata_key": "source_refs", "metadata_value": raw},
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.RELATION_SOURCE_REFS_VALID,
            facts={"metadata_key": "source_refs", "metadata_value": raw, "source_refs_valid": False},
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the published typing
# surface carries .close() alone, so the service helper accepts Any for the dynamic
# attribute access.
# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: runtime discovery Resource.
def _read_row_set_edits(
    snapshot: RegistrySnapshot,
    sheets: Any,
    spreadsheet_id: str,
) -> tuple[tuple[_RowSetEdit, ...], int]:
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
    edits: list[_RowSetEdit] = []
    cells_read = 0
    for row_set_index, row_set in enumerate(row_sets):
        vr = value_ranges[row_set_index] if row_set_index < len(value_ranges) else {}
        rows = vr.get("values", []) or []
        cells, cells_in_block = _decode_row_set_block(rows, row_set)
        cells_read += cells_in_block
        edits.append(_RowSetEdit(grouping=row_set.grouping, cells=cells))
    return tuple(edits), cells_read


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource
# object; no precise static type is available in google-api-python-client.
def _row_set_block_range(row_set: Any) -> str:
    """Build the A1 range covering the 50-row data block of one row-set."""
    last_column = max(col.header_address.column for col in row_set.columns)
    start_col_letters = column_index_to_letters(1)
    end_col_letters = column_index_to_letters(last_column)
    start_row = row_set.first_data_row
    end_row = row_set.first_data_row + 49
    return f"'{row_set.tab.value}'!{start_col_letters}{start_row}:{end_col_letters}{end_row}"


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: googleapiclient Resource exposes
# .spreadsheets() only via runtime Discovery JSON dispatch; the published typing
# surface carries .close() alone, so the service helper accepts Any for the dynamic
# attribute access.
# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: runtime discovery Resource.
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
# object; no precise static type is available in google-api-python-client.
def _decode_row_set_block(
    rows: list[list[object]],
    row_set: Any,
) -> tuple[tuple[_RowSetCellEdit, ...], int]:
    """Decode one row-set's block of (local_row, col_index) cells into typed edits.

    Returns the typed-cell tuple plus the non-blank-cells count for
    this block. Cells whose column index exceeds the row-set's declared
    columns are skipped — that's the Sheets-side defensive path when an
    operator pastes data past the allocated column count.
    """
    cells: list[_RowSetCellEdit] = []
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
# object; no precise static type is available in google-api-python-client.
def _decode_row_set_cell(
    raw: object,
    col_index: int,
    local_row: int,
    row_set: Any,
) -> _RowSetCellEdit | None:
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
    return _RowSetCellEdit(binding=binding_id, row_index=local_row, value=coerced_value)


def compute_from_pull(
    snapshot: RegistrySnapshot,
    pull: _PullResult,
) -> RegistryCalculationResult:
    """Run the local Decimal runtime against a :class:`~adapters.outbound.google.PullResult`.

    Maps each edit family back to the runtime contract:

    - :attr:`~adapters.outbound.google.calc_sheets_pull_records.OperatorEdit.value`
      flows into runtime ``inputs``, with ``Decimal("0")`` substituted for
      ``None`` so the runtime's "every non-computed casilla has a value"
      precondition holds.
    - :attr:`~adapters.outbound.google.calc_sheets_pull_records.BindingEdit.value`
      is routed by the binding's ``typed_enum`` declaration: numeric bindings
      flow into ``binding_values`` as Decimals; enum bindings flow into
      ``enum_binding_values`` as plain strings.
    - :attr:`~adapters.outbound.google.calc_sheets_pull_records.RelationEdit.value`
      flows into ``relation_values`` as Decimals, with ``Decimal("0")``
      substituted for ``None``.

    Refuses to compute when the workbook's metadata stamps do not
    match the supplied snapshot (``pull.metadata_match != "matches"``).
    The caller is responsible for handling stale workbooks before
    invoking this helper.

    Args:
        snapshot: The
            :class:`~domain.calculations.registry.RegistrySnapshot` the
            workbook was compiled against. Used to derive input casilla
            identifiers, active relation periods, and the metadata-match gate.
        pull: The :class:`~adapters.outbound.google.PullResult` carrying
            the operator-edited cells to compute from.

    Returns:
        A :class:`~domain.calculations.registry.RegistryCalculationResult`
        produced by
        :func:`~domain.calculations.registry.calculate_registry_snapshot`.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageConflictError`:
            When ``pull`` does not bind to ``snapshot`` by metadata verdict and
            registry-SHA stamp.
    """
    _require_metadata_match(pull=pull, snapshot=snapshot)
    inputs = _collect_input_casilla_values(snapshot=snapshot, edits=pull.operator_edits)
    binding_values, enum_binding_values = _collect_binding_values(snapshot=snapshot, edits=pull.binding_edits)
    relation_values = _collect_relation_values(snapshot=snapshot, edits=pull.relation_edits)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={
            "filing_period": (
                calculation_filing_date(snapshot.filing_period)
                if snapshot.filing_period is not None
                else date(snapshot.filing_year, 12, 31)
            ),
        },
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        # The worksheet pull carries operator cell edits, not filing-instance
    )


def _require_metadata_match(*, pull: _PullResult, snapshot: RegistrySnapshot) -> None:
    """Refuse to compute when the workbook metadata doesn't bind to the snapshot."""
    _require_matching_metadata(
        spreadsheet_id=pull.spreadsheet_id,
        metadata_match=pull.metadata_match,
        metadata=pull.metadata,
        snapshot=snapshot,
    )


def _coerce_edit_value_to_decimal(value: Decimal | str | bool | None, *, input_key: str) -> Decimal:
    """Coerce an :attr:`~adapters.outbound.google.calc_sheets_pull_records.OperatorEdit.value` shape.

    An absent cell stays zero so the runtime can evaluate the complete input
    lattice. Any supplied malformed or non-finite numeric value is refused;
    it must never become an operator-looking zero.
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal) and value.is_finite():
        return value
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    parsed = coerce_finite_european_decimal(value)
    if parsed is not None:
        return parsed
    error = OutboundStorageValidationError(
        f"numeric spreadsheet edit {input_key!r} must be a finite decimal",
        context={"input_key": input_key, "value": str(value)},
    )
    raise _calc_sheets_pull_terminal_refusal(
        error,
        CalcSheetsPullPreconditionCondition.EDIT_VALUE_FINITE,
        facts={"edit_value": str(value), "finite_decimal": False, "input_key": input_key},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _collect_input_casilla_values(
    *,
    snapshot: RegistrySnapshot,
    edits: tuple[_OperatorEdit, ...],
) -> dict[CasillaId, Decimal]:
    edits_by_casilla = {edit.casilla_id: edit for edit in edits}
    input_ids = frozenset(
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.input_kind not in {InputKind.COMPUTED, InputKind.INFORMATIONAL}
    )
    undeclared_edits = undeclared_casilla_ids(snapshot.revision, edits_by_casilla)
    non_input_edits = tuple(sorted(set(edits_by_casilla) - set(undeclared_edits) - input_ids))
    if undeclared_edits:
        error = OutboundStorageValidationError(
            "operator edits must reference canonical input casilla.id values declared by the workbook snapshot",
            context={
                "modelo_id": snapshot.modelo.id,
                "revision_id": snapshot.revision.id,
                "casilla_ids": ",".join((*undeclared_edits, *non_input_edits)),
                "undeclared_casilla_ids": ",".join(undeclared_edits),
                "non_input_casilla_ids": ",".join(non_input_edits),
            },
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.EDIT_CASILLA_DECLARED,
            facts={
                "modelo_id": snapshot.modelo.id,
                "revision_id": snapshot.revision.id,
                "undeclared_casilla_count": len(undeclared_edits),
                "workbook_edits_declared": False,
            },
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    if non_input_edits:
        error = OutboundStorageValidationError(
            "operator edits must reference canonical input casilla.id values declared by the workbook snapshot",
            context={
                "modelo_id": snapshot.modelo.id,
                "revision_id": snapshot.revision.id,
                "casilla_ids": ",".join(non_input_edits),
                "undeclared_casilla_ids": "",
                "non_input_casilla_ids": ",".join(non_input_edits),
            },
        )
        raise _calc_sheets_pull_terminal_refusal(
            error,
            CalcSheetsPullPreconditionCondition.EDIT_CASILLA_INPUT,
            facts={
                "modelo_id": snapshot.modelo.id,
                "non_input_casilla_count": len(non_input_edits),
                "revision_id": snapshot.revision.id,
                "workbook_edits_input": False,
            },
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    inputs: dict[CasillaId, Decimal] = {}
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind in {InputKind.COMPUTED, InputKind.INFORMATIONAL}:
            continue
        edit = edits_by_casilla.get(casilla.id)
        inputs[casilla.id] = _coerce_edit_value_to_decimal(
            edit.value if edit is not None else None,
            input_key=casilla.id,
        )
    return inputs


def _collect_binding_values(
    *,
    snapshot: RegistrySnapshot,
    edits: tuple[_BindingEdit, ...],
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
            binding_values[binding.id] = _coerce_edit_value_to_decimal(
                edit.value if edit is not None else None,
                input_key=binding.id,
            )
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
    edits: tuple[_RelationEdit, ...],
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


__all__ = ["compute_from_pull", "pull_operator_edits"]
