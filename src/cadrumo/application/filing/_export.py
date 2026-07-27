"""Typed records for the local declaration export / verify lifecycle.

The CLI exposes two primitives the application layer must back end-to-end:

- modelo export writes an
  AEAT declaration file from a validated registry snapshot for an approved
  :class:`domain.filing.ModeloDraft` and reports the byte-level
  summary the operator needs to track the artefact (output path, draft
  identity, content hash, format).
- modelo export verification re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

The records are structured return values for renderers, persistence, and
JSON round trips. Runtime export requires registry-backed
:class:`domain.calculations.registry.ExportLayoutDefinition` records,
and verification parses payloads through
:func:`domain.calculations.registry.parse_export_payload`.

The records intentionally do not embed the AEAT submission lifecycle
(:mod:`domain.submission`) — local export and live submit are
separate concerns and live submit is permanently forbidden.

This module is the draft-level renderer. The work-unit export service in
:mod:`application.modelo._export` rebuilds an approved
:class:`domain.filing.ModeloDraft` from a
:class:`domain.modelos.CalculationRevision`, then delegates here to write
and verify the fichero-BOE bytes.

See Also:
    :func:`application.modelo._export.export_modelo_revision`
        Higher-level work-unit export service that replays a calculation
        revision before calling this draft renderer.
    :mod:`adapters.outbound.aeat.export`
        Outbound export-format adapter errors and fixed-width helper
        namespace.
    :class:`core.access_gate.LiveSubmitForbiddenError`
        Core refusal raised for every attempted live AEAT write.
    :mod:`domain.submission`
        Local-only submitted-state lifecycle, separate from file export.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import (
    Period,
    ResultDisposition,
    result_disposition_is_refund,
)
from ...core.decimal import coerce_decimal
from ...core.hashing import sha256_file, sha256_hex
from ...core.logging import get_logger
from ...core.money import round_to_cents
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CalculationCompletenessManifest,
    CasillaFieldKind,
    CasillaId,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    RegistryValidationError,
    parse_export_payload,
    xml_dictionary_entries,
)
from ...domain.filing import (
    CasillaCollection,
    FilingExportError,
    FilingExportValidationError,
    ModeloCasillaProvenance,
    ModeloDraft,
)
from ...domain.submission import ModeloDraftStatus
from ._export_xml_dictionary import render_xml_dictionary_layout
from .runtime import CasillaRecordMetadata, RegistrySchemaAccessor, build_runtime_schema_provider

_logger = get_logger(__name__)

_SHA256_HEX_LENGTH = 64
"""Length of a hex-encoded SHA-256 digest used by export receipts."""


@dataclass(frozen=True)
class _RecordRenderRow:
    row_index: int | None
    active_binding_ids: frozenset[BindingId]


class DeclaracionExportFormat(StrEnum):
    """Closed catalogue of AEAT export formats.

    Attributes:
        FICHERO_BOE: Fixed-width "importar datos" payload defined by
            the AEAT *Diseño de registros* per modelo and validated
            through the registry.
    """

    FICHERO_BOE = "fichero-boe"
    XML_DICTIONARY = "xml-dictionary"


class DeclaracionVerifyVerdict(StrEnum):
    """Closed verdict the verify command surfaces to the operator.

    Attributes:
        MATCH: Every parser-covered casilla in the file equals the
            approved draft's casilla value. Check
            :attr:`DeclaracionVerifyResult.unchecked_casilla_ids` for
            draft casillas that the registry parser cannot re-read from
            the wire layout.
        DRIFT: At least one casilla diverges between the file and the
            approved draft. The CLI renders the per-casilla diff.
        MISSING: The file is unreadable, malformed, or does not cover
            the casillas the draft declares. No diff is computed.
    """

    MATCH = "match"
    DRIFT = "drift"
    MISSING = "missing"


class DeclaracionExportResult(BaseModel):
    """Receipt produced by exporting an approved draft to disk.

    The record is the structured-data return value of the
    modelo export command. It carries enough metadata
    for the operator to identify the artefact later, for the verify
    command to anchor its comparison, and for the audit log to record
    the export event without re-reading the file.

    Attributes:
        draft_id: The :class:`domain.filing.ModeloDraft` identity
            the export was generated from.
        modelo: AEAT modelo identifier.
        period: Typed filing period for the exported draft.
        format: The on-disk wire format (closed
            :class:`DeclaracionExportFormat`).
        output_path: Absolute path the file was written to.
        byte_size: Size of the written content in bytes; matches
            ``output_path.stat().st_size`` at write time.
        file_sha256: Hex-encoded SHA-256 digest of the written bytes.
            Used by :class:`DeclaracionVerifyResult` to anchor the
            file-vs-draft comparison.
        exported_at: UTC timestamp of when the file was written.
        narrative: Translation key for operator-facing summary.
        casilla_provenance: Regulatory grounding for the draft casillas
            represented by the selected registry export layout.

    See Also:
        :class:`DeclaracionVerifyResult`
            Verification record that re-reads the exported bytes and
            anchors the comparison by ``file_sha256``.
        :class:`domain.calculations.registry.ExportLayoutDefinition`
            Registry layout used to render the fixed-width payload.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    output_path: Path
    byte_size: int = Field(ge=0)
    file_sha256: str = Field(min_length=_SHA256_HEX_LENGTH, max_length=_SHA256_HEX_LENGTH)
    exported_at: datetime
    narrative: str
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        """Reject anything that is not a lowercase hex SHA-256 digest."""
        try:
            int(value, 16)
        except ValueError as exc:
            raise FilingExportValidationError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise FilingExportValidationError("file_sha256 must be lowercase hex")
        return value


