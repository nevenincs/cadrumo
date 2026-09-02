"""The verify preview and the persisting import must classify a row the same way.

``--verify`` runs the diagnostics helper while dry-run and persist run
``_evaluate_import_rows``. The two carried independent duplicate rules and
disagreed on one case: a movement signature repeated WITHIN a single file. The
diagnostics helper counted the second row skipped; the persisting path
deliberately imported both, reasoning that two identical same-day movements are
two genuine movements and that dropping one silently under-declares.

So an operator running ``--verify`` was warned about a duplicate the import would
never skip, and the previewed count was one short of what would land -- short in
the direction that hides money. This pins the agreement rather than either
number, so a future change to the rule has to move both paths together or fail
here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.financial.providers.base import ParsedLedgerRow
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import TransactionCatalogue, derive_import_fingerprint, derive_transaction_id
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...transactions.import_diagnostics import import_ledger_with_diagnostics
from ..actions_import import _evaluate_import_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_PATH = Path("project/data/example.csv")


def _raw(provider_id: str, *, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 4, 5),
        value_date=date(2025, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=description,
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


def _parsed(raw: RawTransaction) -> ParsedLedgerRow:
    return ParsedLedgerRow(raw=raw, direction=TransactionDirection.OUTGOING)


def _both_paths(raws: tuple[RawTransaction, ...]) -> tuple[int, int, int, int]:
    """Return ``(verify_imported, verify_skipped, persist_imported, persist_skipped)``."""
    parsed_rows = tuple(_parsed(raw) for raw in raws)
    fingerprints = tuple(derive_import_fingerprint(parsed.raw, direction=parsed.direction) for parsed in parsed_rows)
    verify = import_ledger_with_diagnostics(
        source_path=_SOURCE_PATH,
        raw_transactions=raws,
        existing_catalogue=TransactionCatalogue(),
        import_fingerprints=fingerprints,
    )
    plan = _evaluate_import_rows(
        bucket_id="preview",
        catalogue=TransactionCatalogue(),
        parsed_rows=parsed_rows,
    )
    return (verify.imported_count, verify.skipped_count, len(plan.imported), len(plan.skipped_refs))


def test_the_fixture_rows_share_a_signature_without_colliding_on_the_key() -> None:
    """Anchor test: the divergence only exists for this exact shape.

    If the rows ever collide on the transaction id too, both paths skip and the
    parity case below passes while testing nothing.
    """
    first, second = _raw("tx-1", description="Retainer"), _raw("tx-2", description="Retainer")
    assert derive_import_fingerprint(first) == derive_import_fingerprint(second)
    assert derive_transaction_id(first) != derive_transaction_id(second)


def test_a_repeated_movement_signature_is_counted_the_same_by_both_paths() -> None:
    """THE divergence. Verify said one imported and one skipped; persist said two."""
    rows = (_raw("tx-1", description="Retainer"), _raw("tx-2", description="Retainer"))

    verify_imported, verify_skipped, persist_imported, persist_skipped = _both_paths(rows)

    assert (verify_imported, verify_skipped) == (persist_imported, persist_skipped)
    assert verify_imported == 2, "the preview under-counted what the import would land"


def test_rows_colliding_on_the_catalogue_key_are_counted_the_same_by_both_paths() -> None:
    """The intra-batch case that IS a skip, agreed on by both paths."""
    rows = (_raw("tx-1", description="Retainer"), _raw("tx-1", description="Retainer"))

    verify_imported, verify_skipped, persist_imported, persist_skipped = _both_paths(rows)

    assert (verify_imported, verify_skipped) == (persist_imported, persist_skipped)
    assert verify_imported == 1


def test_distinct_movements_are_counted_the_same_by_both_paths() -> None:
    """Positive control: the paths do not agree merely by both refusing everything."""
    rows = (_raw("tx-1", description="Retainer"), _raw("tx-2", description="Hosting"))

    verify_imported, verify_skipped, persist_imported, persist_skipped = _both_paths(rows)

    assert (verify_imported, verify_skipped) == (persist_imported, persist_skipped)
    assert (verify_imported, verify_skipped) == (2, 0)
