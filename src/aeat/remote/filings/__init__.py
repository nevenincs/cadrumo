"""Per-modelo read-only filing-detail record shapes (Tier 1).

Phase 1 only declares the record shapes; concrete fetchers land in
Phase 2. Every record wraps a :class:`aeat.remote.RemoteFiling` and
projects modelo-specific casilla totals into typed fields so downstream
consumers can access them without re-parsing the Spanish casilla
labels.

Tier-1 scope:

- :class:`FilingDetail130` — simplified IRPF prepayment (quarterly).
- :class:`FilingDetail303` — VAT return (quarterly).
- :class:`FilingDetail390` — VAT annual summary.

Tier-2 / Tier-3 modelos are out of scope for this phase per the
accepted ADR; additional files land here in follow-up PRs gated on the
corresponding history parser.
"""

from __future__ import annotations

from ._filing_detail_130 import FilingDetail130
from ._filing_detail_303 import FilingDetail303
from ._filing_detail_390 import FilingDetail390

__all__ = [
    "FilingDetail130",
    "FilingDetail303",
    "FilingDetail390",
]
