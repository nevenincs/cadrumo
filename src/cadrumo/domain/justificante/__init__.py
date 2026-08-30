"""Public facade for AEAT justificante receipt metadata.

Callers outside :mod:`domain.justificante` must import receipt-domain
types from this module. The facade re-exports the strict :class:`Justificante`
record, :class:`JustificanteParserBackend` parser contract, and the
:class:`PdfModeloImportError` / :class:`JustificanteError` hierarchy used by
PDF filing-import flows. The encrypted AUDIT store lives in the persistence
adapter as
:class:`~cadrumo.adapters.persistence.profile.justificante.JustificanteRepository`.

This package is scoped to the AEAT *justificante de presentación* receipt:
CSV, modelo, period, presentation timestamp, taxpayer id, totals, source path,
and source hash. A justificante is official submission evidence, but it is not a
filing copy and it does not carry per-casilla values. Application import paths
may compose a :class:`Justificante` into a draft scaffold, a local
:class:`domain.submission.ModeloPresentado` audit baseline, or a
:class:`~ExternalEvidence` reference, but casilla-complete
declaración, borrador, and predeclaración parsing belongs to their own inbound
adapter surfaces.

The PDF parsing pipeline lives in :mod:`adapters.inbound.justificante`;
this module intentionally does not re-export parser entry points. Live CSV
verification lives in :mod:`adapters.outbound.aeat.verify`, because
Playwright/browser automation belongs in the outbound adapter layer, not the
domain.

See Also:
    :func:`application.filing.import_filing_from_justificante`
        Application import path that composes receipt metadata into local draft
        and submission-audit records without treating it as casilla authority.
    :mod:`application.live`
        Read-only live-capture surface that can persist and verify justificante
        evidence against existing filing records.
    :func:`application.live.register_capture_as_filing_evidence`
        Live-capture path that parses a persisted receipt snapshot into
        :class:`Justificante` metadata before stamping matching local filing
        evidence.
    :func:`application.modelo.import_external_filing_evidence`
        Modelo work-unit import path that requires matching
        :class:`~cadrumo.adapters.persistence.profile.justificante.JustificanteRepository`
        metadata for receipt-bound evidence kinds.
    :mod:`domain.submission`
        Local-only :class:`domain.submission.ModeloPresentado` audit trail
        populated by imported or historical receipt evidence.
    :class:`~ExternalEvidence`
        Work-unit filing-record evidence reference that may point at a persisted
        justificante without embedding receipt bytes in the model record.
    :mod:`adapters.inbound.justificante`
        PDF parser implementation kept outside the domain facade.
"""

from __future__ import annotations

from ._protocols import JustificanteRepositoryProtocol
from ._schema import Justificante, JustificanteParserBackend
from .errors import (
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteVerificationError,
    PdfExtractionCoverageMixin,
    PdfModeloImportError,
)

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteRepositoryProtocol",
    "JustificanteVerificationError",
    "PdfExtractionCoverageMixin",
    "PdfModeloImportError",
]
