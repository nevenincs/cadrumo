"""Immutable ledger snapshot backing a modelo filing revision.

A modelo calculation revision that reaches a verified or filed state carries a
content-addressed snapshot of the ledger state it was computed from: a
fingerprint over each contributing transaction's tax-relevant facts plus an
aggregate snapshot fingerprint. This is the audit + staleness layer that sits
on top of the write-time blocking guard.

This module holds the pure records and the pure fingerprint diff. The
Transaction-aware capture (which reads the live catalogue to produce row
fingerprints) lives in the application aggregation layer so the domain stays
free of the ledger-read dependency, per the hexagonal boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import CasillaId
from ...core.country_code import CountryCodeAlpha2
from ...core.hashing import sha256_hex
from ...core.identity import SnapshotId, TransactionId
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.ids import LegalRefId, SourceRefId


class LedgerRowFingerprint(BaseModel):
    """Content fingerprint of one contributing ledger transaction.

    Attributes:
        transaction_id: The contributor's stable ledger transaction id.
        fingerprint: SHA-256 hex over the transaction's tax-relevant facts
            (the fields that can move a casilla), computed by the application
            capture helper.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    fingerprint: SnapshotId


class LedgerFilingSnapshot(BaseModel):
    """Immutable snapshot of the ledger state behind one filing revision.

    Empty ``rows`` is valid and expected for a non-ledger modelo (no
    contributing transactions); its ``snapshot_fingerprint`` is the digest of
    the empty contributor set, so every modelo carries a uniform, comparable
    snapshot regardless of whether it is ledger-fed.

    Attributes:
        rows: Per-contributor fingerprints, sorted by transaction id.
        snapshot_fingerprint: SHA-256 hex over the sorted ``(id, fingerprint)``
            pairs; the content address of the whole ledger state.
        captured_at: UTC timestamp the snapshot was taken.
    """

    model_config = _STRICT_FROZEN

    rows: tuple[LedgerRowFingerprint, ...] = ()
    snapshot_fingerprint: SnapshotId
    captured_at: datetime


class LedgerFilingStalenessVerdict(BaseModel):
    """Drift between a filed snapshot and the current ledger state.

    Attributes:
        is_stale: True when any contributor changed or was removed.
        changed: Contributor ids whose live fingerprint differs from the snapshot.
        removed: Contributor ids absent from the live catalogue.
        unchanged: Contributor ids whose live fingerprint matches the snapshot.
    """

    model_config = _STRICT_FROZEN

    is_stale: bool
    changed: tuple[TransactionId, ...] = ()
    removed: tuple[TransactionId, ...] = ()
    unchanged: tuple[TransactionId, ...] = ()


def snapshot_fingerprint(rows: tuple[LedgerRowFingerprint, ...]) -> SnapshotId:
    """Return the aggregate content address over sorted contributor fingerprints."""
    canonical = "\n".join(f"{row.transaction_id}={row.fingerprint}" for row in _sorted_rows(rows))
    return sha256_hex(canonical.encode("utf-8"))


def _sorted_rows(rows: tuple[LedgerRowFingerprint, ...]) -> tuple[LedgerRowFingerprint, ...]:
    return tuple(sorted(rows, key=lambda row: row.transaction_id))


def diff_ledger_fingerprints(
    snapshot: LedgerFilingSnapshot,
    current_fingerprints: Mapping[TransactionId, SnapshotId],
) -> LedgerFilingStalenessVerdict:
    """Compare a filed snapshot against live per-contributor fingerprints.

    ``current_fingerprints`` maps each contributor's transaction id to its
    freshly-recomputed fingerprint (a contributor missing from the mapping is
    treated as removed). Pure: no ledger read happens here.

    Returns:
        The computed :class:`LedgerFilingStalenessVerdict` detail.
    """
    changed: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []
    for row in snapshot.rows:
        live = current_fingerprints.get(row.transaction_id)
        if live is None:
            removed.append(row.transaction_id)
        elif live != row.fingerprint:
            changed.append(row.transaction_id)
        else:
            unchanged.append(row.transaction_id)
    return LedgerFilingStalenessVerdict(
        is_stale=bool(changed or removed),
        changed=tuple(sorted(changed)),
        removed=tuple(sorted(removed)),
        unchanged=tuple(sorted(unchanged)),
    )


