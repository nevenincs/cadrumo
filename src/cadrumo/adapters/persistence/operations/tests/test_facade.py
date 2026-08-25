"""Public facade contracts for durable operation persistence adapters."""

from __future__ import annotations

import pytest

from .. import (
    OPERATION_SECURE_REFERENCE_NAMESPACE,
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from .. import __all__ as operations_all
from .. import __dict__ as operations_namespace

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_operation_persistence_facade_exports_only_concrete_repositories() -> None:
    """The external adapter surface exposes repositories, never lock internals."""
    assert operations_all == [
        "OPERATION_SECURE_REFERENCE_NAMESPACE",
        "OperationJournalRepository",
        "OperationLeaseFilesystemRepository",
        "OperationSecureReferenceRepository",
        "operation_secure_reference_repository",
    ]
    assert operations_namespace["OPERATION_SECURE_REFERENCE_NAMESPACE"] is OPERATION_SECURE_REFERENCE_NAMESPACE
    assert operations_namespace["OperationJournalRepository"] is OperationJournalRepository
    assert operations_namespace["OperationLeaseFilesystemRepository"] is OperationLeaseFilesystemRepository
    assert operations_namespace["OperationSecureReferenceRepository"] is OperationSecureReferenceRepository
    assert operations_namespace["operation_secure_reference_repository"] is operation_secure_reference_repository
    assert "OperationLeaseStorage" not in operations_namespace
