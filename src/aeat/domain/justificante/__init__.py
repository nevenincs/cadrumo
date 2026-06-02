"""Public API for AEAT justificante domain records and errors.

Callers outside :mod:`aeat.domain.justificante` must import exclusively from this
module for domain records and errors. The parser pipeline lives in
:mod:`aeat.adapters.inbound.justificante`.

Live CSV verification lives in :mod:`aeat.adapters.outbound.aeat.verify`
(Playwright/browser automation belongs in the outbound adapter layer, not
the domain).

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
