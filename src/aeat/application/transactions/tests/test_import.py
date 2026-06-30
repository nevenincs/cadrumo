"""Focused unit tests for application.transactions._import.

`import_ledger_with_diagnostics` orchestrates four classes of
diagnostic over an imported batch of raw transactions:

- PARSER WARNING when the batch is empty (the source file produced
  no rows).
- DUPLICATE INFO when a row's stable id is already present in the
  existing catalogue.
- DUPLICATE WARNING when two rows inside the same batch share a
  stable id.
- GAP WARNING when the sorted ``value_date or booked_date`` deltas
  contain a >35-day gap (emitted at most once per file).
- ORIGINAL_FILE INFO when a verifiable original source path is
  supplied and the file exists on disk.

The helper is currently uncovered by direct unit tests; coverage
through the CLI runner pipeline only exercises the happy path.
A regression in (a) the duplicate-vs-seen branch ordering,
(b) the gap-emission breaker, or (c) the original-file verification
would silently corrupt every operator's import experience.

Tests pin the branch presence and counter shape; assertions are
structural / aggregator-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.errors import BaseSeverity
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.transactions._models import derive_transaction_id
from .._diagnostics import (
    LedgerImportDiagnosticKind,
)
from .._import import import_ledger_with_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    amount: Decimal = Decimal("121.00"),
    description: str | None = None,
) -> RawTransaction:
    """Build a minimal RawTransaction with stable distinguishing fields.

    ``derive_transaction_id`` keys on (provider_id, value_date,
    amount, description) — vary any of those to produce a distinct id.
    """
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=description if description is not None else f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


_SOURCE_PATH = Path("project/data/example.csv")


# ---------------------------------------------------------------------------
# Empty batch
# ---------------------------------------------------------------------------


def test_import_empty_batch_emits_parser_warning_and_zero_counts() -> None:
    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(),
        existing_catalogue=TransactionCatalogue(),
    )

    assert result.imported_count == 0
    assert result.skipped_count == 0
    assert len(result.diagnostics) == 1
    only = result.diagnostics[0]
    assert only.kind is LedgerImportDiagnosticKind.PARSER
    assert only.severity is BaseSeverity.WARNING


def test_import_empty_batch_short_circuits_before_original_file_check(tmp_path: Path) -> None:
    """When rows is empty the helper returns before the original-file
    block — even a present original_source_path produces no
    ORIGINAL_FILE diagnostic."""
    original = tmp_path / "original.csv"
    original.write_bytes(b"any,bytes")

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(),
        existing_catalogue=TransactionCatalogue(),
        original_source_path=original,
    )

    kinds = [d.kind for d in result.diagnostics]
    assert LedgerImportDiagnosticKind.ORIGINAL_FILE not in kinds


# ---------------------------------------------------------------------------
# Single row happy path
# ---------------------------------------------------------------------------


def test_import_single_row_yields_one_imported_no_diagnostics() -> None:
    raw = _raw_transaction("tx-1")

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(raw,),
        existing_catalogue=TransactionCatalogue(),
    )

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.diagnostics == ()


# ---------------------------------------------------------------------------
# Duplicate branches
# ---------------------------------------------------------------------------


def test_import_duplicate_within_file_emits_duplicate_warning() -> None:
    """Two rows in the same batch with identical id-keying fields
    (provider_id, value_date, amount, description) produce a
    DUPLICATE WARNING for the second occurrence."""
    raw_a = _raw_transaction("tx-1")
    raw_b = _raw_transaction("tx-1")  # same identity → same derived id

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(raw_a, raw_b),
        existing_catalogue=TransactionCatalogue(),
    )

    assert result.imported_count == 1
    assert result.skipped_count == 1
    duplicate_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.DUPLICATE]
    assert len(duplicate_diagnostics) == 1
    assert duplicate_diagnostics[0].severity is BaseSeverity.WARNING


def test_import_duplicate_against_catalogue_emits_duplicate_info() -> None:
    """A row whose derived id already lives in the catalogue produces
    a DUPLICATE INFO diagnostic. INFO severity (rather than WARNING)
    is the documented distinguisher between re-import and in-file
    duplicate."""
    raw = _raw_transaction("tx-1")
    transaction = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    catalogue = TransactionCatalogue.model_validate({transaction.transaction_id: transaction})

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(raw,),
        existing_catalogue=catalogue,
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    duplicate_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.DUPLICATE]
    assert len(duplicate_diagnostics) == 1
    assert duplicate_diagnostics[0].severity is BaseSeverity.INFO


def test_import_duplicate_diagnostic_carries_affected_transaction_id() -> None:
    """The diagnostic's affected_transaction_ids tuple captures the
    derived stable id of the duplicate so downstream tooling can
    point the operator at the offending row."""
    raw_a = _raw_transaction("tx-1")
    raw_b = _raw_transaction("tx-1")
    derived_id = derive_transaction_id(raw_a)

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(raw_a, raw_b),
        existing_catalogue=TransactionCatalogue(),
    )

    duplicate_diagnostic = next(d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.DUPLICATE)
    assert duplicate_diagnostic.affected_transaction_ids == (derived_id,)


# ---------------------------------------------------------------------------
# Gap branch
# ---------------------------------------------------------------------------


def test_import_consecutive_dates_emit_no_gap_diagnostic() -> None:
    """A run of consecutive dates yields no GAP warning."""
    rows = [
        _raw_transaction("tx-1", value_date=date(2025, 4, 1)),
        _raw_transaction("tx-2", value_date=date(2025, 4, 5)),
        _raw_transaction("tx-3", value_date=date(2025, 4, 10)),
    ]

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=rows,
        existing_catalogue=TransactionCatalogue(),
    )

    kinds = [d.kind for d in result.diagnostics]
    assert LedgerImportDiagnosticKind.GAP not in kinds


def test_import_36_day_gap_emits_single_gap_warning() -> None:
    """Two rows >35 days apart emit one GAP WARNING."""
    rows = [
        _raw_transaction("tx-1", value_date=date(2025, 1, 1)),
        _raw_transaction("tx-2", value_date=date(2025, 2, 10)),
    ]

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=rows,
        existing_catalogue=TransactionCatalogue(),
    )

    gap_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.GAP]
    assert len(gap_diagnostics) == 1
    assert gap_diagnostics[0].severity is BaseSeverity.WARNING


def test_import_multiple_gaps_emit_only_one_diagnostic() -> None:
    """The helper short-circuits after the first detected gap to
    avoid noisy duplicated GAP diagnostics within one file."""
    rows = [
        _raw_transaction("tx-1", value_date=date(2025, 1, 1)),
        _raw_transaction("tx-2", value_date=date(2025, 2, 10)),  # gap #1
        _raw_transaction("tx-3", value_date=date(2025, 4, 1)),  # gap #2
    ]

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=rows,
        existing_catalogue=TransactionCatalogue(),
    )

    gap_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.GAP]
    assert len(gap_diagnostics) == 1


def test_import_gap_uses_value_date_with_booked_date_fallback() -> None:
    """Rows without a value_date fall back to booked_date for gap math."""
    rows = [
        _raw_transaction("tx-1", value_date=None, booked_date=date(2025, 1, 1)),
        _raw_transaction("tx-2", value_date=None, booked_date=date(2025, 2, 10)),
    ]

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=rows,
        existing_catalogue=TransactionCatalogue(),
    )

    gap_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.GAP]
    assert len(gap_diagnostics) == 1


# ---------------------------------------------------------------------------
# Original-file branch
# ---------------------------------------------------------------------------


def test_import_original_source_present_emits_original_file_info(tmp_path: Path) -> None:
    """A supplied original_source_path that exists on disk emits one
    ORIGINAL_FILE INFO diagnostic scoped at the original path."""
    original = tmp_path / "original.csv"
    original.write_bytes(b"any,bytes\n")

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(_raw_transaction("tx-1"),),
        existing_catalogue=TransactionCatalogue(),
        original_source_path=original,
    )

    original_diagnostics = [d for d in result.diagnostics if d.kind is LedgerImportDiagnosticKind.ORIGINAL_FILE]
    assert len(original_diagnostics) == 1
    assert original_diagnostics[0].severity is BaseSeverity.INFO
    assert original_diagnostics[0].source_path == original


def test_import_original_source_missing_emits_no_original_file_diagnostic(tmp_path: Path) -> None:
    """A supplied original_source_path that does not exist produces
    no ORIGINAL_FILE diagnostic — the helper does not flag missing
    originals as warnings (a missing original is a CLI-layer concern)."""
    missing_original = tmp_path / "does-not-exist.csv"

    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(_raw_transaction("tx-1"),),
        existing_catalogue=TransactionCatalogue(),
        original_source_path=missing_original,
    )

    kinds = [d.kind for d in result.diagnostics]
    assert LedgerImportDiagnosticKind.ORIGINAL_FILE not in kinds


def test_import_no_original_source_emits_no_original_file_diagnostic() -> None:
    """When original_source_path is None the helper does not emit an
    ORIGINAL_FILE diagnostic — the verification block is fully gated
    on the kwarg being supplied."""
    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(_raw_transaction("tx-1"),),
        existing_catalogue=TransactionCatalogue(),
    )

    kinds = [d.kind for d in result.diagnostics]
    assert LedgerImportDiagnosticKind.ORIGINAL_FILE not in kinds


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_import_returns_strict_frozen_result() -> None:
    """LedgerImportResult is strict/frozen; attempts to mutate raise."""
    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(_raw_transaction("tx-1"),),
        existing_catalogue=TransactionCatalogue(),
    )

    attr = "imported_count"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(result, attr, 99)


def test_import_diagnostics_is_tuple_not_list() -> None:
    """The diagnostics field is a tuple — an immutable shape so
    downstream consumers can iterate without defensive copies."""
    result = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=(),
        existing_catalogue=TransactionCatalogue(),
    )

    assert isinstance(result.diagnostics, tuple)
