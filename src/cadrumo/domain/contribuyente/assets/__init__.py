"""Asset ledger records for actividad economica amortizacion tracking.

Provides the strict, frozen pydantic v2 records that back the
registry-backed amortizacion workflow:
:class:`AssetRecord` (a depreciable asset affected to an economic
activity), :class:`AmortizacionLedger` (the recorded per-asset / per-
year accruals), and :class:`LibertadAmortizacionElection`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
