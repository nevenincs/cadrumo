"""Public facade contracts for durable operation persistence adapters."""

from __future__ import annotations

import pytest

from .. import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
)
from .. import __all__ as operations_all
from .. import __dict__ as operations_namespace

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_operation_persistence_facade_exports_only_concrete_repositories() -> None:
    """The external adapter surface exposes repositories, never lock internals."""
    assert operations_all == ["OperationJournalRepository", "OperationLeaseFilesystemRepository"]
    assert operations_namespace["OperationJournalRepository"] is OperationJournalRepository
    assert operations_namespace["OperationLeaseFilesystemRepository"] is OperationLeaseFilesystemRepository
    assert "OperationLeaseStorage" not in operations_namespace
