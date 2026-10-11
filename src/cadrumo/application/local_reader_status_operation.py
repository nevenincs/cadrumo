"""Read operation for the local document reader's status, from any frontend.

``local-reader.status`` measures the runtime host and every reader role's
model into one projection. With ``probe`` it also runs the text model's
fitness check now, which loads that model on the runtime and records nothing.
Nothing is started, pulled or installed.

The fitness probe is injected. The application layer never opens the model
transport itself; the entrypoint composition binds the outbound adapter.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import BaseModel, Field, NonNegativeInt

from ..core.hardware import ContentionCause
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import (
    LocalReaderDocumentReadiness,
    LocalReaderStatus,
    RoleFitnessState,
    TextExtractionFitnessProbe,
    read_local_reader_status,
)
from .local_reader_contracts import (
    LOCAL_READER_OPERATION_SUBJECT,
    LocalReaderFactV1,
    local_reader_public_facts,
    local_reader_verdict_condition,
    local_reader_verdict_facts,
)
from .local_reader_operation import bind_machine_provisioning_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.registry import OperationPublicDefinitionRegistrationV1
from .operations.subject_reference import OperationSubjectReferenceV1
from .provisioning_host import RuntimeHostPlatform, RuntimeInstaller

__all__ = [
    "LOCAL_READER_STATUS_OPERATION_DEFINITION_ID",
    "LocalReaderHostStatusV1",
    "LocalReaderLastPullV1",
    "LocalReaderRoleStatusV1",
    "LocalReaderStatusExecutor",
    "LocalReaderStatusPublicResultV1",
    "LocalReaderStatusRequest",
    "build_local_reader_status_definition",
    "build_local_reader_status_registration",
    "build_local_reader_status_request",
    "local_reader_status_public_result",
    "project_local_reader_status_result",
    "resolve_local_reader_status_access",
]

LOCAL_READER_STATUS_OPERATION_DEFINITION_ID = "local-reader.status"


class LocalReaderStatusRequest(CredentialFreeOperationRequest):
    """One status read; ``probe`` checks the text model's fitness now instead of reading the recorded verdict."""

    probe: bool = False


def build_local_reader_status_request(*, probe: bool) -> OperationRequest[LocalReaderStatusRequest]:
    """Build the request that reads the machine's reader status, probing fitness when asked."""
    return OperationRequest(
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderStatusRequest(probe=probe),
    )


class LocalReaderHostStatusV1(BaseModel):
    """Public projection of the runtime host: whether it is installed, and whether it answers."""

    model_config = STRICT_FROZEN_CONFIG

    platform: RuntimeHostPlatform
    endpoint_url: str = Field(min_length=1)
    endpoint_local: bool
    executable_located: bool
    reachable: bool
    version: str | None = None
    installer: RuntimeInstaller
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


class LocalReaderRoleStatusV1(BaseModel):
    """Public projection of one role's reader.

    ``installed``, ``resident`` and ``load_admitted`` are ``None`` when they
    could not be measured, which is distinct from false.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: tuple[ContentionCause, ...]
    fitness: RoleFitnessState | None = None
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderLastPullV1(BaseModel):
    """Public projection of the most recent fetch the serving process attempted."""

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1)
    pulled: bool
    attempted_at: datetime
    bytes_fetched: NonNegativeInt | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderStatusPublicResultV1(BaseModel):
    """Public projection of the whole local reader at one moment."""

    model_config = STRICT_FROZEN_CONFIG

    host: LocalReaderHostStatusV1
    roles: tuple[LocalReaderRoleStatusV1, ...]
    last_pull: LocalReaderLastPullV1 | None = None
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool


class LocalReaderStatusExecutor:
    """Measure the reader and persist the measurement; nothing is started, pulled or installed."""

    def __init__(self, *, text_probe: TextExtractionFitnessProbe) -> None:
        """Bind the injected text-reader fitness probe a probing read runs."""
        self._text_probe = text_probe

    async def execute(
        self,
        request: OperationRequest[LocalReaderStatusRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the status, probing fitness when the request asks, and persist it."""
        if request.subject_ref != LOCAL_READER_OPERATION_SUBJECT:
            raise ValueError("local-reader operation subject must name the local runtime")
        await context.events.phase(LOCAL_READER_STATUS_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        probe = self._text_probe if request.payload.probe else None
        status = await asyncio.to_thread(read_local_reader_status, text_probe=probe)
        return await context.operands.put(status, written_at=now())


def build_local_reader_status_definition(*, text_probe: TextExtractionFitnessProbe) -> OperationDefinition:
    """Bind the injected fitness probe to the reader status read."""
    return build_single_phase_definition(
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        request_type=LocalReaderStatusRequest,
        subject_reference=OperationSubjectReferenceV1.fixed(LOCAL_READER_OPERATION_SUBJECT),
        result_type=LocalReaderStatus,
        executor_type=LocalReaderStatusExecutor,
        build=lambda: LocalReaderStatusExecutor(text_probe=text_probe),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_local_reader_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind access to the machine's reader without COMMIT: a status read changes no record."""
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        payload_type=LocalReaderStatusRequest,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        commits=lambda _payload: False,
    )


def project_local_reader_status_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled status read into its public result."""
    del terminal_receipt
    return local_reader_status_public_result(LocalReaderStatus.model_validate(result, strict=True))


def local_reader_status_public_result(status: LocalReaderStatus) -> LocalReaderStatusPublicResultV1:
    """Return the public result of one status read, whichever caller took it."""
    host = status.host
    last = status.last_pull
    return LocalReaderStatusPublicResultV1(
        host=LocalReaderHostStatusV1(
            platform=host.platform,
            endpoint_url=host.endpoint_url,
            endpoint_local=host.endpoint_local,
            executable_located=host.executable_located,
            reachable=host.reachable,
            version=host.version,
            installer=host.installer,
            facts=local_reader_public_facts(host.facts),
            verdict_condition_id=local_reader_verdict_condition(host.precondition_verdict),
            verdict_facts=local_reader_verdict_facts(host.precondition_verdict),
        ),
        roles=tuple(
            LocalReaderRoleStatusV1(
                role=row.role,
                model=row.model,
                installed=row.installed,
                resident=row.resident,
                load_admitted=row.load_admitted,
                contention_causes=row.contention_causes,
                fitness=row.fitness,
                fit_for_role=row.fit_for_role,
                ready=row.ready,
                failed_condition_id=row.failed_condition_id,
            )
            for row in status.roles
        ),
        last_pull=(
            None
            if last is None
            else LocalReaderLastPullV1(
                model=last.model,
                pulled=last.pulled,
                attempted_at=last.attempted_at,
                bytes_fetched=last.bytes_fetched,
                failed_condition_id=last.failed_condition_id,
            )
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
