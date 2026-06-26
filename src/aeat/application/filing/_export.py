"""Typed records for the declaration export / verify lifecycle.

The CLI exposes two primitives the application layer must back end-to-end:

- modelo export writes an
  AEAT declaration file from a validated registry snapshot for an approved
  :class:`aeat.domain.filing.ModeloDraft` and reports the byte-level
  summary the operator needs to track the artefact (output path, draft
  identity, content hash, format).
- modelo export verification re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

The records are structured return values for renderers, persistence, and
JSON round trips. Runtime export requires registry-backed schemas.

The records intentionally do not embed the AEAT submission lifecycle
(:mod:`aeat.domain.submission`) — local export and live submit are
separate concerns and live submit is permanently forbidden.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period, ResultDisposition, result_disposition_is_refund
from ...core.decimal import coerce_decimal
from ...core.hashing import sha256_file, sha256_hex
from ...core.logging import get_logger
from ...core.money import round_to_cents
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CasillaFieldKind,
    CasillaId,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    RegistryValidationError,
    parse_export_payload,
)
from ...domain.filing import (
    FilingExportError,
    FilingExportValidationError,
    ModeloCasillaProvenance,
    ModeloDraft,
)
from ...domain.submission._protocols import ModeloDraftStatus
from .runtime import RegistrySchemaAccessor, build_runtime_schema_provider

_logger = get_logger(__name__)

_SHA256_HEX_LENGTH = 64
"""Length of a hex-encoded SHA-256 digest used by export receipts."""


class DeclaracionExportFormat(StrEnum):
    """Closed catalogue of AEAT export formats.

    Attributes:
        FICHERO_BOE: Fixed-width "importar datos" payload defined by
            the AEAT *Diseño de registros* per modelo and validated
            through the registry.
    """

    FICHERO_BOE = "fichero-boe"


class DeclaracionVerifyVerdict(StrEnum):
    """Closed verdict the verify command surfaces to the operator.

    Attributes:
        MATCH: Every casilla in the file equals the approved draft's
            casilla value. The exported artefact is still in sync.
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
        draft_id: The :class:`aeat.domain.filing.ModeloDraft` identity
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
    :class:`aeat.domain.filing.ModeloDraft`. The verdict is the typed
    return value the CLI renders.

    Attributes:
        draft_id: The :class:`aeat.domain.filing.ModeloDraft` identity
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
    """Write an approved draft to a fichero-BOE file and return a receipt.

    Args:
        draft: The :class:`ModeloDraft` to export; must be in ``APROBADO`` status.
        output_path: Destination path for the fichero-BOE bytes.
        headers: Registry header fields (NIF, ejercicio, etc.) embedded in the file.
        schema_provider: Optional registry schema provider override.

    Returns a :class:`DeclaracionExportResult` with the output path and
    casilla provenance for the exported declaration.
    """
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    if draft.schema_version != subview.schema_version:
        raise FilingExportError("declaration export requires a draft built from the active registry snapshot")
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise FilingExportError("declaration export requires an approved draft")
    if not subview.export_layout_ids:
        raise FilingExportError(f"modelo {draft.modelo!r} registry snapshot declares no export layout")
    payload = _render_layout(subview.export_layouts[0], draft=draft, headers=headers)
    casilla_provenance = _exported_casilla_provenance(subview.export_layouts[0], draft=draft)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    digest = sha256_hex(payload)
    return DeclaracionExportResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=DeclaracionExportFormat.FICHERO_BOE,
        output_path=output_path,
        byte_size=len(payload),
        file_sha256=digest,
        exported_at=now(),
        narrative="filing.export.written",
        casilla_provenance=casilla_provenance,
    )


def verify_export(
    draft: ModeloDraft,
    *,
    file_path: Path,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionVerifyResult:
    """Verify an exported file against an approved :class:`ModeloDraft`.

    Returns a :class:`DeclaracionVerifyResult`.
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
        mismatched, checked = _mismatched_casilla_ids(subview.export_layouts[0], draft=draft, payload=payload)
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


_MONEY_QUANT = Decimal("0.01")


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
        for row_index in _record_row_indexes(record, binding_values):
            _guard_record_export(record, casilla_values=casilla_values)
            text = _render_record(
                record,
                draft=draft,
                headers=normalized_headers,
                casilla_values=casilla_values,
                binding_values=binding_values,
                row_index=row_index,
            )
            if record.line_ending == "crlf":
                text += "\r\n"
            elif record.line_ending == "lf":
                text += "\n"
            chunks.append(text.encode(record.encoding))
    return b"".join(chunks)


def _record_row_indexes(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> tuple[int | None, ...]:
    if record.repeat != "binding_rows":
        if record.binding_record is not None and not _record_has_binding_value(record, binding_values):
            return ()
        return (None,)
    binding_ids = {
        field.binding for field in record.fields if field.kind == CasillaFieldKind.BINDING and field.binding is not None
    }
    row_indexes = sorted(
        row_index for binding_id, row_index in binding_values if binding_id in binding_ids and row_index is not None
    )
    return tuple(dict.fromkeys(row_indexes))


def _record_has_binding_value(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> bool:
    binding_ids = {
        field.binding for field in record.fields if field.kind == CasillaFieldKind.BINDING and field.binding is not None
    }
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
    row_index: int | None,
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
                row_index=row_index,
            )
            for field in record.fields
        )
    length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
    buffer = [" "] * length
    for field in sorted(record.fields, key=lambda item: item.offset or 0):
        if field.offset is None:
            raise FilingExportValidationError(f"export field {field.id!r} must declare offset")
        rendered = _render_field(
            field,
            draft=draft,
            headers=headers,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row_index=row_index,
        )
        start = field.offset - 1
        end = start + len(rendered)
        if any(char != " " for char in buffer[start:end]):
            raise FilingExportError(f"export field {field.id!r} overlaps another field")
        buffer[start:end] = rendered
    return "".join(buffer)


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
    if field.required and (value is None or value == ""):
        raise FilingExportValidationError(f"export header {field.header_key!r} is required")
    return value or ""


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
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]]:
    values = {value.casilla_id: value.value for value in draft.values}
    mismatched: list[CasillaId] = []
    checked: list[CasillaId] = []
    for parsed in parse_export_payload(layout, payload).casillas:
        if parsed.casilla_id is None:
            continue
        checked.append(parsed.casilla_id)
        expected = values.get(parsed.casilla_id) or Decimal("0")
        if isinstance(parsed.value, Decimal):
            expected_decimal = coerce_decimal(expected, default=Decimal("0")) or Decimal("0")
            if expected_decimal.quantize(_MONEY_QUANT) != parsed.value.quantize(_MONEY_QUANT):
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
) -> tuple[ModeloCasillaProvenance, ...]:
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


__all__ = [
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "export_draft",
    "verify_export",
]