class DeclaracionVerifyResult(BaseModel):
    """Verdict produced by verifying an exported file against an approved draft.

    The verify command re-reads the file the export command wrote and
    compares its casilla payload against the approved
    :class:`domain.filing.ModeloDraft`. The verdict is the typed
    return value the CLI renders.

    Attributes:
        draft_id: The :class:`domain.filing.ModeloDraft` identity
            the file was compared against.
        file_path: Absolute path of the file that was verified.
        verdict: Closed :class:`DeclaracionVerifyVerdict`.
        mismatched_casilla_ids: Tuple of casilla identifiers whose value
            in the file differs from the approved draft. Empty when
            ``verdict is MATCH``; populated when ``verdict is DRIFT``;
            always empty when ``verdict is MISSING`` (the diff cannot
            be computed).
        unchecked_casilla_ids: Tuple of draft casilla identifiers that do
            not round-trip through the export parser because the wire
            schema exposes them as reserved constants or derived fields
            rather than deserialised currency casillas.
        file_sha256: Hex SHA-256 of the bytes the verifier read.
            Lets the audit trail prove the same file the export
            command wrote was the one verified, even if
            ``output_path`` was renamed in between.
        verified_at: UTC timestamp of when the verdict was produced.
        narrative: Translation key for operator-facing summary.
        casilla_provenance: Regulatory grounding for the draft
            casillas covered by the export parser/layout.
        mismatched_casilla_provenance: Regulatory grounding for the
            subset of ``mismatched_casilla_ids``.

    See Also:
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used to compute parser-covered casillas.
        :class:`DeclaracionVerifyVerdict`
            Closed verdict enum rendered by the CLI.
        :class:`DeclaracionExportResult`
            Export receipt whose digest anchors later verification.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    file_path: Path
    verdict: DeclaracionVerifyVerdict
    mismatched_casilla_ids: tuple[CasillaId, ...] = ()
    unchecked_casilla_ids: tuple[CasillaId, ...] = ()
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    mismatched_casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    file_sha256: str | None = Field(default=None)
    verified_at: datetime
    narrative: str

    @field_validator("mismatched_casilla_ids", "unchecked_casilla_ids")
    @classmethod
    def _validate_casilla_ids(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        """Reject blank casilla identifiers; the CLI renders them verbatim."""
        for entry in value:
            if not entry or entry != entry.strip():
                raise FilingExportValidationError(
                    "casilla-id entries must be non-blank, untrimmed identifiers",
                )
        return value

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str | None) -> str | None:
        """Match :class:`DeclaracionExportResult` digest hygiene when present."""
        if value is None:
            return None
        if len(value) != _SHA256_HEX_LENGTH:
            raise FilingExportValidationError(f"file_sha256 must be {_SHA256_HEX_LENGTH} hex characters when provided")
        try:
            int(value, 16)
        except ValueError as exc:
            raise FilingExportValidationError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise FilingExportValidationError("file_sha256 must be lowercase hex")
        return value


def export_draft(
    draft: ModeloDraft,
    *,
    output_path: Path,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionExportResult:
    """Write an approved draft to a local fichero-BOE file and return a receipt.

    The function selects the active registry
    :class:`~domain.calculations.registry.ExportLayoutDefinition`,
    renders its fixed-width records, writes only ``output_path``, and
    never contacts AEAT. Live submission is outside this surface and is
    refused by :class:`core.access_gate.LiveSubmitForbiddenError`.

    Args:
        draft: The :class:`ModeloDraft` to export; must be in ``APROBADO`` status.
        output_path: Destination path for the fichero-BOE bytes.
        headers: Registry header fields (NIF, ejercicio, etc.) embedded in the file.
        schema_provider: Optional registry schema provider override.

    Returns:
        A :class:`DeclaracionExportResult` with the output path, digest,
        byte size, and casilla provenance for the exported declaration.

    See Also:
        :func:`verify_export`
            Re-read a local export file and compare parser-covered casillas
            against the approved draft.
        :func:`application.modelo._export.export_modelo_revision`
            Work-unit-facing export orchestration that supplies an approved
            draft reconstructed from a calculation revision.
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used by the verification path.
    """
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    if draft.schema_version != subview.schema_version:
        raise FilingExportError("declaration export requires a draft built from the active registry snapshot")
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise FilingExportError("declaration export requires an approved draft")
    if not subview.export_layout_ids:
        raise FilingExportError(_missing_export_layout_message(draft.modelo))
    layout = subview.export_layouts[0]
    _raise_if_export_layout_not_renderable(draft.modelo, layout)
    payload = _render_export_layout(layout, draft=draft, headers=headers, schema_provider=provider)
    if not payload:
        raise FilingExportError(f"modelo {draft.modelo!r} export layout {layout.id!r} rendered an empty payload")
    casilla_provenance = _exported_casilla_provenance(layout, draft=draft, schema_provider=provider)
    if subview.completeness_manifest is not None:
        assert_export_mirrors_manifest(
            layout,
            draft=draft,
            headers=headers,
            schema_provider=provider,
            manifest=subview.completeness_manifest,
            casilla_metadata=subview.casilla_record_metadata,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    digest = sha256_hex(payload)
    return DeclaracionExportResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=_declaracion_export_format(layout),
        output_path=output_path,
        byte_size=len(payload),
        file_sha256=digest,
        exported_at=now(),
        narrative="filing.export.written",
        casilla_provenance=casilla_provenance,
    )


def export_layout_renderability_reason(
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> str | None:
    """Return why ``layout`` cannot currently produce local declaration bytes."""
    if layout is None:
        return "the registry snapshot has no complete export_layouts definition"
    if layout.format == "xml_dictionary":
        if layout.dictionary_source_ref is None:
            return f"XML dictionary export layout {layout.id!r} declares no dictionary source"
        return None
    if layout.format != "fixed_width":
        return f"export layout {layout.id!r} uses unsupported format {layout.format!r}"
    if not layout.records:
        return f"export layout {layout.id!r} declares no export records"
    return None


def _raise_if_export_layout_not_renderable(modelo: str, layout: ExportLayoutDefinition) -> None:
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is not None:
        raise FilingExportError(_export_layout_not_renderable_message(modelo, reason))


def _missing_export_layout_message(modelo: str) -> str:
    reason = export_layout_renderability_reason(modelo, None)
    assert reason is not None
    return _export_layout_not_renderable_message(modelo, reason)


def _export_layout_not_renderable_message(modelo: str, reason: str) -> str:
    return (
        f"modelo {modelo!r} local declaration export is unsupported: {reason}. "
        "Calculation, verification, and local filing surfaces may exist for this modelo, "
        "but this command cannot produce an AEAT-compatible export file and does not certify legal correctness."
    )


def verify_export(
    draft: ModeloDraft,
    *,
    file_path: Path,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionVerifyResult:
    """Verify a local export file against an approved :class:`ModeloDraft`.

    The verifier parses the file through the draft's active registry
    export layout and compares parser-covered casillas against the
    draft. ``MATCH`` means the covered casillas agree; it does not imply
    every draft casilla was present on the wire. Draft casillas outside
    parser coverage are reported in
    :attr:`DeclaracionVerifyResult.unchecked_casilla_ids`.

    Returns:
        A :class:`DeclaracionVerifyResult` with a closed
        :class:`DeclaracionVerifyVerdict`, file digest when available,
        mismatched casillas, unchecked casillas, and provenance.

    See Also:
        :func:`export_draft`
            Write the local fichero-BOE artefact being verified.
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used to read the file.
    """
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    if draft.schema_version != subview.schema_version:
        raise FilingExportError("declaration verify requires a draft built from the active registry snapshot")
    if not subview.export_layout_ids:
        digest = sha256_file(file_path) if file_path.exists() else None
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            file_sha256=digest,
            verified_at=now(),
            narrative="filing.export.missing_registry_layout",
        )
    if not file_path.exists():
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            verified_at=now(),
            narrative="filing.export.missing_file",
        )
    payload = file_path.read_bytes()
    digest = sha256_hex(payload)
    try:
        mismatched, checked = _mismatched_casilla_ids(
            subview.export_layouts[0],
            draft=draft,
            payload=payload,
            schema_provider=provider,
        )
    except RegistryValidationError:
        _logger.warning("declaration export verification could not parse %s", file_path, exc_info=True)
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            file_sha256=digest,
            verified_at=now(),
            narrative="filing.export.malformed_file",
        )
    # Draft casillas the export parser never re-read: the wire layout
    # carries them as RESERVED literals or derived fields, so they round-
    # trip outside the deserialised-currency set. Surface them as
    # ``unchecked_casilla_ids`` so the verdict is honest about its coverage —
    # a MATCH does not mean every draft casilla was confirmed on disk.
    checked_set = set(checked)
    unchecked = tuple(sorted(value.casilla_id for value in draft.values if value.casilla_id not in checked_set))
    return DeclaracionVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=DeclaracionVerifyVerdict.MATCH if not mismatched else DeclaracionVerifyVerdict.DRIFT,
        mismatched_casilla_ids=mismatched,
        unchecked_casilla_ids=unchecked,
        casilla_provenance=_provenance_for_casillas(draft, checked),
        mismatched_casilla_provenance=_provenance_for_casillas(draft, mismatched),
        file_sha256=digest,
        verified_at=now(),
        narrative="filing.export.verified",
    )


#: ``record_type`` of the cuenta-devolución (DID) page in the DR303 export
#: layout. The DID page carries the refund-account block (IBAN / SWIFT-BIC /
#: bank block) AEAT pays into and is emitted ONLY for a refund disposition — a
#: non-refund filing has no refund account to declare, so emitting the page
#: would write an empty 823-byte record the Diseño intends only for a refund.
_DID_PAGE_RECORD_TYPE = "page_did"


def _did_page_suppressed(record: ExportRecordDefinition, *, headers: dict[str, str]) -> bool:
    """Return whether a DID (cuenta-devolución) page record must be suppressed.

    The DID page is emitted only when the determined disposition (carried on the
    ``declaration_type`` header) is a refund (``D`` / ``V`` / ``X``). A
    non-refund filing suppresses the page rather than emitting an empty refund
    block. Non-DID records are never suppressed by this guard.
    """
    if record.record_type != _DID_PAGE_RECORD_TYPE:
        return False
    declaration_type = headers.get("declaration_type", "")
    try:
        disposition = ResultDisposition(declaration_type)
    except ValueError:
        return True
    return not result_disposition_is_refund(disposition)


def _declaracion_export_format(layout: ExportLayoutDefinition) -> DeclaracionExportFormat:
    if layout.format == "xml_dictionary":
        return DeclaracionExportFormat.XML_DICTIONARY
    return DeclaracionExportFormat.FICHERO_BOE


def _render_export_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> bytes:
    if layout.format == "xml_dictionary":
        return render_xml_dictionary_layout(layout, draft=draft, headers=headers, schema_provider=schema_provider)
    return _render_layout(layout, draft=draft, headers=headers)


def _render_layout(layout: ExportLayoutDefinition, *, draft: ModeloDraft, headers: dict[str, str]) -> bytes:
    chunks: list[bytes] = []
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    binding_values: dict[tuple[BindingId, int | None], object] = {
        (value.binding_id, value.row_index): value.value for value in draft.binding_values
    }
    for record in sorted(layout.records, key=lambda item: item.order):
        if _did_page_suppressed(record, headers=normalized_headers):
            continue
        for row in _record_render_rows(record, binding_values):
            _guard_record_export(record, casilla_values=casilla_values)
            text = _render_record(
                record,
                draft=draft,
                headers=normalized_headers,
                casilla_values=casilla_values,
                binding_values=binding_values,
                row=row,
            )
            if record.line_ending == "crlf":
                text += "\r\n"
            elif record.line_ending == "lf":
                text += "\n"
            chunks.append(text.encode(record.encoding))
    return b"".join(chunks)


render_layout = _render_layout


def _record_render_rows(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> tuple[_RecordRenderRow, ...]:
    if record.repeat != "binding_rows":
        if record.binding_record is not None and not _record_has_binding_value(record, binding_values):
            return ()
        return (_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),)
    binding_fields = _record_binding_fields(record)
    row_indexes = sorted(
        {
            row_index
            for binding_id, row_index in binding_values
            if row_index is not None
            and any(field.binding == binding_id for field in binding_fields)
            and _is_active_binding_value(binding_values[(binding_id, row_index)])
        },
    )
    rows: list[_RecordRenderRow] = []
    for row_index in row_indexes:
        active_fields = tuple(
            field
            for field in binding_fields
            if field.binding is not None and _is_active_binding_value(binding_values.get((field.binding, row_index)))
        )
        for group in _compatible_binding_field_groups(active_fields):
            rows.append(
                _RecordRenderRow(
                    row_index=row_index,
                    active_binding_ids=frozenset(field.binding for field in group if field.binding is not None),
                ),
            )
    return tuple(rows)


def _record_binding_fields(record: ExportRecordDefinition) -> tuple[ExportFieldDefinition, ...]:
    return tuple(
        field for field in record.fields if field.kind == CasillaFieldKind.BINDING and field.binding is not None
    )


def _is_active_binding_value(value: object) -> bool:
    return value is not None and value != ""


def _compatible_binding_field_groups(
    fields: tuple[ExportFieldDefinition, ...],
) -> tuple[tuple[ExportFieldDefinition, ...], ...]:
    groups: list[list[ExportFieldDefinition]] = []
    for field in sorted(fields, key=lambda item: (item.offset or 0, str(item.id))):
        for group in groups:
            if not any(_export_fields_overlap(field, existing) for existing in group):
                group.append(field)
                break
        else:
            groups.append([field])
    return tuple(tuple(group) for group in groups)


def _export_fields_overlap(left: ExportFieldDefinition, right: ExportFieldDefinition) -> bool:
    if left.offset is None or left.length is None or right.offset is None or right.length is None:
        return False
    left_end = left.offset + left.length - 1
    right_end = right.offset + right.length - 1
    return left.offset <= right_end and right.offset <= left_end


def _record_has_binding_value(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> bool:
    binding_ids = {field.binding for field in _record_binding_fields(record)}
    return any(
        binding_id in binding_ids and value not in {None, ""} for (binding_id, _), value in binding_values.items()
    )


def _guard_record_export(record: ExportRecordDefinition, *, casilla_values: dict[CasillaId, object]) -> None:
    if record.requires_positive_casilla_id is None:
        return
    raw = casilla_values.get(record.requires_positive_casilla_id)
    amount = coerce_decimal(raw, default=Decimal("0")) or Decimal("0")
    if amount <= 0:
        raise FilingExportValidationError(
            f"export record {record.id!r} requires positive casilla {record.requires_positive_casilla_id!r}",
        )


def _render_record(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: _RecordRenderRow,
) -> str:
    positioned = all(field.offset is not None for field in record.fields)
    if not positioned:
        return "".join(
            _render_field(
                field,
                draft=draft,
                headers=headers,
                casilla_values=casilla_values,
                binding_values=binding_values,
                row_index=row.row_index,
            )
            for field in record.fields
            if _field_is_active_for_row(field, row)
        )
    length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
    buffer = [" "] * length
    for field in sorted(record.fields, key=lambda item: item.offset or 0):
        if not _field_is_active_for_row(field, row):
            continue
        if field.offset is None:
            raise FilingExportValidationError(f"export field {field.id!r} must declare offset")
        rendered = _render_field(
            field,
            draft=draft,
            headers=headers,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row_index=row.row_index,
        )
        start = field.offset - 1
        end = start + len(rendered)
        if any(char != " " for char in buffer[start:end]):
            raise FilingExportError(f"export field {field.id!r} overlaps another field")
        buffer[start:end] = rendered
    return "".join(buffer)


def _field_is_active_for_row(field: ExportFieldDefinition, row: _RecordRenderRow) -> bool:
    if not row.active_binding_ids:
        return True
    if field.kind != CasillaFieldKind.BINDING:
        return True
    return field.binding in row.active_binding_ids


def _render_field(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> str:
    if field.length is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare length")
    raw = _field_value(
        field,
        draft=draft,
        headers=headers,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row_index=row_index,
    )
    return _format_field(field, raw)


def _field_value(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object:
    match field.kind:
        case CasillaFieldKind.LITERAL:
            return field.literal
        case CasillaFieldKind.FILLER:
            return ""
        case CasillaFieldKind.CASILLA:
            return _casilla_field_value(field, casilla_values)
        case CasillaFieldKind.BINDING:
            return _binding_field_value(field, binding_values, row_index)
        case CasillaFieldKind.HEADER:
            return _header_field_value(field, headers)
        case CasillaFieldKind.DRAFT:
            return _draft_value(field, draft)
        case CasillaFieldKind.COMPUTED:
            return _computed_field_value(field, draft)
        case _:
            raise FilingExportError(f"unsupported export field kind {field.kind!r}")


def _casilla_field_value(field: ExportFieldDefinition, casilla_values: dict[CasillaId, object]) -> object:
    if field.casilla_id is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare casilla_id")
    return casilla_values.get(field.casilla_id)


def _binding_field_value(
    field: ExportFieldDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object:
    if field.binding is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare binding")
    return binding_values.get((field.binding, row_index))


def _header_field_value(field: ExportFieldDefinition, headers: dict[str, str]) -> str:
    if field.header_key is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare header_key")
    value = headers.get(field.header_key.lower())
    if field.required and (value is None or not value.strip()) and not _required_header_allows_blank(field, headers):
        raise FilingExportValidationError(f"export header {field.header_key!r} is required")
    return value.strip() if value else ""


_M202_LEGAL_ENTITY_BLANK_NAME_FIELD_IDS: frozenset[str] = frozenset(
    {
        "modelo-202-2019-2022-page-01-header-name-pos-83",
        "modelo-202-2023-2024-page-01-header-name-pos-83",
        "modelo-202-page-01-header-name-pos-83",
    },
)


def _required_header_allows_blank(field: ExportFieldDefinition, headers: dict[str, str]) -> bool:
    """Allow only Modelo 202's individual-name slot to blank for legal entities."""
    return (
        str(field.id) in _M202_LEGAL_ENTITY_BLANK_NAME_FIELD_IDS
        and field.header_key == "name"
        and (headers.get("entity_type") or "").strip() == "legal_entity"
        and bool((headers.get("surnames") or "").strip())
    )


