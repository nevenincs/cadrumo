"""Capture and staleness for the modelo filing ledger snapshot.

Used by: :mod:`application.modelo._ledger_drift_gate` for the calculate-time
staleness refusal, :mod:`entrypoints.cli._ledger_read_cli` for the stale-revision
listing, and :mod:`application.modelo._verification_actions` for the Modelo 303
deductible-evidence verify gate.

That list names the callers as they stand and is not a guarantee that no other
site reaches these functions; grep before relying on it. It previously named two
modules that call nothing here at all, which is worse than naming none: a reader
auditing the staleness refusal went looking in the wrong package, found nothing,
and had every reason to conclude the enforcement did not exist.

The pure records live in :mod:`domain.modelos._ledger_filing_snapshot`.
This application module holds the Transaction-aware halves:
computing a contributor's content fingerprint from the live
:class:`~domain.transactions.TransactionCatalogue`, building a
:class:`~domain.modelos._ledger_filing_snapshot.LedgerFilingSnapshot` for a
:class:`~domain.modelos.calculation_revision.CalculationRevision`'s ``source_transaction_ids``,
and evaluating drift between a filed snapshot and the current ledger state.

The fingerprint covers exactly the transaction facts that can move a casilla --
dates, amount magnitude, currency, direction, business classification and
proportionality, the IVA base/rate/amount/category, the spending and IRPF
categories, the M210 source-jurisdiction/classification facts, the EU member
state, the FX conversion, and the lifecycle state.
Cosmetic fields (description, counterparty, notes) are deliberately excluded so
staleness fires on material change, not on a relabel.

This module uses
:class:`~domain.modelos._ledger_filing_snapshot.LedgerFilingStalenessVerdict`
for drift evaluation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime

from pydantic import TypeAdapter, ValidationError

from ...core import CasillaId
from ...core.hashing import sha256_hex
from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
from ...domain.modelos import (
    LedgerEvidenceRow,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    LedgerFilingStalenessVerdict,
    LedgerRowFingerprint,
    ManualFactBasisEntry,
    diff_ledger_fingerprints,
    snapshot_fingerprint,
)
from ...domain.modelos.calculation_revision import SEALED_REVISION_STATES, CalculationRevision
from ...domain.modelos.errors import ModeloValidationError
from ...domain.transactions.models import Transaction, TransactionCatalogue

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
    ("source_jurisdiction", "source_jurisdiction"),
    ("m210_official_tipo_renta_code", "m210_income_classification.official_tipo_renta_code"),
    ("m210_gross_income_amount", "m210_income_classification.gross_income_amount"),
    ("m210_applicable_rate", "m210_income_classification.applicable_rate"),
    ("m210_payer_mode", "m210_income_classification.payer_mode"),
    ("m210_payer_id", "m210_income_classification.payer_id"),
    ("m210_asset_or_right_id", "m210_income_classification.asset_or_right_id"),
    ("counterparty_country", "counterparty_country"),
    ("fx_rate", "fx_rate"),
    ("value_in_eur", "value_in_eur"),
    ("lifecycle_state", "lifecycle_state"),
)
_LEGAL_REFS_ADAPTER = TypeAdapter(tuple[LegalRefId, ...])
_SOURCE_REFS_ADAPTER = TypeAdapter(tuple[SourceRefId, ...])


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
        if target is None:
            return None
        target = getattr(target, attr)
    return target


def row_fingerprint(transaction: Transaction) -> str:
    """Return the SHA-256 content fingerprint of one transaction's tax facts."""
    canonical = "|".join(f"{label}={_normalise(_resolve(transaction, path))}" for label, path in _FINGERPRINT_FIELDS)
    return sha256_hex(canonical.encode("utf-8"))


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


def _normalised_ref_values(refs: Iterable[object], *, field_name: str) -> tuple[str, ...]:
    normalised: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        value = str(ref).strip()
        if not value:
            raise ModeloValidationError(f"ledger filing evidence requires non-empty {field_name}")
        if value not in seen:
            normalised.append(value)
            seen.add(value)
    if not normalised:
        raise ModeloValidationError(f"ledger filing evidence requires non-empty {field_name}")
    return tuple(normalised)


def _normalised_legal_refs(refs: Iterable[LegalRefId], *, field_name: str) -> tuple[LegalRefId, ...]:
    normalised = _normalised_ref_values(refs, field_name=field_name)
    try:
        return _LEGAL_REFS_ADAPTER.validate_python(normalised)
    except ValidationError as exc:
        raise ModeloValidationError(f"ledger filing evidence has invalid {field_name}") from exc


