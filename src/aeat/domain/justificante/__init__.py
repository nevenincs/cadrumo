"""Public API for AEAT justificante domain records and errors.

Callers outside :mod:`aeat.domain.justificante` must import exclusively from this
module for domain records and errors. The parser pipeline lives in
:mod:`aeat.adapters.inbound.justificante`.

Live CSV verification lives in :mod:`aeat.adapters.outbound.aeat.verify`
(Playwright/browser automation belongs in the outbound adapter layer, not
the domain).

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import (
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteVerificationError,
)
from ._schema import Justificante, JustificanteParserBackend

if TYPE_CHECKING:
    from ._repository import JustificanteRepository

__all__ = [
    "Justificante",
    "JustificanteCsvNotFoundError",
    "JustificanteError",
    "JustificanteParseError",
    "JustificanteParserBackend",
    "JustificanteRepository",
    "JustificanteVerificationError",
]


def __getattr__(name: str) -> object:
    if name == "JustificanteRepository":
        from ._repository import JustificanteRepository

        return JustificanteRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