def _computed_field_value(field: ExportFieldDefinition, draft: ModeloDraft) -> str:
    if field.computed_key == "envelope_closing_tag":
        year = str(draft.period.filing_year)
        period_code = draft.period.registry_token
        return f"</T{draft.modelo}0{year}{period_code}0000>"
    raise FilingExportError(f"unsupported export computed field {field.computed_key!r}")


def _draft_value(field: ExportFieldDefinition, draft: ModeloDraft) -> str:
    if field.draft_attribute == "modelo":
        return draft.modelo
    if field.draft_attribute == "period":
        return draft.period.registry_token
    if field.draft_attribute == "profile_tax_id":
        return draft.profile_tax_id
    if field.draft_attribute == "filing_year":
        return str(draft.period.filing_year)
    if field.draft_attribute == "period_code":
        return draft.period.registry_token
    raise FilingExportError(f"unsupported draft export attribute {field.draft_attribute!r}")


def _format_field(field: ExportFieldDefinition, value: object) -> str:
    if field.length is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare length")
    if field.kind == CasillaFieldKind.FILLER:
        return " " * field.length
    if field.data_type == "money":
        rendered = _format_money(value, length=field.length, signed=field.signed)
    elif field.data_type == "integer":
        rendered = _format_integer(value, length=field.length)
    elif field.data_type == "boolean":
        rendered = "X" if value is True else ""
    else:
        rendered = "" if value is None else str(value)
    if len(rendered) > field.length:
        raise FilingExportValidationError(f"export field {field.id!r} value exceeds length {field.length}")
    return _pad(rendered, field)