def _normalised_source_refs(refs: Iterable[SourceRefId], *, field_name: str) -> tuple[SourceRefId, ...]:
    normalised = _normalised_ref_values(refs, field_name=field_name)
    try:
        return _SOURCE_REFS_ADAPTER.validate_python(normalised)
    except ValidationError as exc:
        raise ModeloValidationError(f"ledger filing evidence has invalid {field_name}") from exc


def _evidence_row(
    transaction: Transaction,
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> LedgerEvidenceRow:
    """Project a typed transaction into a primitive evidence row.

    Carries the same tax-relevant facts the fingerprint covers (so evidence and
    fingerprint stay consistent) plus the readability + attachment references a
    filing artefact needs. Enum members are stored as their ``value``; dates as
    ISO-8601 strings.
    """
    raw = transaction.raw
    m210_classification = transaction.m210_income_classification
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
        source_jurisdiction=transaction.source_jurisdiction,
        m210_official_tipo_renta_code=(
            m210_classification.official_tipo_renta_code if m210_classification is not None else None
        ),
        m210_gross_income_amount=(m210_classification.gross_income_amount if m210_classification is not None else None),
        m210_applicable_rate=(m210_classification.applicable_rate if m210_classification is not None else None),
        m210_payer_mode=(_enum_value(m210_classification.payer_mode) if m210_classification is not None else None),
        m210_payer_id=m210_classification.payer_id if m210_classification is not None else None,
        m210_asset_or_right_id=(m210_classification.asset_or_right_id if m210_classification is not None else None),
        counterparty_country=transaction.counterparty_country,
        fx_rate=transaction.fx_rate,
        value_in_eur=transaction.value_in_eur,
        lifecycle_state=transaction.lifecycle_state.value,
        counterparty=raw.counterparty,
        description=raw.description,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        invoice_id=transaction.invoice_id,
        attachment_ids=transaction.attachment_ids,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def compute_ledger_filing_evidence(
    *,
    source_transaction_ids: Iterable[str],
    catalogue: TransactionCatalogue,
    snapshot_fingerprint: str,
    captured_at: datetime,
    legal_refs: Iterable[LegalRefId],
    source_refs: Iterable[SourceRefId],
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
        legal_refs: Registry legal references grounding this evidence bundle.
        source_refs: Official source references grounding this evidence bundle.
        manual_entries: The manual entries basis.
    """
    index = _index(catalogue)
    source_ids = tuple(sorted(set(source_transaction_ids)))
    evidence_legal_refs = _normalised_legal_refs(legal_refs, field_name="legal_refs") if source_ids else ()
    evidence_source_refs = _normalised_source_refs(source_refs, field_name="source_refs") if source_ids else ()
    rows = tuple(
        _evidence_row(
            index[tx_id],
            legal_refs=evidence_legal_refs,
            source_refs=evidence_source_refs,
        )
        for tx_id in source_ids
        if tx_id in index
    )
    return LedgerFilingEvidence(
        snapshot_fingerprint=snapshot_fingerprint,
        rows=rows,
        manual_entries=manual_entries,
        captured_at=captured_at,
    )


def project_manual_fact_basis_entries(
    input_values_by_casilla_id: Mapping[CasillaId, str],
    *,
    legal_refs_by_casilla_id: Mapping[CasillaId, Iterable[LegalRefId]],
    source_refs_by_casilla_id: Mapping[CasillaId, Iterable[SourceRefId]],
) -> tuple[ManualFactBasisEntry, ...]:
    """Project operator-entered casilla inputs into :class:`ManualFactBasisEntry` entries.

    The calculation revision stores caller-supplied casilla inputs as rendered
    strings. Non-empty values are part of the evidence bundle because no ledger
    row explains them.
    """
    return tuple(
        ManualFactBasisEntry(
            casilla_id=casilla,
            value=value,
            legal_refs=_normalised_legal_refs(
                legal_refs_by_casilla_id.get(casilla, ()),
                field_name=f"legal_refs for manual fact {casilla}",
            ),
            source_refs=_normalised_source_refs(
                source_refs_by_casilla_id.get(casilla, ()),
                field_name=f"source_refs for manual fact {casilla}",
            ),
        )
        for casilla, value in sorted(input_values_by_casilla_id.items())
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
    live catalogue. A revision with no snapshot or a non-finalized
    state is skipped. Pure given its inputs.

    Args:
        revisions: A mapping of :class:`CalculationRevision` files.
        catalogue: The live :class:`TransactionCatalogue`.
    """
    findings: list[tuple[CalculationRevision, LedgerFilingStalenessVerdict]] = []
    for revision in revisions.values():
        if revision.state not in SEALED_REVISION_STATES or revision.ledger_filing_snapshot is None:
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
