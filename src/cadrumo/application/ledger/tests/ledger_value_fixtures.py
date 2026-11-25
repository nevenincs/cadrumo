"""Canonical dependency-only value fixtures for ledger tests."""

from pathlib import Path

import pytest

from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from .counterparty_establishment_support import InMemoryCounterpartyEstablishmentRepository


@pytest.fixture
def repository() -> CounterpartyEstablishmentRepositoryProtocol:
    """Return a fresh inward capability for application-policy tests."""
    return InMemoryCounterpartyEstablishmentRepository()


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


__all__ = ["pdf_file", "repository"]