def _format_money(value: object, *, length: int, signed: bool) -> str:
    if isinstance(value, bool):
        raise FilingExportValidationError("money export fields cannot render boolean values")
    amount = coerce_decimal(value, default=Decimal("0")) or Decimal("0")
    cents = int((round_to_cents(abs(amount)) * 100).to_integral_value())
    if amount < 0:
        if not signed:
            raise FilingExportValidationError("unsigned money export field cannot render a negative value")
        return "N" + str(cents).zfill(length - 1)
    if signed:
        return " " + str(cents).zfill(length - 1)
    return str(cents).zfill(length)


def _format_integer(value: object, *, length: int) -> str:
    if value is None or value == "":
        return "0".zfill(length)
    if isinstance(value, bool):
        raise FilingExportValidationError("integer export fields cannot render boolean values")
    coerced = coerce_decimal(value)
    if coerced is None:
        raise FilingExportValidationError(f"integer export field cannot coerce {value!r} to Decimal")
    return str(int(coerced)).zfill(length)


def _pad(value: str, field: ExportFieldDefinition) -> str:
    if field.length is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare length")
    if field.padding == "left_zero":
        return value.rjust(field.length, "0")
    if field.padding == "left_space":
        return value.rjust(field.length, " ")
    if field.padding == "right_space":
        return value.ljust(field.length, " ")
    return value


