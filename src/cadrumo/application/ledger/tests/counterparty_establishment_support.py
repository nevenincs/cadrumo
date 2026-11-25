"""In-memory counterparty establishment repository for application-policy tests."""

from __future__ import annotations

from typing import override

from ..counterparty_establishment import ConfirmedCounterpartyFacts
from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol


class InMemoryCounterpartyEstablishmentRepository(CounterpartyEstablishmentRepositoryProtocol):
    """Inward fake for tests that do not exercise encrypted storage."""

    def __init__(self) -> None:
        self._records: dict[str, ConfirmedCounterpartyFacts] = {}

    @override
    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        return self._records.get(identifier)

    @override
    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        self._records[payload.counterparty_key] = payload

    @override
    def delete(self, identifier: str) -> bool:
        return self._records.pop(identifier, None) is not None
