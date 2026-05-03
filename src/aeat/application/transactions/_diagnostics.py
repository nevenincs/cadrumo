"""Typed diagnostic records for the ledger-import use case.

The CLI uses a closed catalogue of import
diagnostic kinds emitted by ``aeat app ledger import PATH --provider PROVIDER --verify``:

- ``original-file`` — verifies an imported batch against the
  original source file (encoding, byte size, hash) so a partial
  download or rename surfaces clearly.
- ``gap`` — detects calendar gaps in the imported transaction
  stream so the operator notices a missing month / week / day
  without rerunning analytics.
- ``duplicate`` — flags an imported transaction whose stable id
  matches one already in the ledger so re-importing the same
  bank statement does not double-count.
- ``parser`` — reports a parser-level problem (malformed cell,
  unknown column, encoding hint mismatch) without aborting the
  import outright.

The CLI consumes :class:`LedgerImportDiagnostic` records via
:func:`build_ledger_import_diagnostic` and renders them grouped
by ``severity`` and ``kind``.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative


class LedgerImportDiagnosticKind(StrEnum):
    """Closed catalogue of ledger-import diagnostic categories."""

    ORIGINAL_FILE = "original-file"
    GAP = "gap"
    DUPLICATE = "duplicate"
    PARSER = "parser"


class LedgerImportDiagnosticSeverity(StrEnum):
    """Severity of a single :class:`LedgerImportDiagnostic`.

    Used to group rendered output and decide whether to
    short-circuit the import. ``WARNING`` is informational only;
    ``ERROR`` blocks ingestion of the affected row(s).
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LedgerImportDiagnostic(BaseModel):
    """One typed diagnostic emitted by the ledger import use-case.

    Attributes:
        kind: Closed :class:`LedgerImportDiagnosticKind`.
        severity: :class:`LedgerImportDiagnosticSeverity`.
        message: Multilingual operator-facing message; Spanish is
            authoritative per the project i18n contract.
        source_path: Optional pointer at the source artefact the
            diagnostic refers to (input file, provider name, etc.).
        source_locator: Optional sub-path inside ``source_path``
            (row index, column name, period range) the diagnostic
            scopes to.
        affected_transaction_ids: Tuple of stable transaction
            identifiers the diagnostic refers to. Empty for
            file-wide diagnostics (e.g., a malformed header).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: LedgerImportDiagnosticKind
    severity: LedgerImportDiagnosticSeverity
    message: Translatable
    source_path: Path | None = None
    source_locator: str | None = Field(default=None, max_length=256)
    affected_transaction_ids: tuple[str, ...] = ()

    @field_validator("message")
    @classmethod
    def _require_authoritative_message(cls, value: Translatable) -> Translatable:
        """Reject diagnostics without an authoritative Spanish message."""
        try:
            require_authoritative(value, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("source_locator")
    @classmethod
    def _trim_source_locator(cls, value: str | None) -> str | None:
        """Trim the source locator while rejecting blank-but-not-None values."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("source_locator must not be blank when provided")
        return trimmed


def build_ledger_import_diagnostic(
    *,
    kind: LedgerImportDiagnosticKind,
    severity: LedgerImportDiagnosticSeverity,
    message: Translatable,
    source_path: Path | None = None,
    source_locator: str | None = None,
    affected_transaction_ids: tuple[str, ...] = (),
) -> LedgerImportDiagnostic:
    """Construct a :class:`LedgerImportDiagnostic` with the canonical field order.

    Wraps the constructor so the application use-case has a single
    factory the CLI tests can stub. Adding new optional metadata
    later means extending this helper rather than every emit site.
    """
    return LedgerImportDiagnostic(
        kind=kind,
        severity=severity,
        message=message,
        source_path=source_path,
        source_locator=source_locator,
        affected_transaction_ids=affected_transaction_ids,
    )


__all__ = [
    "LedgerImportDiagnostic",
    "LedgerImportDiagnosticKind",
    "LedgerImportDiagnosticSeverity",
    "build_ledger_import_diagnostic",
]
