"""Pytest fixtures for outbound sede adapter tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ......adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
from ......application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser


@pytest.fixture(autouse=True)
def _bind_declaration_parser() -> Iterator[None]:
    """Compose the inward declaration parser for Sede observation tests."""
    with bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()):
        yield
