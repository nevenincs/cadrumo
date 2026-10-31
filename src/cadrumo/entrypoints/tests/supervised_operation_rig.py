"""Build one real operation supervisor over durable journal, lease and operand stores."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
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
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability


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
    definition_id: str,
    request: OperationRequest[Any],
    result_type: type[Result],
) -> tuple[OperationPersistedSnapshot, OperationResultProjectionResultV1[Result]]:
    """Submit ``request``, settle it, and read the public result the contract projects for its terminal revision."""
    operation_id = await supervisor.submit(request, operation_id="3" * 64)
    terminal = await run_to_terminal(supervisor, operation_id)
    contract = registry.lookup_public_contract(definition_id)
    assert contract.result_schema is not None
    projected = await result_service.resolve(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        result_type,
    )
    return terminal, projected


def cli_submit_context(*, profile_id: UUID, contract: OperationPublicDefinitionContractV1) -> OperationAccessContext:
    """Return the access context of a CLI submission against published authority for a random destination."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )
