"""Read operation for the local document reader's status, from any frontend.

``local-reader.status`` judges the lane the agent service derives for every
reader role into one projection. Nothing is started, pulled, loaded or
installed, and the local AI server is not asked anything.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from ..core.model_roles import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import (
    LocalReaderDocumentReadiness,
    LocalReaderStatus,
    read_local_reader_status,
    read_role_lanes,
)
from .local_reader_contracts import (
    LOCAL_READER_OPERATION_SUBJECT,
)
from .local_reader_operation import bind_machine_reader_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.registry import OperationPublicDefinitionRegistrationV1
from .operations.subject_reference import OperationSubjectReferenceV1

__all__ = [
    "LOCAL_READER_STATUS_OPERATION_DEFINITION_ID",
    "LocalReaderRoleStatusV1",
    "LocalReaderStatusExecutor",
    "LocalReaderStatusPublicResultV1",
    "LocalReaderStatusRequest",
    "build_local_reader_status_definition",
    "build_local_reader_status_registration",
    "local_reader_status_public_result",
    "project_local_reader_status_result",
    "resolve_local_reader_status_access",
]

LOCAL_READER_STATUS_OPERATION_DEFINITION_ID = "local-reader.status"


class LocalReaderStatusRequest(CredentialFreeOperationRequest):
    """One status read of the machine's local reader."""


class LocalReaderRoleStatusV1(BaseModel):
    """Public projection of one role's reader.

    ``installed`` is ``None`` when nobody stated it, which is distinct from false.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    installed: bool | None = None
    ready: bool
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderStatusPublicResultV1(BaseModel):
    """Public projection of the whole local reader at one moment."""

    model_config = STRICT_FROZEN_CONFIG

    roles: tuple[LocalReaderRoleStatusV1, ...]
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool


class LocalReaderStatusExecutor:
    """Judge the reader and persist the judgement; nothing is started, pulled or installed."""

    async def execute(
        self,
        request: OperationRequest[LocalReaderStatusRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the status and persist it."""
        if request.subject_ref != LOCAL_READER_OPERATION_SUBJECT:
            raise ValueError("local-reader operation subject must name the local runtime")
        await context.events.phase(LOCAL_READER_STATUS_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        lanes = await read_role_lanes(ModelRole)
        status = await asyncio.to_thread(read_local_reader_status, lanes)
        return await context.operands.put(status, written_at=now())


def build_local_reader_status_definition() -> OperationDefinition:
    """Build the reader status read."""
    return build_single_phase_definition(
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        request_type=LocalReaderStatusRequest,
        subject_reference=OperationSubjectReferenceV1.fixed(LOCAL_READER_OPERATION_SUBJECT),
        result_type=LocalReaderStatus,
        executor_type=LocalReaderStatusExecutor,
        build=LocalReaderStatusExecutor,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_local_reader_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind access to the machine's reader without COMMIT: a status read changes no record."""
    return bind_machine_reader_access(
        request,
        context,
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        payload_type=LocalReaderStatusRequest,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
    )


def project_local_reader_status_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled status read into its public result."""
    del terminal_receipt
    return local_reader_status_public_result(LocalReaderStatus.model_validate(result, strict=True))


def local_reader_status_public_result(status: LocalReaderStatus) -> LocalReaderStatusPublicResultV1:
    """Return the public result of one status read, whichever caller took it."""
    return LocalReaderStatusPublicResultV1(
        roles=tuple(
            LocalReaderRoleStatusV1(
                role=row.role,
                model=row.model,
                installed=row.installed,
                ready=row.ready,
                failed_condition_id=row.failed_condition_id,
            )
            for row in status.roles
        ),
        extraction_ready=status.extraction_ready,
        document_readiness=status.document_readiness,
        text_layer_model_fill_available=status.text_layer_model_fill_available,
    )


def build_local_reader_status_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the status definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LocalReaderStatusPublicResultV1,
        result_projector=project_local_reader_status_result,
        access_resolver=resolve_local_reader_status_access,
    )
