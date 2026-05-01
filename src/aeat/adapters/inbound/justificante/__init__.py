"""Inbound parser adapter for AEAT justificante PDFs."""

from __future__ import annotations

from ....domain.justificante import (
    Justificante,
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteParserBackend,
    JustificanteVerificationError,
)
from ._parser import parse_justificante

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteVerificationError",
    "parse_justificante",
]
