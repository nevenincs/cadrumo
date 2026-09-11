"""Compatibility surface for the identity package.

Identity definitions live in focused public modules. The imports below remain
only for still-live cross-lane consumers; all other identity consumers import
their canonical defining module directly.
"""

from __future__ import annotations

# Temporary cross-lane bridges. Each name is still imported by the listed
# reserved consumer and must remain here until that owning lane moves it:
#   ContinuidadId -> continuidad: dev/registry/aeip (LANE-1)
#   CalculationRevisionId -> hex_ids: dev/registry/filing_export_proof_contracts (LANE-1)
#   SnapshotId, WorkUnitId -> hex_ids: application/aggregation/source_mesh (LANE-3)
#   InvoiceId, TransactionId -> hex_ids/transaction_ids: application/aggregation (LANE-3)
#   TransactionId, TransactionIdReference -> transaction_ids: application/ledger/tests (LANE-2)
#   InvoiceId, TransactionId -> hex_ids/transaction_ids: entrypoints/tui (LANE-2)
from .continuidad import ContinuidadId
from .hex_ids import CalculationRevisionId, InvoiceId, SnapshotId, WorkUnitId
from .transaction_ids import TransactionId, TransactionIdReference

__all__ = [
    "CalculationRevisionId",
    "ContinuidadId",
    "InvoiceId",
    "SnapshotId",
    "TransactionId",
    "TransactionIdReference",
    "WorkUnitId",
]
