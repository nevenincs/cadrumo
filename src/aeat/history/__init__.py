"""AEAT filing-history read surface (#168).

Strictly read-only subpackage that, given the list of
:class:`aeat.status.Expediente` rows, fetches each filing's detail
page, parses the casilla→value mapping, and persists the result as
strict pydantic v2 records. This layer is the foundation for the
double-entry verification engine tracked under EPIC #166.

The fetcher **never** writes to AEAT. See
[[2026-04-16-aeat-history-fetch-adr]] decisions D1 (read-only),
D10 (non-goals), and the live-AEAT-write safety charter (#116).

Non-goals (v1):

- No verification logic — this package *produces* ``FiledModelo``;
  the verification engine consumes it.
- No writes, no form submissions, no rectifying filings.
- No PDF-duplicate parsing — HTML detail surface only.
- No typed casilla coercion — values are strings keyed by
  ``casilla_id``. The verification engine coerces via
  :class:`aeat.casillas.CasillaRecord.data_type`.
- No sqlite / storage-layer wiring — single JSON file under
  ``AEAT_FILING_HISTORY_DIR``.

Public API: callers outside this subpackage must import exclusively
from :mod:`aeat.history`. The underscored submodules are
implementation detail and may change without notice.

Example:
    >>> from aeat.history import HistoryFetcher, HistoryModelo
    >>> # Build fetcher from injected Protocol-conforming collaborators.
    >>> fetcher = HistoryFetcher(
    ...     expediente_source=source,
    ...     detail_fetcher=detail,
    ...     settings=settings,
    ... )
    >>> records = await fetcher.fetch_for_modelo(HistoryModelo.MODELO_303)
"""

from __future__ import annotations

from ._errors import (
    HistoryError,
    HistoryFetchError,
    HistoryParseError,
    HistoryUnsupportedModeloError,
)
from ._fetcher import HistoryFetcher
from ._models import (
    FiledModelo,
    FiledModeloMetadata,
    FilingHistory,
    HistoryModelo,
    RawCalculationPayload,
)
from ._protocols import CertificateBackend, ExpedienteSource, FilingDetailFetcher

__all__ = [
    "CertificateBackend",
    "ExpedienteSource",
    "FiledModelo",
    "FiledModeloMetadata",
    "FilingDetailFetcher",
    "FilingHistory",
    "HistoryError",
    "HistoryFetchError",
    "HistoryFetcher",
    "HistoryModelo",
    "HistoryParseError",
    "HistoryUnsupportedModeloError",
    "RawCalculationPayload",
]
