"""Public API for the AEAT justificante (PDF receipt) parser (#44).

Callers outside :mod:`aeat.justificante` must import exclusively from this
module — the private ``_schema``, ``_extract``, ``_parser``, ``_verify``,
and ``_parsers`` modules are implementation details and may change without
notice.

Example:
    >>> from pathlib import Path
    >>> from aeat.justificante import parse_justificante
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
from ._parser import parse_justificante
from ._schema import Justificante, JustificanteParserBackend
from ._verify import verify_csv

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteVerificationError",
    "parse_justificante",
    "verify_csv",
]