def _mismatched_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]]:
    values = {value.casilla_id: value.value for value in draft.values}
    mismatched: list[CasillaId] = []
    checked: list[CasillaId] = []
    for parsed in parse_export_payload(
        layout,
        payload,
        source_root=schema_provider.source_root,
        sources=schema_provider.sources,
    ).casillas:
        if parsed.casilla_id is None:
            continue
        checked.append(parsed.casilla_id)
        expected = values.get(parsed.casilla_id) or Decimal("0")
        if isinstance(parsed.value, Decimal):
            expected_decimal = coerce_decimal(expected, default=Decimal("0")) or Decimal("0")
            if round_to_cents(expected_decimal) != round_to_cents(parsed.value):
                mismatched.append(parsed.casilla_id)
        elif str(expected) != str(parsed.value):
            mismatched.append(parsed.casilla_id)
    return tuple(dict.fromkeys(mismatched)), tuple(dict.fromkeys(checked))


def _provenance_for_casillas(
    draft: ModeloDraft,
    casilla_ids: Iterable[CasillaId],
) -> tuple[ModeloCasillaProvenance, ...]:
    provenance_by_id = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    return tuple(
        provenance_by_id[casilla_id] for casilla_id in dict.fromkeys(casilla_ids) if casilla_id in provenance_by_id
    )


