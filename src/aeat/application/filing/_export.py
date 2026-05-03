"""Typed records for the v6 declaration export / verify lifecycle.

The v6 CLI candidate exposes two primitives the application layer must
back end-to-end:

- ``aeat app declaration export --output PATH`` writes an
  AEAT-compatible file (typically the fichero-BOE fixed-width payload
  produced by :mod:`aeat.adapters.outbound.aeat.export._formats`) for an
  approved :class:`aeat.domain.filing.FilingDraft` and reports the
  byte-level summary the operator needs to track the artefact (output
  path, draft identity, content hash, format).
- ``aeat app declaration verify --file PATH`` re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

This module ships the *typed surface* the CLI implementation team can
render, persist, and JSON round-trip against — while the orchestration
that drives the actual export-and-verify loop lands incrementally on
top of the existing :mod:`aeat.adapters.outbound.aeat.export` format
serialisers and deserialisers.

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
            the AEAT *Diseño de registros* per modelo. Produced by
            :mod:`aeat.adapters.outbound.aeat.export._formats`.
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
    import hashlib
    from datetime import UTC
    from decimal import Decimal

    from ...domain.filing import FilingDraftStatus

    if draft.status is not FilingDraftStatus.APPROVED:
        raise ValueError("Cannot export a draft that is not APPROVED")

    casillas: dict[str, Decimal] = {}
    for value in draft.values:
        if isinstance(value.value, Decimal):
            casillas[value.casilla_id] = value.value
        elif isinstance(value.value, int) and not isinstance(value.value, bool):
            casillas[value.casilla_id] = Decimal(value.value)

    payload_bytes = b""
    year = draft.period[:4]
    if draft.modelo == "130":
        from ...adapters.outbound.aeat.export._formats._serialise import serialise

        if int(year) >= 2025:
            from ...adapters.outbound.aeat.export._formats import modelo_130_2025 as module
        else:
            from ...adapters.outbound.aeat.export._formats import modelo_130_2024 as module

        payload_bytes = serialise(
            casilla_values=casillas,
            headers=headers,  # type: ignore[arg-type]
            specs=module.RECORD_SPECS,
            encoding=module.ENCODING,
            total_length=module.RECORD_LENGTH,
            required_field_ids=module.REQUIRED_HEADER_FIELDS,
        )
    elif draft.modelo == "303":
        from ...adapters.outbound.aeat.export._formats._serialise import serialise_envelope

        if int(year) >= 2025:
            from ...adapters.outbound.aeat.export._formats import modelo_303_2025 as module
        else:
            from ...adapters.outbound.aeat.export._formats import modelo_303_2024 as module

        payload_bytes = serialise_envelope(
            casilla_values=casillas,
            headers=headers,  # type: ignore[arg-type]
            segments=module.ENVELOPE,
            encoding=module.ENCODING,
            required_field_ids=module.REQUIRED_HEADER_FIELDS,
        )
    else:
        raise ValueError(f"export not supported for modelo {draft.modelo}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload_bytes)

    file_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    _logger.info(
        "exported draft draft_id=%s modelo=%s period=%s bytes=%d path=%s",
        draft.draft_id,
        draft.modelo,
        draft.period,
        len(payload_bytes),
        output_path,
    )
    return DeclarationExportResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=DeclarationExportFormat.FICHERO_BOE,
        output_path=output_path,
        byte_size=len(payload_bytes),
        file_sha256=file_sha256,
        exported_at=datetime.now(tz=UTC),
        narrative=Translatable(
            es=f"Fichero BOE generado para modelo {draft.modelo}.",
            en=f"Fichero BOE generated for modelo {draft.modelo}.",
            ca=f"Fitxer BOE generat per al model {draft.modelo}.",
            hu=f"BOE fájl generálva a {draft.modelo} modellhez.",
        ),
    )


def verify_export(
    draft: FilingDraft,
    *,
    file_path: Path,
) -> DeclarationVerifyResult:
    """Verify an exported file against an approved draft and return a verdict."""
    import hashlib
    from datetime import UTC
    from decimal import Decimal

    payload_bytes = file_path.read_bytes()
    file_sha256 = hashlib.sha256(payload_bytes).hexdigest()

    parsed_casillas: dict[str, Decimal] = {}
    try:
        year = draft.period[:4]
        if draft.modelo == "130":
            from ...adapters.outbound.aeat.export._formats._deserialise import deserialise

            if int(year) >= 2025:
                from ...adapters.outbound.aeat.export._formats import modelo_130_2025 as module
            else:
                from ...adapters.outbound.aeat.export._formats import modelo_130_2024 as module

            parsed_casillas = dict(
                deserialise(
                    payload_bytes,
                    specs=module.RECORD_SPECS,
                    encoding=module.ENCODING,
                    total_length=module.RECORD_LENGTH,
                ).casilla_values
            )
        elif draft.modelo == "303":
            from ...adapters.outbound.aeat.export._formats._deserialise import deserialise_envelope

            if int(year) >= 2025:
                from ...adapters.outbound.aeat.export._formats import modelo_303_2025 as module
            else:
                from ...adapters.outbound.aeat.export._formats import modelo_303_2024 as module

            parsed_casillas = dict(
                deserialise_envelope(
                    payload_bytes,
                    segments=module.ENVELOPE,
                    encoding=module.ENCODING,
                ).merged_casilla_values
            )
        else:
            raise ValueError(f"verify not supported for modelo {draft.modelo}")
    except (ValueError, UnicodeDecodeError, AssertionError, OSError):
        _logger.warning(
            "verify: failed to parse export file draft_id=%s path=%s",
            draft.draft_id,
            file_path,
            exc_info=True,
        )
        return DeclarationVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclarationVerifyVerdict.MISSING,
            file_sha256=file_sha256,
            verified_at=datetime.now(tz=UTC),
            narrative={
                "es": "No se pudo interpretar el archivo como fichero BOE.",
                "en": "File could not be parsed as fichero BOE.",
            },
        )

    expected: dict[str, Decimal] = {}
    for value in draft.values:
        if isinstance(value.value, Decimal):
            expected[value.casilla_id] = value.value.quantize(Decimal("0.01"))
        elif isinstance(value.value, int) and not isinstance(value.value, bool):
            expected[value.casilla_id] = Decimal(value.value).quantize(Decimal("0.01"))

    comparable_keys = sorted(set(expected) & set(parsed_casillas))
    unchecked = tuple(sorted(set(expected) - set(comparable_keys)))
    if expected and not comparable_keys:
        return DeclarationVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclarationVerifyVerdict.MISSING,
            file_sha256=file_sha256,
            verified_at=datetime.now(tz=UTC),
            narrative=Translatable(
                es="El archivo no expone casillas comparables para este borrador.",
                en="File exposes no comparable casillas for this draft.",
                ca="L'arxiu no exposa caselles comparables per a aquest esborrany.",
                hu="A fájl nem tartalmaz összehasonlítható rovatokat ehhez a tervezethez.",
            ),
        )

    mismatched = []
    for key in comparable_keys:
        expected_val = expected[key]
        actual_val = parsed_casillas[key].quantize(Decimal("0.01"))
        if expected_val != actual_val:
            mismatched.append(key)

    if mismatched:
        verdict = DeclarationVerifyVerdict.DRIFT
        narrative = Translatable(
            es="El archivo difiere del borrador aprobado.",
            en="File drifts from the approved draft.",
            ca="L'arxiu difereix de l'esborrany aprovat.",
            hu="A fájl eltér a jóváhagyott tervezettől.",
        )
        _logger.warning(
            "verify found drift draft_id=%s path=%s mismatched_casillas=%d",
            draft.draft_id,
            file_path,
            len(mismatched),
        )
    else:
        verdict = DeclarationVerifyVerdict.MATCH
        narrative = Translatable(
            es="El archivo coincide con el borrador aprobado.",
            en="File matches the approved draft.",
            ca="L'arxiu coincideix amb l'esborrany aprovat.",
            hu="A fájl megegyezik a jóváhagyott tervezettel.",
        )
        _logger.debug("verify matched draft_id=%s path=%s", draft.draft_id, file_path)

    return DeclarationVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=verdict,
        mismatched_casillas=tuple(sorted(mismatched)),
        unchecked_casillas=unchecked,
        file_sha256=file_sha256,
        verified_at=datetime.now(tz=UTC),
        narrative=narrative,
    )


__all__ = [
    "DeclarationExportFormat",
    "DeclarationExportResult",
    "DeclarationVerifyResult",
    "DeclarationVerifyVerdict",
    "export_draft",
    "verify_export",
]
