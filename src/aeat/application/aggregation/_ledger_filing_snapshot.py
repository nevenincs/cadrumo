"""Capture and staleness for the modelo filing ledger snapshot.

The pure records and fingerprint diff live in the domain
(:mod:`aeat.domain.modelos._ledger_filing_snapshot`). This application module
holds the Transaction-aware halves: computing a contributor's content
fingerprint from the live catalogue, building a :class:`LedgerFilingSnapshot`
for a revision's ``source_transaction_ids``, and evaluating drift between a
filed snapshot and the current ledger state.

The fingerprint covers exactly the transaction facts that can move a casilla --
dates, signed amount, currency, direction, business classification and
proportionality, the IVA base/rate/amount/category, the spending and IRPF
categories, the EU member state, the FX conversion, and the lifecycle state.
Cosmetic fields (description, counterparty, notes) are deliberately excluded so
staleness fires on material change, not on a relabel.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date, datetime

from ...domain.modelos._ledger_filing_snapshot import (
    LedgerFilingSnapshot,
    LedgerFilingStalenessVerdict,
    LedgerRowFingerprint,
    diff_ledger_fingerprints,
    snapshot_fingerprint,
)
from ...domain.transactions import Transaction, TransactionCatalogue

# Tax-relevant projection: (label, accessor). Order is fixed and canonical.
_FINGERPRINT_FIELDS: tuple[tuple[str, str], ...] = (
    ("booked_date", "raw.booked_date"),
    ("value_date", "raw.value_date"),
    ("amount", "raw.amount"),
    ("currency", "raw.currency"),
    ("direction", "direction"),
    ("business_classification", "business_classification"),
    ("business_pct", "business_pct"),
    ("taxable_base", "taxable_base"),
    ("iva_rate", "iva_rate"),
    ("iva_amount", "iva_amount"),
    ("iva_category", "iva_category"),
    ("category_id", "category_id"),
    ("irpf_category", "irpf_category"),
    ("counterparty_eu_member_state", "counterparty_eu_member_state"),
    ("fx_rate", "fx_rate"),
    ("value_in_eur", "value_in_eur"),
    ("lifecycle_state", "lifecycle_state"),
)


def _normalise(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _resolve(transaction: Transaction, path: str) -> object:
    target: object = transaction
    for attr in path.split("."):
        target = getattr(target, attr)
    return target


def row_fingerprint(transaction: Transaction) -> str:
    """Return the SHA-256 content fingerprint of one transaction's tax facts."""
    canonical = "|".join(
        f"{label}={_normalise(_resolve(transaction, path))}" for label, path in _FINGERPRINT_FIELDS
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _index(catalogue: TransactionCatalogue) -> dict[str, Transaction]:
    return {transaction.transaction_id: transaction for transaction in catalogue.values()}


def compute_ledger_filing_snapshot(
    *,
    source_transaction_ids: Iterable[str],
    catalogue: TransactionCatalogue,
    captured_at: datetime,
) -> LedgerFilingSnapshot:
    """Capture an immutable snapshot over a revision's contributing rows.

    Contributor ids absent from the catalogue are skipped (a snapshot records
    the rows that exist at capture time); an empty contributor set yields a
    valid empty snapshot, which is the uniform shape for non-ledger modelos.
    """
    index = _index(catalogue)
    rows = tuple(
        LedgerRowFingerprint(transaction_id=tx_id, fingerprint=row_fingerprint(index[tx_id]))
        for tx_id in sorted(set(source_transaction_ids))
        if tx_id in index
    )
    return LedgerFilingSnapshot(
        rows=rows,
        snapshot_fingerprint=snapshot_fingerprint(rows),
        captured_at=captured_at,
    )


def evaluate_ledger_filing_staleness(
    snapshot: LedgerFilingSnapshot,
    catalogue: TransactionCatalogue,
) -> LedgerFilingStalenessVerdict:
    """Compare a filed snapshot against the current ledger state."""
    index = _index(catalogue)
    current = {
        row.transaction_id: row_fingerprint(index[row.transaction_id])
        for row in snapshot.rows
        if row.transaction_id in index
    }
    return diff_ledger_fingerprints(snapshot, current)


__all__ = [
    "compute_ledger_filing_snapshot",
    "evaluate_ledger_filing_staleness",
    "row_fingerprint",
]
