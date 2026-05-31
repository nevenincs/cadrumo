"""Narrow Protocol surface for justificante repository consumers.

The justificante repository is backed by an encrypted SQL object store;
this Protocol captures only the surface domain service code consumes,
decoupling callers from the concrete ``SecureBoundRepository`` base class
and its adapter-layer imports.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from ._schema import Justificante


@runtime_checkable
class JustificanteRepositoryProtocol(Protocol):
    """Narrow domain-facing contract for the justificante repository."""

    def load(self, record_id: str) -> Justificante | None:
        """Load a persisted justificante by CSV identifier, or return ``None``."""
        ...

    def save(self, payload: Justificante) -> None:
        """Persist ``payload`` in the encrypted object store."""
        ...

    def list_csvs(self) -> tuple[str, ...]:
        """Return every justificante CSV persisted in this repository."""
        ...

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted justificante in lexicographic CSV order."""
        ...


__all__ = [
    "JustificanteRepositoryProtocol",
]
