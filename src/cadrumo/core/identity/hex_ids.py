"""Canonical content-addressed identity aliases backed by :data:`Hex64Str`."""

from __future__ import annotations

from ..hex import Hex64Str

__all__ = [
    "CalculationRevisionId",
    "FilingRecordId",
    "InvoiceId",
    "ModeloEditBaselineId",
    "ModeloEditMutationResultReceiptId",
    "SnapshotId",
    "VerificationReportId",
    "WorkUnitId",
]


type CalculationRevisionId = Hex64Str
"""Hex-64 identity of one calculation revision under a work unit."""

type FilingRecordId = Hex64Str
"""Hex-64 identity of one filing record bound to a calculation revision."""

type InvoiceId = Hex64Str
"""Hex-64 content-addressed invoice identity."""

type ModeloEditBaselineId = Hex64Str
"""Hex-64 identity of one admitted Modelo edit compare-and-swap baseline."""

type ModeloEditMutationResultReceiptId = Hex64Str
"""Hex-64 identity of one Modelo edit mutation result receipt."""

type SnapshotId = Hex64Str
"""Hex-64 content-addressed snapshot identity."""

type VerificationReportId = Hex64Str
"""Hex-64 identity of one verification report bound to a calculation revision."""

type WorkUnitId = Hex64Str
"""Hex-64 identity of one modelo work unit."""
