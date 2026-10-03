"""Exact-profile local invoice-reader readiness operation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ..local_reader import LocalReaderDocumentReadiness, LocalReaderStatus, RoleFitnessState
from ..operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..provisioning_host import RuntimeHostPlatform, RuntimeInstaller
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .invoice_evidence_operation import (
    InvoiceEvidenceLabel,
    check_invoice_evidence_result_size,
    invoice_evidence_operation_capabilities,
    require_invoice_evidence_terminal_success,
)

LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID = "ledger.evidence.reader-readiness"


class LedgerEvidenceReaderReadinessRequest(BaseModel):
    """Metadata-only readiness for the authenticated exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ReaderHostProjectionV1(BaseModel):
    """Closed host facts; no provisioning action is available here."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    platform: RuntimeHostPlatform
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2_048)]
    endpoint_local: bool
    executable_located: bool
    reachable: bool
    version: InvoiceEvidenceLabel | None = None
    installer: RuntimeInstaller
    available: bool
    failed_condition_id: InvoiceEvidenceLabel | None = None


class ReaderRoleProjectionV1(BaseModel):
    """One locally measured model role and its recorded fitness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: Annotated[str, Field(min_length=1, max_length=128)]
    model: InvoiceEvidenceLabel | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    fitness: RoleFitnessState | None = None
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: InvoiceEvidenceLabel | None = None


class ReaderPullProjectionV1(BaseModel):
    """The process-local last pull, if one was recorded earlier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    model: InvoiceEvidenceLabel
    pulled: bool
    attempted_at: datetime
    bytes_fetched: Annotated[int, Field(ge=0)] | None = None
    failed_condition_id: InvoiceEvidenceLabel | None = None


class LedgerEvidenceReaderReadinessProjection(BaseModel):
    """Exact-profile reader status without document or tax values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    host: ReaderHostProjectionV1
    roles: Annotated[tuple[ReaderRoleProjectionV1, ...], Field(max_length=32)]
    last_pull: ReaderPullProjectionV1 | None = None
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool

    @classmethod
    def from_status(cls, profile_id: UUID, status: LocalReaderStatus) -> Self:
        """Copy measured host and role facts without a provisioning action."""
        host = status.host
        last_pull = status.last_pull
        return cls(
            profile_id=profile_id,
            host=ReaderHostProjectionV1(
                platform=host.platform,
                endpoint_url=host.endpoint_url,
                endpoint_local=host.endpoint_local,
                executable_located=host.executable_located,
                reachable=host.reachable,
                version=host.version,
                installer=host.installer,
                available=host.available,
                failed_condition_id=(
                    None if host.precondition_verdict is None else host.precondition_verdict.failed_condition_id
                ),
            ),
            roles=tuple(
                ReaderRoleProjectionV1(
                    role=row.role.value,
                    model=row.model,
                    installed=row.installed,
                    resident=row.resident,
                    load_admitted=row.load_admitted,
                    contention_causes=tuple(cause.value for cause in row.contention_causes),
                    fitness=row.fitness,
                    fit_for_role=row.fit_for_role,
                    ready=row.ready,
                    failed_condition_id=row.failed_condition_id,
                )
                for row in status.roles
            ),
            last_pull=(
                None
                if last_pull is None
                else ReaderPullProjectionV1(
                    model=last_pull.model,
                    pulled=last_pull.pulled,
                    attempted_at=last_pull.attempted_at,
                    bytes_fetched=last_pull.bytes_fetched,
                    failed_condition_id=last_pull.failed_condition_id,
                )
            ),
            extraction_ready=status.extraction_ready,
            document_readiness=status.document_readiness,
            text_layer_model_fill_available=status.text_layer_model_fill_available,
        )


class LedgerEvidenceReaderReadinessExecutionResult(BaseModel):
    """Encrypted worker result scoped to the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReaderReadinessProjection


class LedgerEvidenceReaderReadinessExecutor:
    """Read local runtime and recorded fitness without loading a model."""

    def __init__(self, read_status: Callable[[], LocalReaderStatus]) -> None:
        """Bind the read-only canonical status provider."""
        self._read_status = read_status

    async def execute(
        self, request: OperationRequest[LedgerEvidenceReaderReadinessRequest], context: OperationExecutorContext
    ) -> str:
        """Measure local readiness and capture a bounded profile result."""
        profile_id = request.payload.profile_id
        if request.definition_id != LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, profile_id)
        await context.events.phase(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        async def read_and_capture() -> str:
            status = await asyncio.to_thread(self._read_status)
            result = LedgerEvidenceReaderReadinessProjection.from_status(profile_id, status)
            check_invoice_evidence_result_size(result)
            return await context.operands.put(
                LedgerEvidenceReaderReadinessExecutionResult(profile_id=profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(read_and_capture(), task_name="ledger-evidence-reader-readiness")


def build_ledger_evidence_reader_readiness_definition(
    read_status: Callable[[], LocalReaderStatus],
) -> OperationDefinition:
    """Register one read-only local reader measurement for the exact profile."""
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceReaderReadinessRequest,
        result_type=LedgerEvidenceReaderReadinessExecutionResult,
        executor_type=LedgerEvidenceReaderReadinessExecutor,
        build=lambda: LedgerEvidenceReaderReadinessExecutor(read_status),
        capabilities=invoice_evidence_operation_capabilities(mutates=False),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _project_readiness(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceReaderReadinessExecutionResult:
        raise ValueError("invalid reader readiness result")
    require_invoice_evidence_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({OperationEffect.NONE}),
    )
    if result.result.profile_id != result.profile_id:
        raise ValueError("reader readiness result belongs to another profile")
    return result.result


def _resolve_metadata_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if context.contract.definition_id != LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = require_access_request_profile_payload(
        request,
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        payload_type=LedgerEvidenceReaderReadinessRequest,
        access_profile_id=context.profile_id,
    )
    return bind_operation_access_profile(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        profile_id=payload.profile_id,
        definition_id=request.definition_id,
        periods=frozenset(),
    )


def build_ledger_evidence_reader_readiness_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind metadata disclosure and the closed readiness schema."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidenceReaderReadinessProjection,
        result_projector=_project_readiness,
        access_resolver=_resolve_metadata_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID",
    "LedgerEvidenceReaderReadinessExecutionResult",
    "LedgerEvidenceReaderReadinessExecutor",
    "LedgerEvidenceReaderReadinessProjection",
    "LedgerEvidenceReaderReadinessRequest",
    "ReaderHostProjectionV1",
    "ReaderPullProjectionV1",
    "ReaderRoleProjectionV1",
    "build_ledger_evidence_reader_readiness_definition",
    "build_ledger_evidence_reader_readiness_registration",
]
