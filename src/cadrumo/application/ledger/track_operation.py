"""Registered exact-profile ledger audit lineage and declaration participation."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_manual import get_manual_transaction, ledger_transaction_payload, ledger_transaction_tracking_payload
from .id_resolution import resolve_lineage_transaction_id
from .participation_read import TransactionParticipationIndexRepositoryFactory, get_transaction_participation
from .read_access import resolve_ledger_read_access
from .tracking_projection import (
    LedgerImportedProvenanceProjection,
    LedgerParticipationProjection,
    LedgerTrackingProjection,
)
from .transaction_projection import LedgerTransactionProjection

LEDGER_TRACK_OPERATION_DEFINITION_ID = "ledger.track"


class LedgerTrackRequest(CredentialFreeOperationRequest):
    """An exact profile and a current or superseded transaction handle."""

    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")


class LedgerTrackProjection(BaseModel):
    """Complete admitted lineage, transaction and finalized participation facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    transaction: LedgerTransactionProjection
    tracking: LedgerTrackingProjection
    imported_provenance: LedgerImportedProvenanceProjection | None
    participated_in: tuple[LedgerParticipationProjection, ...] | None

    @model_validator(mode="after")
    def _same_transaction(self) -> LedgerTrackProjection:
        if self.transaction.transaction_id != self.tracking.transaction_id:
            raise ValueError("lineage and transaction identities must agree")
        if (self.tracking.created_event_id is None) != (self.imported_provenance is not None):
            raise ValueError("import provenance must agree with transaction origin")
        if self.participated_in == ():
            raise ValueError("an absent participation index is represented by null")
        return self


class LedgerTrackExecutor:
    """Read canonical lineage and its persisted finalized-revision inverse index."""

    def __init__(
        self, ports: LedgerActionPortsFactory, participation: TransactionParticipationIndexRepositoryFactory
    ) -> None:
        """Retain only the explicit profile-bound composition capability."""
        self._ports = ports
        self._participation = participation

    async def execute(self, request: OperationRequest[LedgerTrackRequest], context: OperationExecutorContext) -> str:
        """Publish an encrypted read result with no domain mutation effect."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if (
            request.definition_id != LEDGER_TRACK_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_TRACK_OPERATION_DEFINITION_ID)

        def read() -> LedgerTrackProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            selected = resolve_lineage_transaction_id(payload.transaction_prefix, ports.transaction_repository.load())
            result = get_manual_transaction(bucket_id=bucket_id, transaction_id=selected, ports=ports)
            if result.ref.bucket_id != bucket_id or result.ref.transaction_id != selected:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            participation_repository = self._participation(bucket_id=bucket_id)
            if participation_repository.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            index = get_transaction_participation(
                transaction_id=selected,
                bucket_id=bucket_id,
                participation_index_repository=participation_repository,
            )
            if index.transaction_id != selected:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return LedgerTrackProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                transaction=LedgerTransactionProjection.from_payload(ledger_transaction_payload(result.transaction)),
                tracking=LedgerTrackingProjection.from_payload(ledger_transaction_tracking_payload(result.transaction)),
                imported_provenance=LedgerImportedProvenanceProjection.from_transaction(result.transaction),
                participated_in=LedgerParticipationProjection.from_index(index),
            )

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="ledger-track")


def build_ledger_track_definition(
    ports: LedgerActionPortsFactory, participation: TransactionParticipationIndexRepositoryFactory
) -> OperationDefinition:
    """Declare one local read without COMMIT or external-provider capability."""
    return OperationDefinition(
        definition_id=LEDGER_TRACK_OPERATION_DEFINITION_ID,
        request_type=LedgerTrackRequest,
        result_type=LedgerTrackProjection,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerTrackRequest,
            executor_type=LedgerTrackExecutor,
            build=lambda: LedgerTrackExecutor(ports, participation),
        ),
        phase_codes=(LEDGER_TRACK_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_track_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict result facts and the complete-profile read permission."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerTrackRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=LedgerTrackProjection
        ),
        access_resolver=resolve_ledger_track_access,
    )


def resolve_ledger_track_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Protect the complete transaction, cross-period lineage and declaration history."""
    if request.definition_id != LEDGER_TRACK_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerTrackRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
