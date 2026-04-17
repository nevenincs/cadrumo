"""Error hierarchy for the justificante parser (#44).

All errors inherit from :class:`aeat.errors.AeatError` so they compose with
the project-wide exception handling discipline.
"""

from __future__ import annotations

from ..errors import AeatError


class JustificanteError(AeatError):
    """Base class for every justificante-related failure."""


class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`."""


class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""


class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
