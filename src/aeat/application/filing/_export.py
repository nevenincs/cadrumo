"""Typed records for the declaration export / verify lifecycle.

The CLI exposes two primitives the application layer must back end-to-end:

- ``aeat app declaration export --output PATH`` writes an
  AEAT-compatible file from a validated registry snapshot for an approved
  :class:`aeat.domain.filing.FilingDraft` and reports the byte-level
  summary the operator needs to track the artefact (output path, draft
  identity, content hash, format).
- ``aeat app declaration verify --file PATH`` re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

The records are structured return values for renderers, persistence, and
JSON round trips. Runtime export remains disabled until registry-backed
schemas replace the deleted generated modules.

The records intentionally do not embed the AEAT submission lifecycle
(:mod:`aeat.domain.submission`) — local export and live submit are
separate concerns and live submit is permanently forbidden.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.filing import FilingDraft

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative
from ...core.logging import get_logger

_logger = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` enforcing strict, frozen, no-extras."""


_SHA256_HEX_LENGTH = 64
"""Length of a hex-encoded SHA-256 digest used by export receipts."""


class DeclarationExportFormat(StrEnum):
    """Closed catalogue of AEAT-compatible export formats.

    Attributes:
        FICHERO_BOE: Fixed-width "importar datos" payload defined by
            the AEAT *Diseño de registros* per modelo and validated
            through the registry.
    """

    FICHERO_BOE = "fichero-boe"


class DeclarationVerifyVerdict(StrEnum):
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


class DeclarationExportResult(BaseModel):
    """Receipt produced by exporting an approved draft to disk.

    The record is the structured-data return value of the
    `aeat app declaration export` command. It carries enough metadata
    for the operator to identify the artefact later, for the verify
    command to anchor its comparison, and for the audit log to record
    the export event without re-reading the file.

    Attributes:
        draft_id: The :class:`aeat.domain.filing.FilingDraft` identity
            the export was generated from.
        modelo: AEAT modelo identifier (e.g. ``"130"``, ``"303"``).
        period: Canonical period identifier (e.g. ``"2026Q1"``).
        format: The on-disk wire format (closed
            :class:`DeclarationExportFormat`).
        output_path: Absolute path the file was written to.
        byte_size: Size of the written content in bytes; matches
            ``output_path.stat().st_size`` at write time.
        file_sha256: Hex-encoded SHA-256 digest of the written bytes.
            Used by :class:`DeclarationVerifyResult` to anchor the
            file-vs-draft comparison.
        exported_at: UTC timestamp of when the file was written.
        narrative: Multilingual operator-facing summary, Spanish
            authoritative per the project's i18n contract.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    format: DeclarationExportFormat
    output_path: Path
    byte_size: int = Field(ge=0)
    file_sha256: str = Field(min_length=_SHA256_HEX_LENGTH, max_length=_SHA256_HEX_LENGTH)
    exported_at: datetime
    narrative: Translatable

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        """Reject anything that is not a lowercase hex SHA-256 digest."""
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise ValueError("file_sha256 must be lowercase hex")
        return value

    @field_validator("narrative")
    @classmethod
    def _require_authoritative_narrative(cls, value: Translatable) -> Translatable:
        """Reject narratives that omit the authoritative Spanish key."""
        try:
            require_authoritative(value, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return value


class DeclarationVerifyResult(BaseModel):
    """Verdict produced by verifying an exported file against an approved draft.

    The verify command re-reads the file the export command wrote and
    compares its casilla payload against the approved
    :class:`aeat.domain.filing.FilingDraft`. The verdict is the typed
    return value the CLI renders.

    Attributes:
        draft_id: The :class:`aeat.domain.filing.FilingDraft` identity
            the file was compared against.
        file_path: Absolute path of the file that was verified.
        verdict: Closed :class:`DeclarationVerifyVerdict`.
        mismatched_casillas: Tuple of casilla identifiers whose value
            in the file differs from the approved draft. Empty when
            ``verdict is MATCH``; populated when ``verdict is DRIFT``;
            always empty when ``verdict is MISSING`` (the diff cannot
            be computed).
        unchecked_casillas: Tuple of draft casilla identifiers that do
            not round-trip through the export parser because the wire
            schema exposes them as reserved constants or derived fields
            rather than deserialised currency casillas.
        file_sha256: Hex SHA-256 of the bytes the verifier read.
            Lets the audit trail prove the same file the export
            command wrote was the one verified, even if
            ``output_path`` was renamed in between.
        verified_at: UTC timestamp of when the verdict was produced.
        narrative: Multilingual operator-facing summary, Spanish
            authoritative per the project's i18n contract.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    file_path: Path
    verdict: DeclarationVerifyVerdict
    mismatched_casillas: tuple[str, ...] = ()
    unchecked_casillas: tuple[str, ...] = ()
    file_sha256: str | None = Field(default=None)
    verified_at: datetime
    narrative: Translatable

    @field_validator("mismatched_casillas", "unchecked_casillas")
    @classmethod
    def _validate_casilla_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject blank casilla identifiers; the CLI renders them verbatim."""
        for entry in value:
            if not entry or entry != entry.strip():
                raise ValueError("mismatched_casillas entries must be non-blank, untrimmed identifiers")
        return value

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str | None) -> str | None:
        """Match :class:`DeclarationExportResult` digest hygiene when present."""
        if value is None:
            return None
        if len(value) != _SHA256_HEX_LENGTH:
            raise ValueError(f"file_sha256 must be {_SHA256_HEX_LENGTH} hex characters when provided")
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise ValueError("file_sha256 must be lowercase hex")
        return value

    @field_validator("narrative")
    @classmethod
    def _require_authoritative_narrative(cls, value: Translatable) -> Translatable:
        """Reject narratives that omit the authoritative Spanish key."""
        try:
            require_authoritative(value, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return value


def export_draft(
    draft: FilingDraft,
    *,
    output_path: Path,
    headers: dict[str, str],
) -> DeclarationExportResult:
    """Write an approved draft to a fichero-BOE file and return a receipt."""
    _ = (draft, output_path, headers)
    raise ValueError("declaration export requires a validated registry snapshot; generated exporters are disabled")


def verify_export(
    draft: FilingDraft,
    *,
    file_path: Path,
) -> DeclarationVerifyResult:
    """Verify an exported file against an approved draft and return a verdict."""
    _ = (draft, file_path)
    raise ValueError("declaration verify requires a validated registry snapshot; generated exporters are disabled")


__all__ = [
    "DeclarationExportFormat",
    "DeclarationExportResult",
    "DeclarationVerifyResult",
    "DeclarationVerifyVerdict",
    "export_draft",
    "verify_export",
]
