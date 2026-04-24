"""Read-only typed model of the post-auth AEAT Sede Electronica surface.

``aeat.remote`` owns the authoritative strict-pydantic records that
project AEAT's authenticated surface — expedientes, filings, casillas,
receipts, navigation catalogues — into a shape the rest of the project
can consume without re-parsing Spanish prose. Every record exported
from this subpackage is ``strict=True``, ``frozen=True``,
``extra="forbid"`` and carries a ``mode: Literal["read"] = "read"``
Layer 1 write-guard marker.

Consumers MUST import only from :mod:`aeat.remote`; leading-underscore
modules are private and free to change. No symbol exported here carries
a write-verb name (English or Spanish) and no record permits a
``mode`` value other than ``"read"``. Any future write surface must
live in a separate subpackage that goes through the audited submission
engine in :mod:`aeat.submission`; widening ``mode`` inside
``aeat.remote`` is categorically forbidden.

The Phase 1 surface declares domain records and typing Protocols only.
Phase 2 lands the concrete Playwright read paths that realise the
Protocols against live AEAT pages; Phase 3 lands the reconciliation
comparator that consumes these records. See the accepted
``aeat-verify`` ADR for the full five-layer write-guard rationale.
"""

from __future__ import annotations

from ._errors import RemoteFetchError, RemoteNavigationError, RemoteParseError
from ._protocols import NotificationReader, RemoteFilingFetcher
from ._schema import (
    RemoteCasilla,
    RemoteExpediente,
    RemoteFiling,
    RemoteFilingRef,
    RemoteNavigationGraph,
    RemoteNotification,
    RemoteReceipt,
)
from ._status import RemoteFilingStatus
from .filings import FilingDetail130, FilingDetail303, FilingDetail390

__all__ = [
    "FilingDetail130",
    "FilingDetail303",
    "FilingDetail390",
    "NotificationReader",
    "RemoteCasilla",
    "RemoteExpediente",
    "RemoteFetchError",
    "RemoteFiling",
    "RemoteFilingFetcher",
    "RemoteFilingRef",
    "RemoteFilingStatus",
    "RemoteNavigationError",
    "RemoteNavigationGraph",
    "RemoteNotification",
    "RemoteParseError",
    "RemoteReceipt",
]
