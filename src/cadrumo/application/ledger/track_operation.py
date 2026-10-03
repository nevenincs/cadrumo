"""Registered exact-profile ledger audit lineage and declaration participation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
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
        if request.definition_id != LEDGER_TRACK_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
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

        return await capture_read_result(context, read, task_name="ledger-track")


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
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_track_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict result facts and the complete-profile read permission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerTrackProjection,
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
