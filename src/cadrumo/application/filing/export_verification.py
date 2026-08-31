"""Canonical declaration-export receipts and read-back verification."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, NonNegativeInt, field_validator

from ...core.casilla_id import CasillaId
from ...core.export_layout_format import ExportLayoutFormat
from ...core.hashing import hash_file, sha256_file, sha256_hex
from ...core.identity import ContentDigest
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export_parse import parse_export_payload, xml_dictionary_entries
from ...domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.filing.errors import FilingExportError, FilingExportValidationError
from ...domain.filing.schema import ModeloCasillaProvenance, ModeloDraft
from ._export_xml_dictionary import expected_xml_dictionary_root_identity, read_xml_dictionary_root_identity
from .runtime import RegistryModeloSubview, RegistrySchemaAccessor, build_runtime_schema_provider

_logger = get_logger(__name__)
_SHA256_HEX_LENGTH = 64


class DeclaracionExportFormat(StrEnum):
    """Closed catalogue of local declaration-export formats."""

    FICHERO_BOE = "fichero-boe"
    XML_DICTIONARY = "xml-dictionary"


class DeclaracionVerifyVerdict(StrEnum):
    """Closed verdict the verifier surfaces to the operator."""

    MATCH = "match"
    DRIFT = "drift"
    MISSING = "missing"


class DeclaracionExportResult(BaseModel):
    """Receipt produced by exporting an approved draft to disk."""

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    output_path: Path
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    exported_at: datetime
    narrative: str
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise FilingExportValidationError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise FilingExportValidationError("file_sha256 must be lowercase hex")
        return value


class FilingExportConsumedResult(BaseModel):
    """Internal receipt for a validated payload delivered without plaintext disk."""

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    byte_size: int = Field(gt=0)
    file_sha256: ContentDigest
    exported_at: datetime
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        if any(character not in "0123456789abcdef" for character in value):
            raise FilingExportValidationError("file_sha256 must be lowercase hexadecimal")
        return value


class FilingExportValidatedPayload(BaseModel):
    """Secret-bearing in-memory payload delivered only after validation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    payload: bytes = Field(min_length=1)
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)


class FilingExportPayloadConsumer(Protocol):
    """Destination port for validated bytes that must not touch plaintext disk."""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        """Consume the payload synchronously before its in-memory owner returns."""


class DeclaracionVerifyResult(BaseModel):
    """Verdict produced by verifying an exported file against an approved draft."""

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str = Field(min_length=1, max_length=128)
    file_path: Path
    verdict: DeclaracionVerifyVerdict
    mismatched_casilla_ids: tuple[CasillaId, ...] = ()
    unchecked_casilla_ids: tuple[CasillaId, ...] = ()
    mismatched_root_fields: tuple[str, ...] = ()
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    mismatched_casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    file_sha256: str | None = Field(default=None)
    verified_at: datetime
    narrative: str

    @field_validator("mismatched_casilla_ids", "unchecked_casilla_ids")
    @classmethod
    def _validate_casilla_ids(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        for entry in value:
            if not entry or entry != entry.strip():
                raise FilingExportValidationError("casilla-id entries must be non-blank, untrimmed identifiers")
        return value

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str | None) -> str | None:
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


def assert_export_artifact_matches_receipt(receipt: DeclaracionExportResult, *, artifact_path: Path) -> None:
    """Bind a disk artifact's extent and digest to its export receipt."""
    try:
        digest, byte_size = hash_file(artifact_path)
    except OSError as exc:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_artefact_unreadable",
            context={"artifact_path": str(artifact_path), "os_error_type": type(exc).__name__},
        ) from exc
    if byte_size != receipt.byte_size:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_byte_size_mismatch",
            context={
                "artifact_path": str(artifact_path),
                "declared_byte_size": receipt.byte_size,
                "observed_byte_size": byte_size,
            },
        )
    if digest != receipt.file_sha256:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_digest_mismatch",
            context={
                "artifact_path": str(artifact_path),
                "declared_sha256": receipt.file_sha256,
                "observed_sha256": digest,
            },
        )


def verify_export(
    draft: ModeloDraft,
    *,
    file_path: Path,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionVerifyResult:
    """Verify parser-covered bytes and root identity against an approved draft."""
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    _require_current_verify_schema(draft, subview)
    if not subview.export_layout_ids:
        return _missing_registry_layout_verification(draft, file_path)
    return _verify_export_file(draft, file_path=file_path, provider=provider, subview=subview)


def _require_current_verify_schema(draft: ModeloDraft, subview: RegistryModeloSubview) -> None:
    if draft.schema_version != subview.schema_version:
        raise FilingExportError(
            translated_message="application.filing.export.errors.verify_draft_snapshot_stale",
            context={
                "modelo": draft.modelo,
                "draft_schema_version": draft.schema_version,
                "active_schema_version": subview.schema_version,
            },
        )


def _missing_verification_result(
    draft: ModeloDraft, *, file_path: Path, narrative: str, digest: str | None = None
) -> DeclaracionVerifyResult:
    return DeclaracionVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=DeclaracionVerifyVerdict.MISSING,
        file_sha256=digest,
        verified_at=now(),
        narrative=narrative,
    )


def _missing_registry_layout_verification(draft: ModeloDraft, file_path: Path) -> DeclaracionVerifyResult:
    try:
        digest = sha256_file(file_path) if file_path.exists() else None
    except OSError:
        _logger.warning("declaration export verification could not read %s", file_path, exc_info=True)
        digest = None
    return _missing_verification_result(
        draft, file_path=file_path, narrative="filing.export.missing_registry_layout", digest=digest
    )


