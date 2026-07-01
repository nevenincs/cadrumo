"""Public facade for AEAT justificante receipt metadata.

Callers outside :mod:`aeat.domain.justificante` must import receipt-domain
types from this module. The facade re-exports the strict :class:`Justificante`
record, :class:`JustificanteParserBackend` parser contract,
:class:`JustificanteRepository` encrypted AUDIT store, and the
:class:`PdfModeloImportError` / :class:`JustificanteError` hierarchy used by
PDF filing-import flows.

This package is scoped to the AEAT *justificante de presentación* receipt:
CSV, modelo, period, presentation timestamp, taxpayer id, totals, source path,
and source hash. A justificante is official submission evidence, but it is not a
filing copy and it does not carry per-casilla values. Application import paths
may compose a :class:`Justificante` into a draft scaffold, a local
:class:`aeat.domain.submission.ModeloPresentado` audit baseline, or a
:class:`aeat.domain.modelos.ExternalEvidence` reference, but casilla-complete
declaración, borrador, and predeclaración parsing belongs to their own inbound
adapter surfaces.

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
