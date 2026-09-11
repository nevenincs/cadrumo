"""Domain-facing persistence port for parsed AEAT receipt metadata."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from .schema import Justificante


@runtime_checkable
class JustificanteRepositoryProtocol(Protocol):
    """Read/write surface used by application receipt-evidence workflows.

    The encrypted implementation lives in
    :mod:`cadrumo.adapters.persistence.profile.justificante`; this port keeps
    application and domain code independent of that storage adapter.
    """

    def load(self, csv: str, /) -> Justificante | None:
        """Return the persisted receipt identified by its AEAT CSV."""
        ...

    def save(self, justificante: Justificante, /) -> None:
        """Persist one parsed receipt metadata record."""
        ...

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted receipt in deterministic CSV order."""
        ...


__all__ = ["JustificanteRepositoryProtocol"]
