"""Public API for AEAT justificante domain records and errors (#44).

Callers outside :mod:`aeat.domain.justificante` must import exclusively from this
module for domain records and errors. The parser pipeline lives in
:mod:`aeat.adapters.inbound.justificante`.

Live CSV verification lives in :mod:`aeat.adapters.outbound.aeat.verify`
(Playwright/browser automation belongs in the outbound adapter layer, not
the domain).

Example:
    >>> from pathlib import Path
    >>> from aeat.adapters.inbound.justificante import parse_justificante
    >>> record = parse_justificante(Path("tests/fixtures/justificantes/modelo_130_2026Q1.pdf"))
    >>> record.modelo
    '130'
"""

from __future__ import annotations

from ._errors import (
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteVerificationError,
)
from ._repository import (
    JustificanteMigrationSummary,
    JustificanteRepository,
    migrate_legacy_justificantes_to_repository,
)
from ._schema import Justificante, JustificanteParserBackend

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteMigrationSummary",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteRepository",
    "JustificanteVerificationError",
    "migrate_legacy_justificantes_to_repository",
]