def _exported_casilla_provenance(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[ModeloCasillaProvenance, ...]:
    if layout.format == "xml_dictionary":
        entries = xml_dictionary_entries(
            layout,
            source_root=schema_provider.source_root,
            sources=schema_provider.sources,
        )
        draft_casillas = {value.casilla_id for value in draft.values}
        return _provenance_for_casillas(
            draft,
            (
                entry.casilla_id
                for entry in entries
                if entry.casilla_id is not None and entry.casilla_id in draft_casillas
            ),
        )
    draft_casillas = {value.casilla_id for value in draft.values}
    layout_casillas = (
        field.casilla_id
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id is not None
        and field.casilla_id in draft_casillas
    )
    return _provenance_for_casillas(draft, layout_casillas)


def boe_representable_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> frozenset[CasillaId]:
    """Return the casillas the ``.boe`` layout files a slot for, for this disposition.

    A casilla is *representable* when the official record design carries a field
    for it that this draft's disposition does not suppress. ``xml_dictionary``
    layouts derive their casillas from the dictionary entries; ``fixed_width``
    layouts from every ``CASILLA`` field plus the binding-row casilla mappings
    (``row_field_casilla_ids``), across records not suppressed for the disposition
    (e.g. the DID refund page on a non-refund filing).

    The completeness gate intersects the calculation-completeness manifest with
    this set: a manifest casilla absent here is a calculation-closure casilla the
    official filed record does not carry, so it is out of scope for the ``.boe``
    parity gate rather than a drift.
    """
    if layout.format == "xml_dictionary":
        entries = xml_dictionary_entries(
            layout,
            source_root=schema_provider.source_root,
            sources=schema_provider.sources,
        )
        return frozenset(entry.casilla_id for entry in entries if entry.casilla_id is not None)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    representable: set[CasillaId] = set()
    for record in layout.records:
        if _did_page_suppressed(record, headers=normalized_headers):
            continue
        for field in record.fields:
            if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None:
                representable.add(field.casilla_id)
        representable.update(record.row_field_casilla_ids.values())
    return frozenset(representable)


def rendered_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> frozenset[CasillaId]:
    """Return the representable casillas whose value actually reaches disk.

    A representable casilla reaches disk only when the :class:`ModeloDraft`
    carries a value for it; a representable casilla absent from
    ``draft.values`` renders as a blank fixed-width slot (or an omitted xml
    element), which is the structurally-thin file the completeness gate
    exists to refuse. This is the rendered set the gate compares against the
    manifest-required-and-representable set.
    """
    # build_draft emits a ModeloValue for every declared casilla, using
    # value=None (kind=EMPTY) as the "nothing here" marker, so casilla-id
    # membership in draft.values is NOT value presence: an EMPTY casilla would
    # render as a blank slot. Filter to real values (value is None iff EMPTY).
    valued_casillas = {value.casilla_id for value in draft.values if value.value is not None}
    return frozenset(
        boe_representable_casilla_ids(layout, headers=headers, schema_provider=schema_provider) & valued_casillas
    )


def required_applicable_casilla_ids(
    manifest: CalculationCompletenessManifest,
    *,
    collection: CasillaCollection,
    representable: frozenset[CasillaId],
) -> frozenset[CasillaId]:
    """Return the casillas that must carry a value in a complete fichero-BOE export.

    A casilla is *required-applicable* when it declares a formula (a calculation
    RESULT) or is schema-required, AND the official export record files a slot for
    it at this filing's disposition (``representable``).  Optional operator-input
    casillas — retenciones, prior payments, deductions the taxpayer may
    legitimately not have — declare neither a formula nor a ``required`` flag, so
    they are excluded: a blank slot for them is a valid zero, not a
    structurally-thin file.

    This is the single derivation authority shared by the completeness gate
    (:func:`assert_export_mirrors_manifest`) and the parity regression tests.
    Both call this function instead of re-deriving the set locally, so a change
    to the required-set semantics propagates to all consumers in one place.

    Args:
        manifest: Revision's
            :class:`~domain.calculations.registry.CalculationCompletenessManifest`.
        collection: :class:`~domain.filing.CasillaCollection` for the modelo,
            supplying ``formula`` and ``required`` for each declared casilla.
        representable: Casilla IDs the official export record files a slot for
            at this filing's disposition; see :func:`boe_representable_casilla_ids`.

    Returns:
        Frozen set of casilla IDs that must carry a real value before the
        fichero-BOE bytes are written.

    See Also:
        :func:`boe_representable_casilla_ids`
            Derives the ``representable`` argument from the export layout and headers.
        :func:`assert_export_mirrors_manifest`
            Gate that enforces this required set before writing bytes.
    """
    return frozenset(
        casilla.casilla_id
        for casilla in manifest.casillas
        if (schema := collection.get(casilla.casilla_id)) is not None
        and (schema.formula is not None or schema.required)
    ) & representable


def assert_export_mirrors_manifest(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
    manifest: CalculationCompletenessManifest,
    casilla_metadata: tuple[CasillaRecordMetadata, ...],
) -> None:
    """Panic if the ``.boe`` would not mirror the manifest-required structure.

    The completeness gate: every casilla that is a calculation RESULT (declares a
    formula) or is schema-required, and that the calculation-completeness manifest
    lists AND the official record files (``representable`` for this
    :class:`ModeloDraft`'s disposition), MUST carry a value on disk. Such a casilla
    rendered blank means the calculation did not populate it -- a structurally-thin
    file behind a valid SHA-256 digest, which this gate refuses with a hard
    :class:`FilingExportError` naming every missing casilla with its official record
    number and segmento, so the panic is loud and explicit.

    Optional operator-input casillas -- retenciones, prior payments, deductions the
    taxpayer may legitimately not have -- are NOT required to carry a value: a blank
    slot for them is a valid zero, not a thin file (grounded in the AEAT casilla
    semantics; e.g. Modelo 131 casillas 02/08/09/12/14 are optional inputs), so they
    are excluded from the required set. A manifest casilla absent from the
    representable set is a calculation-closure casilla the official record does not
    file and is likewise out of scope. Callers pass ``manifest`` only when the
    revision declares one; a revision without a manifest is handled by the
    coverage-advisory path, not here.

    The gate applies only to the fixed-width fichero-BOE. In that format every
    field occupies its byte slot always, so an omitted required casilla renders a
    blank slot behind a valid digest -- the structurally-thin file. An
    ``xml_dictionary`` export instead omits an absent casilla as an absent
    optional element, which is legitimate (a filer declares only the casillas its
    situation requires), so completeness is not asserted for that transport.

    Beyond casilla presence, the gate asserts two further structural-fidelity
    dimensions before any bytes are written, so the ``.boe`` mirrors the official
    modelo-revision structure and not merely its casilla set:

    - Record/section order: the records that reach disk, emitted in their declared
      ``order``, must follow the registry export-layout declaration order, and no
      two rendered records may share an ``order``
      (:func:`_assert_record_order_fidelity`).
    - Casilla numbering/segmento: every manifest casilla the official record files
      a slot for must carry the same ``(number, segmento)`` the registry
      ``CasillaDefinition`` declares -- re-grounded against the projected
      :class:`~application.filing.runtime.CasillaRecordMetadata`, not the
      manifest's own copy (:func:`_assert_casilla_metadata_fidelity`).

    Each dimension is a hard, enumerated :class:`FilingExportError`; a structural
    divergence is a failure, never a warning.
    """
    if layout.format != "fixed_width":
        return
    _assert_record_order_fidelity(modelo=draft.modelo, layout=layout, headers=headers)
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=schema_provider)
    _assert_casilla_metadata_fidelity(
        modelo=draft.modelo,
        manifest=manifest,
        representable=representable,
        casilla_metadata=casilla_metadata,
    )
    rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=schema_provider)
    # Require a value on disk only for calculation RESULTS (casillas declaring a
    # formula) and schema-required casillas. Optional operator inputs -- retenciones,
    # prior payments, deductions the taxpayer may legitimately not have -- render a
    # blank slot that is a valid zero, not a thin file, so they are excluded from the
    # required set (grounded in the AEAT casilla semantics, e.g. Modelo 131 casillas
    # 02/08/09/12/14).
    collection = schema_provider.get_collection(draft.modelo)
    required_applicable = required_applicable_casilla_ids(
        manifest,
        collection=collection,
        representable=representable,
    )
    missing = sorted(required_applicable - rendered)
    if not missing:
        return
    metadata = {casilla.casilla_id: (casilla.number, casilla.segmento) for casilla in manifest.casillas}
    rendered_missing = "; ".join(_format_missing_casilla(casilla_id, metadata[casilla_id]) for casilla_id in missing)
    raise FilingExportError(
        f"fichero-BOE export for modelo {draft.modelo!r} would omit {len(missing)} required "
        f"casilla(s) the official record files, rendering them as blank slots (structurally-thin "
        f"filing): {rendered_missing}. Every required casilla must be declared in the draft before export.",
    )


