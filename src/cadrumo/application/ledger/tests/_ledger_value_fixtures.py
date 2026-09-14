"""Canonical dependency-only value fixtures for ledger tests."""

from pathlib import Path
from typing import override

import pytest

from ..counterparty_establishment import ConfirmedCounterpartyFacts
from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol


class _InMemoryCounterpartyEstablishmentRepository(CounterpartyEstablishmentRepositoryProtocol):
    """Inward fake for application tests that do not exercise encrypted storage."""

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


@pytest.fixture
def repository() -> CounterpartyEstablishmentRepositoryProtocol:
    """Return a fresh inward capability for application-policy tests."""
    return _InMemoryCounterpartyEstablishmentRepository()


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


__all__ = ["pdf_file", "repository"]
