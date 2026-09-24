"""Pytest fixtures for outbound sede adapter tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ......application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
from ......domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....inbound.reconciliation_parser import InboundReconciliationEvidenceParser


@pytest.fixture(autouse=True)
def _bind_declaration_parser() -> Iterator[None]:
    """Compose the inward declaration parser for Sede observation tests."""
    with bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()):
        yield


@pytest.fixture(scope="module")
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Hold one real indexed authority operation for evidence projections."""
    with bundled_indexed_authority().operation() as operation:
        yield operation
