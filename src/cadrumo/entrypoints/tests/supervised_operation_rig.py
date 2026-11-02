"""Build one real operation supervisor over durable journal, lease and operand stores."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.authorization import OperationExecutionAuthority
from cadrumo.application.operations.frontend_contracts import OperationResultProjectionResultV1
from cadrumo.application.operations.frontend_requests import OperationResultProjectionRequestV1
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, OperationAccessRequest


class SupervisedOperation(NamedTuple):
    """The stores and services one supervised operation test drives."""

    journal: OperationJournalRepository
    leases: OperationLeaseFilesystemRepository
    operands: OperationSecureReferenceRepository
    supervisor: OperationSupervisor
    result_service: OperationResultProjectionService


def build_supervised_operation(
    *,
    tmp_path: Path,
    objects: SecureObjectRepository,
    authority: PinnedAuthorityOperation,
    registry: OperationRegistry,
    now: datetime,
    execution_authority: OperationExecutionAuthority | None = None,
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
        execution_authority=execution_authority,
    )
    result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
    return SupervisedOperation(journal, leases, operands, supervisor, result_service)


async def run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    """Admit the operation and wait for the supervised task that settles it."""
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def assert_foreign_profile_refused(
    *, registry: OperationRegistry, request: OperationRequest[Any], context: OperationAccessContext
) -> None:
    """Assert the same request retargeted at another profile is refused as a profile mismatch."""
    foreign_profile_id = uuid4()
    foreign_request = request.model_copy(
        update={
            "subject_ref": profile_operation_subject(str(foreign_profile_id)),
            "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
        }
    )
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_operation_access(registry=registry, request=foreign_request, context=context)
    assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH


async def settle_and_project[Result: BaseModel](
    supervisor: OperationSupervisor,
    result_service: OperationResultProjectionService,
    registry: OperationRegistry,
    request: OperationRequest[Any],
    result_type: type[Result],
    *,
    operation_id: str = "3" * 64,
) -> tuple[OperationPersistedSnapshot, OperationResultProjectionResultV1[Result]]:
    """Submit ``request``, settle it, and read the public result the contract projects for its terminal revision."""
    submitted_id = await supervisor.submit(request, operation_id=operation_id)
    terminal = await run_to_terminal(supervisor, submitted_id)
    contract = registry.lookup_public_contract(request.definition_id)
    assert contract.result_schema is not None
    projected = await result_service.resolve(
        OperationResultProjectionRequestV1(
            operation_id=submitted_id,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        result_type,
    )
    return terminal, projected


def operation_access_context(
    contract: OperationPublicDefinitionContractV1,
    *,
    profile_id: UUID,
    action: AccessAction = AccessAction.SUBMIT,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    destination_id: UUID | None = None,
    authority_operation: PinnedAuthorityOperation | None = None,
    admitted_request: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    """Return the access context of ``action`` against published authority, for a random destination unless given."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4() if destination_id is None else destination_id,
        action=action,
        frontend=frontend,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted_request,
        authority_operation=authority_operation,
    )


def cli_submit_context(
    *,
    profile_id: UUID,
    contract: OperationPublicDefinitionContractV1,
    authority_operation: PinnedAuthorityOperation | None = None,
) -> OperationAccessContext:
    """Return the access context of a CLI submission against published authority for a random destination."""
    return operation_access_context(contract, profile_id=profile_id, authority_operation=authority_operation)


class ProcessResourceScope:
    """Track worker-owned PROCESS activation and cleanup without launching a process."""

    def __init__(self) -> None:
        self.activation_depth = 0
        self.activation_entries = 0
        self.close_calls = 0
        self.closed = False

    @contextmanager
    def activate(self) -> Generator[None]:
        self.activation_entries += 1
        self.activation_depth += 1
        try:
            yield
        finally:
            self.activation_depth -= 1

    async def close(self) -> None:
        assert self.activation_depth == 0
        self.close_calls += 1
        self.closed = True
