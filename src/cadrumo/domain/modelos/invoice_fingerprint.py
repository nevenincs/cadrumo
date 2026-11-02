"""Pure records for the invoice state a calculation revision was computed from.

An invoice is read live on every calculation and nothing else pins what it said,
so a catalogue edit leaves a stored draft's figures unexplained. These records
hold only invoice ids, which are already content digests, and row digests: no
figure, counterparty or tax id is stored beside the revision.

The capture and the field set live in
:mod:`application.aggregation.invoice_filing_fingerprint`.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core.hashing import sha256_hex
from ...core.identity.hex_ids import InvoiceId, SnapshotId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.utc import UtcInstant


class InvoiceRowFingerprint(BaseModel):
    """The digest of one in-scope invoice's calculation facts."""

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    fingerprint: SnapshotId


class InvoiceFingerprintSnapshot(BaseModel):
    """The invoices a revision's modelo and period read when it was calculated.

    Empty ``rows`` is a real statement for a modelo that reads invoices: none were
    in scope, so the first one recorded later is an addition. A revision whose
    field is ``None`` was calculated before fingerprints existed and proves nothing
    either way.

    Attributes:
        rows: Per-invoice digests, sorted by invoice id.
        snapshot_fingerprint: SHA-256 hex over the sorted pairs.
        captured_at: UTC timestamp of the capture.
        field_set_version: Which invoice facts the digests cover; a stored digest
            is only comparable under its own version.
    """

    model_config = _STRICT_FROZEN

    rows: tuple[InvoiceRowFingerprint, ...] = ()
    snapshot_fingerprint: SnapshotId
    captured_at: UtcInstant
    field_set_version: int


class InvoiceFingerprintVerdict(BaseModel):
    """How a stored invoice fingerprint compares with the catalogue now."""

    model_config = _STRICT_FROZEN

    changed: tuple[InvoiceId, ...] = ()
    removed: tuple[InvoiceId, ...] = ()
    added: tuple[InvoiceId, ...] = ()

    @property
    def is_stale(self) -> bool:
        """Whether any in-scope invoice changed, left the scope or entered it."""
        return bool(self.changed or self.removed or self.added)


def invoice_snapshot_fingerprint(rows: tuple[InvoiceRowFingerprint, ...]) -> SnapshotId:
    """Return the order-independent content address over the row digests."""
    canonical = "\n".join(f"{row.invoice_id}={row.fingerprint}" for row in sorted(rows, key=lambda row: row.invoice_id))
    return sha256_hex(canonical.encode("utf-8"))


def diff_invoice_fingerprints(
    snapshot: InvoiceFingerprintSnapshot,
    current: Mapping[InvoiceId, SnapshotId],
) -> InvoiceFingerprintVerdict:
    """Compare stored row digests with digests recomputed under the same version."""
    recorded = {row.invoice_id: row.fingerprint for row in snapshot.rows}
    return InvoiceFingerprintVerdict(
        changed=tuple(
            sorted(
                invoice_id
                for invoice_id, fingerprint in recorded.items()
                if invoice_id in current and current[invoice_id] != fingerprint
            )
        ),
        removed=tuple(sorted(recorded.keys() - current.keys())),
        added=tuple(sorted(current.keys() - recorded.keys())),
    )


__all__ = [
    "InvoiceFingerprintSnapshot",
    "InvoiceFingerprintVerdict",
    "InvoiceRowFingerprint",
    "diff_invoice_fingerprints",
    "invoice_snapshot_fingerprint",
]
