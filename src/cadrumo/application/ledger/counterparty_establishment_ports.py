"""Application-owned persistence capability for counterparty facts.

The establishment policy owns the fact DTO and its conflict/resolution rules.
Encrypted storage is supplied by an outer composition root through this narrow
protocol; storage-specific failures are translated by the adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .counterparty_establishment import ConfirmedCounterpartyFacts


class CounterpartyEstablishmentPersistenceError(RuntimeError):
    """Translated failure from the counterparty-establishment store."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"counterparty establishment persistence operation failed: {operation}")


class CounterpartyEstablishmentRepositoryProtocol(Protocol):
    """Required bucket-bound operations for remembered counterparty facts."""

    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        """Load one remembered fact, or return None when absent."""
        ...

    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        """Persist one validated remembered fact."""
        ...

    def delete(self, identifier: str) -> bool:
        """Delete one remembered fact and report whether it existed."""
        ...


class CounterpartyEstablishmentRepositoryFactory(Protocol):
    """Construct the persistence capability for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> CounterpartyEstablishmentRepositoryProtocol:
        """Return the capability bound to bucket_id."""
        ...


__all__ = [
    "CounterpartyEstablishmentPersistenceError",
    "CounterpartyEstablishmentRepositoryFactory",
    "CounterpartyEstablishmentRepositoryProtocol",
]
