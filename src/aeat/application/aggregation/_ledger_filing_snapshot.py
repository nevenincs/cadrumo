"""Capture and staleness for the modelo filing ledger snapshot.

Used by: :mod:`aeat.application.modelo._work_lifecycle` for revision staleness checks,
:mod:`aeat.application.evidence` for audit bundle generation.

The pure records live in :mod:`aeat.domain.modelos._ledger_filing_snapshot`.
This application module holds the Transaction-aware halves:
computing a contributor's content fingerprint from the live
:class:`~aeat.domain.transactions.TransactionCatalogue`, building a
:class:`~aeat.domain.modelos._ledger_filing_snapshot.LedgerFilingSnapshot` for a
:class:`~aeat.domain.calculations.registry.CalculationRevision`'s ``source_transaction_ids``,
and evaluating drift between a filed snapshot and the current ledger state.

The fingerprint covers exactly the transaction facts that can move a casilla --
dates, signed amount, currency, direction, business classification and
proportionality, the IVA base/rate/amount/category, the spending and IRPF
categories, the EU member state, the FX conversion, and the lifecycle state.
Cosmetic fields (description, counterparty, notes) are deliberately excluded so
staleness fires on material change, not on a relabel.

This module uses
:class:`~aeat.domain.modelos._ledger_filing_snapshot.LedgerFilingStalenessVerdict`
for drift evaluation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import date, datetime

from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._errors import ModeloValidationError
from ...domain.modelos._ledger_filing_snapshot import (
    LedgerEvidenceRow,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    LedgerFilingStalenessVerdict,
    LedgerRowFingerprint,
    ManualFactBasisEntry,
    diff_ledger_fingerprints,
    snapshot_fingerprint,
)
from ...domain.transactions import Transaction, TransactionCatalogue

# Finalized revision states whose ledger snapshot, once captured, must stay in
# sync with the live ledger; drift in any of these is operator-actionable.
_FINALIZED_STATES = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    },
)

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
    canonical = "|".join(f"{label}={_normalise(_resolve(transaction, path))}" for label, path in _FINGERPRINT_FIELDS)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _index(catalogue: TransactionCatalogue) -> dict[str, Transaction]:
    return {transaction.transaction_id: transaction for transaction in catalogue.values()}


def compute_ledger_filing_snapshot(
    *,
    source_transaction_ids: Iterable[str],
    catalogue: TransactionCatalogue,
    captured_at: datetime,
) -> LedgerFilingSnapshot:
    """Capture an immutable :class:`LedgerFilingSnapshot` over a revision's contributing rows.

    Contributor ids absent from the catalogue are skipped (a snapshot records
    the rows that exist at capture time); an empty contributor set yields a
    valid empty snapshot, which is the uniform shape for non-ledger modelos.

    Args:
        source_transaction_ids: Contributor identifiers.
        catalogue: The live :class:`TransactionCatalogue`.
        captured_at: Captured timestamp.
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


def _enum_value(value: object) -> str | None:
    """Return an enum member's canonical string value, or None."""
    if value is None:
        return None
    inner = getattr(value, "value", None)
    return inner if isinstance(inner, str) else str(value)


def _evidence_row(transaction: Transaction) -> LedgerEvidenceRow:
    """Project a typed transaction into a primitive evidence row.

    Carries the same tax-relevant facts the fingerprint covers (so evidence and
    fingerprint stay consistent) plus the readability + attachment references a
    filing artefact needs. Enum members are stored as their ``value``; dates as
    ISO-8601 strings.
    """
    raw = transaction.raw
    return LedgerEvidenceRow(
        transaction_id=transaction.transaction_id,
        fingerprint=row_fingerprint(transaction),
        booked_date=raw.booked_date.isoformat(),
        value_date=raw.value_date.isoformat() if raw.value_date is not None else None,
        amount=raw.amount,
        currency=raw.currency,
        direction=transaction.direction.value,
        business_classification=transaction.business_classification.value,
        business_pct=transaction.business_pct,
        taxable_base=transaction.taxable_base,
        iva_rate=transaction.iva_rate,
        iva_amount=transaction.iva_amount,
        iva_category=_enum_value(transaction.iva_category),
        category_id=transaction.category_id,
        irpf_category=transaction.irpf_category,
        counterparty_eu_member_state=_enum_value(transaction.counterparty_eu_member_state),
        fx_rate=transaction.fx_rate,
        value_in_eur=transaction.value_in_eur,
        lifecycle_state=transaction.lifecycle_state.value,
        counterparty=raw.counterparty,
        description=raw.description,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        attachment_ids=transaction.attachment_ids,
    )