def _read_verification_payload(file_path: Path) -> bytes | None:
    try:
        return file_path.read_bytes()
    except OSError:
        _logger.warning("declaration export verification could not read %s", file_path, exc_info=True)
        return None


def _verify_export_file(
    draft: ModeloDraft,
    *,
    file_path: Path,
    provider: RegistrySchemaAccessor,
    subview: RegistryModeloSubview,
) -> DeclaracionVerifyResult:
    if not file_path.exists():
        return _missing_verification_result(draft, file_path=file_path, narrative="filing.export.missing_file")
    payload = _read_verification_payload(file_path)
    if payload is None:
        return _missing_verification_result(draft, file_path=file_path, narrative="filing.export.missing_file")
    digest = sha256_hex(payload)
    try:
        mismatched, checked = _mismatched_casilla_ids(
            subview.export_layouts[0], draft=draft, payload=payload, schema_provider=provider
        )
    except RegistryValidationError:
        _logger.warning("declaration export verification could not parse %s", file_path, exc_info=True)
        return _missing_verification_result(
            draft, file_path=file_path, narrative="filing.export.malformed_file", digest=digest
        )
    unchecked = tuple(sorted(value.casilla_id for value in draft.values if value.casilla_id not in set(checked)))
    try:
        mismatched_root = _mismatched_root_fields(
            subview.export_layouts[0], draft=draft, payload=payload, schema_provider=provider
        )
    except FilingExportValidationError:
        _logger.warning("declaration export verification could not read root identity of %s", file_path, exc_info=True)
        return _missing_verification_result(
            draft, file_path=file_path, narrative="filing.export.malformed_file", digest=digest
        )
    return DeclaracionVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=DeclaracionVerifyVerdict.MATCH
        if not mismatched and not mismatched_root
        else DeclaracionVerifyVerdict.DRIFT,
        mismatched_casilla_ids=mismatched,
        unchecked_casilla_ids=unchecked,
        mismatched_root_fields=mismatched_root,
        casilla_provenance=_provenance_for_casillas(draft, checked),
        mismatched_casilla_provenance=_provenance_for_casillas(draft, mismatched),
        file_sha256=digest,
        verified_at=now(),
        narrative="filing.export.verified",
    )


def verify_written_export(draft: ModeloDraft, *, file_path: Path, schema_provider: RegistrySchemaAccessor) -> None:
    """Fail closed unless the just-written declaration re-parses as a match."""
    verification = verify_export(draft, file_path=file_path, schema_provider=schema_provider)
    if verification.verdict is DeclaracionVerifyVerdict.MATCH:
        return
    raise FilingExportError(
        translated_message="application.filing.export.errors.post_write_verification_refused",
        context={
            "artifact_path": str(file_path),
            "verdict": verification.verdict.value,
            "mismatched_casilla_ids": tuple(verification.mismatched_casilla_ids),
            "mismatched_root_fields": tuple(verification.mismatched_root_fields),
        },
    )


def exported_casilla_provenance(
    layout: ExportLayoutDefinition, *, draft: ModeloDraft, schema_provider: RegistrySchemaAccessor
) -> tuple[ModeloCasillaProvenance, ...]:
    """Return the provenance rows for the casillas the layout actually exports.

    Args:
        layout: Export layout deciding which casillas reach the artefact.
        draft: Approved :class:`ModeloDraft` supplying the casilla values.
        schema_provider: Registry accessor resolving the casilla definitions.

    Returns:
        One :class:`ModeloCasillaProvenance` per exported casilla.
    """
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        entries = xml_dictionary_entries(
            layout, source_root=schema_provider.source_root, sources=schema_provider.sources
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


def _mismatched_casilla_ids(
    layout: ExportLayoutDefinition, *, draft: ModeloDraft, payload: bytes, schema_provider: RegistrySchemaAccessor
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]]:
    values = {value.casilla_id: value.value for value in draft.values}
    fields_by_identity = {(record.id, field.id): field for record in layout.records for field in record.fields}
    mismatched: list[CasillaId] = []
    checked: list[CasillaId] = []
    for parsed in parse_export_payload(
        layout, payload, source_root=schema_provider.source_root, sources=schema_provider.sources
    ).casillas:
        if parsed.casilla_id is None:
            continue
        checked.append(parsed.casilla_id)
        expected = values.get(parsed.casilla_id)
        try:
            field = fields_by_identity[(parsed.record_id, parsed.field_id)]
            expected_wire = render_fixed_width_export_field(field, expected)
        except (KeyError, RegistryValidationError) as exc:
            raise FilingExportValidationError(
                f"export field {parsed.field_id!r} could not render its expected verification value"
            ) from exc
        if expected_wire != parsed.raw:
            mismatched.append(parsed.casilla_id)
    return tuple(dict.fromkeys(mismatched)), tuple(dict.fromkeys(checked))


def _mismatched_root_fields(
    layout: ExportLayoutDefinition, *, draft: ModeloDraft, payload: bytes, schema_provider: RegistrySchemaAccessor
) -> tuple[str, ...]:
    if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
        return ()
    expected = expected_xml_dictionary_root_identity(layout, draft=draft, schema_provider=schema_provider)
    actual = read_xml_dictionary_root_identity(payload)
    return tuple(sorted(name for name, value in expected.items() if actual.get(name) != value))


def _provenance_for_casillas(
    draft: ModeloDraft, casilla_ids: Iterable[CasillaId]
) -> tuple[ModeloCasillaProvenance, ...]:
    provenance_by_id = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    return tuple(
        provenance_by_id[casilla_id] for casilla_id in dict.fromkeys(casilla_ids) if casilla_id in provenance_by_id
    )