def _segmento_phrase(segmento: str | None) -> str:
    """Render a segmento clause for a fidelity-drift enumeration, blank when unset."""
    return "" if segmento is None else f" within segmento {segmento!r}"


def _assert_record_order_fidelity(
    *,
    modelo: str,
    layout: ExportLayoutDefinition,
    headers: dict[str, str],
) -> None:
    """Panic if the rendered record order drifts from the registry declaration order.

    A fixed-width ``.boe`` emits its records sorted by each record's ``order``
    field; the AEAT *Diseño de registros* fixes that page/segment sequence and the
    registry export layout declares the records in that official order
    (``layout.records``). This assertion re-grounds the emitted record sequence
    against that declaration: the records that reach disk (excluding
    disposition-suppressed records such as the DID refund page) must, when emitted
    in ``order``, appear in the same sequence the registry declares, and no two
    rendered records may share an ``order`` (an ambiguous emit sequence). A
    permuted or ambiguous record order is a hard, enumerated
    :class:`FilingExportError` -- the ``.boe`` record/section sequence must mirror
    the official modelo-revision structure.
    """
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    declared = tuple(
        record for record in layout.records if not _did_page_suppressed(record, headers=normalized_headers)
    )
    orders = [record.order for record in declared]
    duplicate_orders = sorted({order for order in orders if orders.count(order) > 1})
    if duplicate_orders:
        rendered = ", ".join(str(order) for order in duplicate_orders)
        raise FilingExportError(
            f"fichero-BOE export for modelo {modelo!r} declares export records that share an emit "
            f"order ({rendered}), so the rendered record sequence is ambiguous "
            f"(structural-fidelity drift). Each rendered record must declare a distinct order so the "
            f"exported record sequence mirrors the official modelo-revision structure.",
        )
    emitted = tuple(sorted(declared, key=lambda record: record.order))
    if [record.id for record in emitted] != [record.id for record in declared]:
        drifts = "; ".join(
            f"position {index}: registry declares record {declared[index].id!r} "
            f"but the .boe would emit {emitted[index].id!r}"
            for index in range(len(declared))
            if declared[index].id != emitted[index].id
        )
        raise FilingExportError(
            f"fichero-BOE export for modelo {modelo!r} would emit its records out of the "
            f"registry-declared record order (structural-fidelity drift): {drifts}. The rendered "
            f"record sequence must follow the official modelo-revision structure.",
        )


