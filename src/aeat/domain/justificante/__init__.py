"""Public facade for AEAT justificante receipt metadata.

Callers outside :mod:`aeat.domain.justificante` must import receipt-domain
types from this module. The facade re-exports the strict :class:`Justificante`
record, :class:`JustificanteParserBackend` parser contract,
:class:`JustificanteRepository` encrypted AUDIT store, and the
:class:`PdfModeloImportError` / :class:`JustificanteError` hierarchy used by
PDF filing-import flows.

The PDF parsing pipeline lives in :mod:`aeat.adapters.inbound.justificante`;
this module intentionally does not re-export parser entry points. Live CSV
verification lives in :mod:`aeat.adapters.outbound.aeat.verify`, because
Playwright/browser automation belongs in the outbound adapter layer, not the
domain.

"""

from __future__ import annotations

from ._errors import (
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteVerificationError,
    PdfModeloImportError,
)
from ._repository import (
    JustificanteRepository,
)
from ._schema import Justificante, JustificanteParserBackend

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteRepository",
    "JustificanteVerificationError",
    "PdfModeloImportError",
]