def compute_ledger_filing_evidence(
    *,
    source_transaction_ids: Iterable[str],
    catalogue: TransactionCatalogue,
    snapshot_fingerprint: str,
    captured_at: datetime,
    manual_entries: tuple[ManualFactBasisEntry, ...] = (),
) -> LedgerFilingEvidence:
    """Capture the bundled :class:`LedgerFilingEvidence` fact basis behind one filing revision.

    Projects every contributor in ``source_transaction_ids`` present in the
    catalogue into a typed :class:`LedgerEvidenceRow`, binding the bundle to the
    revision's ``snapshot_fingerprint``. ``manual_entries`` carries the
    operator-entered fact basis (casilla inputs / binding overrides) that has no
    contributing ledger row. Contributor ids absent from the catalogue are
    skipped (mirroring :func:`compute_ledger_filing_snapshot`); the caller's
    no-silent-omission guard cross-checks the evidence set against the fingerprint
    set.

    Args:
        source_transaction_ids: Contributor identifiers.
        catalogue: The live :class:`TransactionCatalogue`.
        snapshot_fingerprint: The fingerprinted snapshot identifier.
        captured_at: Captured timestamp.
        manual_entries: The manual entries basis.
    """
    index = _index(catalogue)
    rows = tuple(_evidence_row(index[tx_id]) for tx_id in sorted(set(source_transaction_ids)) if tx_id in index)
    return LedgerFilingEvidence(
        snapshot_fingerprint=snapshot_fingerprint,
        rows=rows,
        manual_entries=manual_entries,
        captured_at=captured_at,
    )


def project_manual_fact_basis_entries(inputs_snapshot: Mapping[str, str]) -> tuple[ManualFactBasisEntry, ...]:
    """Project operator-entered casilla inputs into :class:`ManualFactBasisEntry` entries.

    The calculation revision stores caller-supplied casilla inputs as rendered
    strings. Non-empty values are part of the evidence bundle because no ledger
    row explains them.
    """
    return tuple(
        ManualFactBasisEntry(casilla=casilla, value=value)
        for casilla, value in sorted(inputs_snapshot.items())
        if value.strip()
    )


def assert_evidence_covers_snapshot(snapshot: LedgerFilingSnapshot, evidence: LedgerFilingEvidence) -> None:
    """Raise when bundled evidence omits or invents fingerprinted contributors."""
    snapshot_ids = {row.transaction_id for row in snapshot.rows}
    evidence_ids = {row.transaction_id for row in evidence.rows}
    if snapshot_ids != evidence_ids:
        missing = sorted(snapshot_ids - evidence_ids)
        extra = sorted(evidence_ids - snapshot_ids)
        raise ModeloValidationError(
            f"ledger filing evidence does not cover the fingerprint snapshot: missing={missing} extra={extra}",
        )


def evaluate_ledger_filing_staleness(
    snapshot: LedgerFilingSnapshot,
    catalogue: TransactionCatalogue,
) -> LedgerFilingStalenessVerdict:
    """Compare a filed snapshot against the current ledger state, returning a :class:`LedgerFilingStalenessVerdict`.

    Args:
        snapshot: The filed ledger snapshot.
        catalogue: The live :class:`TransactionCatalogue`.
    """
    index = _index(catalogue)
    current = {
        row.transaction_id: row_fingerprint(index[row.transaction_id])
        for row in snapshot.rows
        if row.transaction_id in index
    }
    return diff_ledger_fingerprints(snapshot, current)


def stale_filed_revisions(
    *,
    revisions: Mapping[str, CalculationRevision],
    catalogue: TransactionCatalogue,
) -> tuple[tuple[CalculationRevision, LedgerFilingStalenessVerdict], ...]:
    """Return finalized snapshot-backed revisions whose ledger drifted.

    Each item pairs a :class:`CalculationRevision` with its
    :class:`LedgerFilingStalenessVerdict`. Scans verified/filed revisions
    carrying a ``ledger_filing_snapshot`` and re-evaluates each against the
    live catalogue. A revision with no snapshot (legacy) or a non-finalized
    state is skipped. Pure given its inputs.

    Args:
        revisions: A mapping of :class:`CalculationRevision` files.
        catalogue: The live :class:`TransactionCatalogue`.
    """
    findings: list[tuple[CalculationRevision, LedgerFilingStalenessVerdict]] = []
    for revision in revisions.values():
        if revision.state not in _FINALIZED_STATES or revision.ledger_filing_snapshot is None:
            continue
        verdict = evaluate_ledger_filing_staleness(revision.ledger_filing_snapshot, catalogue)
        if verdict.is_stale:
            findings.append((revision, verdict))
    return tuple(findings)


__all__ = [
    "assert_evidence_covers_snapshot",
    "compute_ledger_filing_evidence",
    "compute_ledger_filing_snapshot",
    "evaluate_ledger_filing_staleness",
    "project_manual_fact_basis_entries",
    "row_fingerprint",
    "stale_filed_revisions",
]
