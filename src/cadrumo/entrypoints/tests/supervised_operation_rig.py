"""Build one real operation supervisor over durable journal, lease and operand stores."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation


class SupervisedOperation(NamedTuple):
    """The stores and services one supervised operation test drives."""

    journal: OperationJournalRepository
    leases: OperationLeaseFilesystemRepository
    operands: object
    supervisor: OperationSupervisor
    result_service: OperationResultProjectionService


def build_supervised_operation(
    *,
    tmp_path: Path,
    objects: SecureObjectRepository,
    authority: PinnedAuthorityOperation,
    registry: OperationRegistry,
    now: datetime,
) -> SupervisedOperation:
    """Return a supervisor with fixed owner and lease token, journalled under ``tmp_path``."""
    durable_root = tmp_path / "operations"
    journal = OperationJournalRepository(storage_root=durable_root)
    leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
    operands = operation_secure_reference_repository(objects=objects)
    supervisor = OperationSupervisor(
        authority_operation=authority,
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: now,
        lease_duration=timedelta(minutes=5),
    )
    result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
    return SupervisedOperation(journal, leases, operands, supervisor, result_service)