def _assert_casilla_metadata_fidelity(
    *,
    modelo: str,
    manifest: CalculationCompletenessManifest,
    representable: frozenset[CasillaId],
    casilla_metadata: tuple[CasillaRecordMetadata, ...],
) -> None:
    """Panic if a representable manifest casilla's number/segmento drifts from the registry.

    The completeness manifest carries its own copy of each casilla's official
    ``(number, segmento)`` -- the metadata this parity gate reports and keys on.
    This assertion re-grounds that copy against the authoritative
    :class:`~application.filing.runtime.CasillaRecordMetadata` projected from
    the registry ``CasillaDefinition`` (the same authority the calculation engine
    consumes), for every manifest casilla the official record files a slot for
    (``representable``). A divergent ``number`` or ``segmento`` -- or a manifest
    casilla the registry no longer declares -- is a hard, enumerated
    :class:`FilingExportError` with the expected registry value versus the value the
    ``.boe`` would file, so the exported casilla numbering and segmento cannot drift
    from the official modelo-revision structure behind a valid digest.
    """
    registry_by_id = {meta.casilla_id: meta for meta in casilla_metadata}
    drifts: list[str] = []
    for manifest_casilla in manifest.casillas:
        casilla_id = manifest_casilla.casilla_id
        if casilla_id not in representable:
            continue
        registry_meta = registry_by_id.get(casilla_id)
        if registry_meta is None:
            drifts.append(
                f"{casilla_id} (manifest declares number {manifest_casilla.number!r}"
                f"{_segmento_phrase(manifest_casilla.segmento)} but the registry does not declare this casilla)",
            )
            continue
        if (manifest_casilla.number, manifest_casilla.segmento) != (registry_meta.number, registry_meta.segmento):
            drifts.append(
                f"{casilla_id} (registry declares number {registry_meta.number!r}"
                f"{_segmento_phrase(registry_meta.segmento)} but the .boe would file it as number "
                f"{manifest_casilla.number!r}{_segmento_phrase(manifest_casilla.segmento)})",
            )
    if not drifts:
        return
    raise FilingExportError(
        f"fichero-BOE export for modelo {modelo!r} would render {len(drifts)} casilla(s) whose "
        f"number/segmento drifts from the registry-declared record-design metadata "
        f"(structural-fidelity drift): {'; '.join(drifts)}. The exported casilla numbering and "
        f"segmento must mirror the official modelo-revision structure.",
    )


def _format_missing_casilla(casilla_id: CasillaId, metadata: tuple[str, str | None]) -> str:
    number, segmento = metadata
    if segmento is not None:
        return f"{casilla_id} (segmento {segmento}, casilla {number})"
    return f"{casilla_id} (casilla {number})"


__all__ = [
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "assert_export_mirrors_manifest",
    "boe_representable_casilla_ids",
    "export_draft",
    "render_layout",
    "rendered_casilla_ids",
    "required_applicable_casilla_ids",
    "verify_export",
]
