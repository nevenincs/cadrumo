"""Typed diagnostic records for the ledger-import use case.

The CLI uses a closed catalogue of import
diagnostic kinds emitted by ``aeat app ledger import PATH --provider PROVIDER --verify``:

- ``original-file`` — records the caller-supplied original source file
  path when it is available, so import reports can distinguish the
  parsed input path from the source artefact the operator intended to
  verify.
- ``gap`` — detects calendar gaps in the imported transaction
  stream so the operator notices a missing month / week / day
  without rerunning analytics.
- ``duplicate`` — flags an imported transaction whose stable id
  matches one already in the ledger so re-importing the same
  bank statement does not double-count.
- ``parser`` — reports a parser-level problem (malformed cell,
  unknown column, encoding hint mismatch) without aborting the
  import outright.

The CLI consumes :class:`~cadrumo.application.transactions.LedgerImportDiagnostic`
records via
:func:`~cadrumo.application.transactions.build_ledger_import_diagnostic` and renders
them grouped by ``severity`` and ``kind``.

See Also:
    :class:`~cadrumo.application.transactions.LedgerImportDiagnosticKind`,
    :class:`~cadrumo.application.transactions.LedgerImportDiagnostic`, and
    :func:`~cadrumo.application.transactions.build_ledger_import_diagnostic`.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ...core.errors.severity import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG


class LedgerImportDiagnosticKind(StrEnum):
    """Closed catalogue of ledger-import diagnostic categories."""

    ORIGINAL_FILE = "original-file"
    GAP = "gap"
    DUPLICATE = "duplicate"
    PARSER = "parser"


class LedgerImportDiagnostic(BaseModel):
    """One typed diagnostic emitted by the ledger import use-case.

    Attributes:
        kind: Closed
            :class:`~cadrumo.application.transactions.LedgerImportDiagnosticKind`.
        severity: :class:`~cadrumo.core.errors.BaseSeverity`.
        message: A strictly-typed :class:`~cadrumo.core.i18n._Translatable` key.
        source_path: Optional pointer at the source artefact the
            diagnostic refers to (input file, provider name, etc.).
        source_locator: Optional sub-path inside ``source_path``
            (row index, column name, period range) the diagnostic
            scopes to.
        affected_transaction_ids: Tuple of stable transaction
            identifiers the diagnostic refers to. Empty for
            file-wide diagnostics (e.g., a malformed header).
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: LedgerImportDiagnosticKind
    severity: BaseSeverity
    message: tr
    source_path: Path | None = None
    source_locator: str | None = Field(default=None, max_length=256)
    affected_transaction_ids: tuple[str, ...] = ()

    @field_validator("message")
    @classmethod
    def _require_authoritative_message(cls, value: str) -> str:
        """Reject diagnostics without an authoritative Spanish message."""
        from ...core.i18n import tr

        if not value or not str(value).strip():
            raise ValueError("message must be a non-empty Translatable key")
        # tr() humanises unknown keys into a readable fallback, so a plain
        # round-trip comparison no longer detects missing entries. Pass a
        # unique sentinel default: a key with no Spanish catalogue entry
        # renders back the sentinel verbatim.
        sentinel = f"\x00no-translation\x00{value}"
        rendered = tr(str(value), locale="es", default=sentinel)
        if rendered == sentinel:
            raise ValueError(f"message key {value!r} has no authoritative Spanish translation")
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
    severity: BaseSeverity,
    message: tr,
    source_path: Path | None = None,
    source_locator: str | None = None,
    affected_transaction_ids: tuple[str, ...] = (),
) -> LedgerImportDiagnostic:
    """Construct a diagnostic with the canonical field order.

    Centralised factory so adding new optional metadata later means
    extending this helper rather than every emit site. The returned
    :class:`~cadrumo.application.transactions.LedgerImportDiagnostic` preserves the
    closed :class:`~cadrumo.application.transactions.LedgerImportDiagnosticKind`
    and :class:`~cadrumo.core.errors.BaseSeverity` values the CLI groups by.
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
    "build_ledger_import_diagnostic",
]
