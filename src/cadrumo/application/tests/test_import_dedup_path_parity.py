"""The verify preview and the persisting import must agree on every row.

``--verify`` runs the diagnostics path and the actual import runs the
persisting path. They once reasoned oppositely about a fingerprint repeated
within one file: the preview called it a duplicate and counted it skipped, the
import persisted both rows. So the operator was warned about a row the import
would happily keep, and the previewed count was wrong in the direction that
hides money.

Both now consume the same verdict, but each still maintains its own
``seen``/``batch`` sets around that call, and that bookkeeping is where they can
still drift apart. Sharing a function proves nothing on its own — what matters
is that the two real paths reach the same import/skip decision, so this drives
both of them over the same rows and compares the outcomes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.inbound.financial.providers import ParsedLedgerRow
from ...domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    TransactionCatalogue,
    TransactionDirection,
    derive_import_fingerprint,
    derive_transaction_id,
)
from ..ledger._actions_import import _evaluate_import_rows
from ..transactions import import_ledger_with_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "0dac9c08-a56b-41bf-9752-636041072300"  # was 'bucket-parity'
_SOURCE = Path("project/data/parity.csv")
_DIRECTION = TransactionDirection.OUTGOING


def _raw(provider_id: str, *, amount: Decimal = Decimal("121.00"), description: str | None = None) -> RawTransaction:
    """Build a EUR row. EUR keeps the FX normalizer out of the comparison."""
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 4, 5),
        value_date=date(2025, 4, 5),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=description if description is not None else f"row {provider_id}",
        provenance=RawProvenance(
            source_path=_SOURCE,
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _parsed(raw: RawTransaction) -> ParsedLedgerRow:
    """Pair a row with the direction the provider read at the parse boundary."""
    return ParsedLedgerRow(raw=raw, direction=_DIRECTION)


def _preview(rows: tuple[RawTransaction, ...], catalogue: TransactionCatalogue) -> tuple[int, int]:
    """Run the ``--verify`` diagnostics path; return ``(imported, skipped)``."""
    result = import_ledger_with_diagnostics(
        source_path=_SOURCE,
        raw_transactions=rows,
        existing_catalogue=catalogue,
        import_fingerprints=tuple(derive_import_fingerprint(raw, direction=_DIRECTION) for raw in rows),
    )
    return result.imported_count, result.skipped_count


def _persist(rows: tuple[RawTransaction, ...], catalogue: TransactionCatalogue) -> tuple[int, int]:
    """Run the persisting path; return ``(imported, skipped)``."""
    plan = _evaluate_import_rows(
        bucket_id=_BUCKET,
        catalogue=catalogue,
        parsed_rows=tuple(_parsed(raw) for raw in rows),
    )
    return len(plan.imported), len(plan.skipped_refs)


def _stored(rows: tuple[RawTransaction, ...]) -> TransactionCatalogue:
    """Persist ``rows`` through the real import path, returning the catalogue."""
    plan = _evaluate_import_rows(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue(),
        parsed_rows=tuple(_parsed(raw) for raw in rows),
    )
    return TransactionCatalogue.model_validate({tx.transaction_id: tx for tx in plan.imported})


def _input_classes() -> list[tuple[str, tuple[RawTransaction, ...], TransactionCatalogue]]:
    """One case per verdict the classifier can return, plus a mixed batch."""
    single = _raw("tx-1")
    # Same movement identity, distinct provider ids: the fingerprint ignores the
    # provider id, so these share a fingerprint while resolving to two ids.
    repeated_fingerprint = (
        _raw("row-1", description="Cuota mensual"),
        _raw("row-2", description="Cuota mensual"),
    )
    identical_rows = (_raw("tx-1"), _raw("tx-1"))
    return [
        ("all new", (_raw("tx-1"), _raw("tx-2")), TransactionCatalogue()),
        ("empty batch", (), TransactionCatalogue()),
        ("duplicate of stored", (single,), _stored((single,))),
        ("intra-batch id collision", identical_rows, TransactionCatalogue()),
        ("intra-batch fingerprint repeat", repeated_fingerprint, TransactionCatalogue()),
        ("stored plus new", (single, _raw("tx-9")), _stored((single,))),
        ("mixed", (single, _raw("tx-1"), _raw("tx-9")), _stored((single,))),
    ]


@pytest.mark.parametrize(
    ("label", "rows", "catalogue"),
    [pytest.param(label, rows, catalogue, id=label) for label, rows, catalogue in _input_classes()],
)
def test_the_preview_and_the_import_agree_on_every_input_class(
    label: str,
    rows: tuple[RawTransaction, ...],
    catalogue: TransactionCatalogue,
) -> None:
    """The two real paths must reach the same import/skip split."""
    assert _preview(rows, catalogue) == _persist(rows, catalogue), label


def test_an_intra_batch_repeat_is_counted_as_imported_by_both_paths() -> None:
    """The specific regression: a repeat must not be counted skipped anywhere.

    Two rows whose fingerprints match but whose ids differ are two genuine
    movements. Pinned as a literal expectation rather than only as agreement,
    because the two paths agreeing on the *wrong* answer would satisfy the
    parametrised comparison above while under-declaring in both.
    """
    rows = (_raw("row-1", description="Cuota mensual"), _raw("row-2", description="Cuota mensual"))
    fingerprints = {derive_import_fingerprint(raw, direction=_DIRECTION) for raw in rows}
    assert len(fingerprints) == 1, "fixture no longer produces an intra-batch fingerprint repeat"
    assert len({derive_transaction_id(raw) for raw in rows}) == 2, "fixture rows must carry distinct ids"

    assert _preview(rows, TransactionCatalogue()) == (2, 0)
    assert _persist(rows, TransactionCatalogue()) == (2, 0)


def test_an_id_collision_is_counted_as_skipped_by_both_paths() -> None:
    """Two rows resolving to one catalogue key: exactly one can persist."""
    rows = (_raw("tx-1"), _raw("tx-1"))
    assert _preview(rows, TransactionCatalogue()) == (1, 1)
    assert _persist(rows, TransactionCatalogue()) == (1, 1)
