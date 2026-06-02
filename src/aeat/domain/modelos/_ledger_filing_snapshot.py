"""Immutable ledger snapshot backing a modelo filing revision.

A modelo calculation revision that reaches a verified or filed state carries a
content-addressed snapshot of the ledger state it was computed from: a
fingerprint over each contributing transaction's tax-relevant facts plus an
aggregate snapshot fingerprint. This is the audit + staleness layer that sits
on top of the write-time blocking guard (see the
``modelo-filing-ledger-snapshot`` ADR).

This module holds the pure records and the pure fingerprint diff. The
Transaction-aware capture (which reads the live catalogue to produce row
fingerprints) lives in the application aggregation layer so the domain stays
free of the ledger-read dependency, per the hexagonal boundary.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel, Field

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class LedgerRowFingerprint(BaseModel):
    """Content fingerprint of one contributing ledger transaction.

    Attributes:
        transaction_id: The contributor's stable ledger transaction id.
        fingerprint: SHA-256 hex over the transaction's tax-relevant facts
            (the fields that can move a casilla), computed by the application
            capture helper.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)


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
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
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
    changed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()


def snapshot_fingerprint(rows: tuple[LedgerRowFingerprint, ...]) -> str:
    """Return the aggregate content address over sorted contributor fingerprints."""
    canonical = "\n".join(f"{row.transaction_id}={row.fingerprint}" for row in _sorted_rows(rows))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sorted_rows(rows: tuple[LedgerRowFingerprint, ...]) -> tuple[LedgerRowFingerprint, ...]:
    return tuple(sorted(rows, key=lambda row: row.transaction_id))


def diff_ledger_fingerprints(
    snapshot: LedgerFilingSnapshot,
    current_fingerprints: Mapping[str, str],
) -> LedgerFilingStalenessVerdict:
    """Compare a filed snapshot against live per-contributor fingerprints.

    ``current_fingerprints`` maps each contributor's transaction id to its
    freshly-recomputed fingerprint (a contributor missing from the mapping is
    treated as removed). Pure: no ledger read happens here.
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


__all__ = [
    "LedgerFilingSnapshot",
    "LedgerFilingStalenessVerdict",
    "LedgerRowFingerprint",
    "diff_ledger_fingerprints",
    "snapshot_fingerprint",
]