class LedgerEvidenceRow(BaseModel):
    """Typed evidence projection of one contributing ledger transaction.

    Where :class:`LedgerRowFingerprint` records only the content hash (for
    staleness detection), this record carries the actual tax-relevant facts that
    moved a casilla, plus its regulatory grounding and evidence references, so the
    fact basis can be reconstituted from the revision and rendered into a filing
    artefact. ``fingerprint`` binds this row to the matching
    :class:`LedgerRowFingerprint`, so an evidence/fingerprint mismatch is
    detectable.

    Enum-valued facts are stored as their canonical string ``value`` (and dates as
    ISO-8601 strings) so the record roundtrips cleanly through the strict
    persistence boundary and the domain stays free of the ledger-read dependency;
    the application capture layer projects the typed ``Transaction`` into this
    primitive shape.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    fingerprint: SnapshotId
    booked_date: str = Field(min_length=1)
    value_date: str | None = None
    # Non-negative magnitude in the row's native currency; flow is carried by
    # ``direction``, never by the sign (the amount mirrors the already-absolute
    # ``value_in_eur`` projection).
    amount: Decimal
    currency: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    business_classification: str = Field(min_length=1)
    business_pct: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    iva_category: str | None = None
    category_id: str | None = None
    irpf_category: str | None = None
    source_jurisdiction: CountryCodeAlpha2 | None = None
    m210_official_tipo_renta_code: str | None = Field(default=None, min_length=2, max_length=2)
    m210_gross_income_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    m210_applicable_rate: UnitProportion | None = None
    m210_payer_mode: str | None = None
    m210_payer_id: str | None = None
    m210_asset_or_right_id: str | None = None
    counterparty_country: CountryCodeAlpha2 | None = None
    fx_rate: Decimal | None = None
    value_in_eur: Decimal | None = None
    lifecycle_state: str = Field(min_length=1)
    counterparty: str | None = None
    description: str = ""
    purchase_invoice_evidence_id: str | None = None
    # A row's reconciliation-catalogue Invoice foreign key, mirroring
    # Transaction.invoice_id. Carried alongside purchase_invoice_evidence_id,
    # not instead of it, for the same reason the two are separate evidence
    # axes on Transaction: a validated Invoice is a distinct, and stronger,
    # evidence class from a bare PurchaseInvoiceEvidence blob. Without this
    # field, a row credited only through a linked Invoice at verify time
    # would still read as evidence-less once bundled here, and the
    # export/local-filing gate (application/modelo/_ledger_evidence_gate.py)
    # would block a revision verify had just granted -- a regression proven
    # by test_modelo_303_verify_and_file_credit_a_linked_validated_invoice.
    invoice_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    document_link_ids: tuple[str, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @field_validator("amount", "value_in_eur")
    @classmethod
    def _reject_negative_magnitude(cls, value: Decimal | None) -> Decimal | None:
        """Reject a negative ``amount`` / ``value_in_eur``; both are magnitudes.

        Flow is carried by :attr:`direction`, never by the sign of the amount.
        The evidence row mirrors the already-absolute EUR projection so a
        reader never has to reconcile which field is signed.
        """
        if value is not None and value < Decimal("0"):
            raise ValueError("ledger evidence amount must be a non-negative magnitude; flow is carried by direction")
        return value


class ManualFactBasisEntry(BaseModel):
    """One operator-entered fact behind a revision that is not ledger-derived.

    Manual casilla inputs and binding overrides have no contributing ledger row;
    they are nonetheless part of the fact basis a filing artefact must explain.
    ``casilla_id`` is the canonical registry casilla id and ``value`` is the
    rendered canonical string of the operator-entered value.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: str = Field(min_length=1)
    kind: str = Field(default="casilla_input", min_length=1)
    note: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class LedgerFilingEvidence(BaseModel):
    """The bundled fact basis behind one ledger-derived filing revision.

    Pegged to the revision's :class:`LedgerFilingSnapshot` via
    ``snapshot_fingerprint`` so evidence and the staleness fingerprint share one
    content address. Empty ``rows`` + empty ``manual_entries`` is valid for a
    non-ledger, non-manual revision; a ledger-derived revision MUST carry one
    ``LedgerEvidenceRow`` per fingerprint contributor (the application capture
    asserts the sets match, so no contributor is silently dropped from the
    evidence).
    """

    model_config = _STRICT_FROZEN

    snapshot_fingerprint: SnapshotId
    rows: tuple[LedgerEvidenceRow, ...] = ()
    manual_entries: tuple[ManualFactBasisEntry, ...] = ()
    captured_at: datetime


__all__ = [
    "LedgerEvidenceRow",
    "LedgerFilingEvidence",
    "LedgerFilingSnapshot",
    "LedgerFilingStalenessVerdict",
    "LedgerRowFingerprint",
    "ManualFactBasisEntry",
    "diff_ledger_fingerprints",
    "snapshot_fingerprint",
]
