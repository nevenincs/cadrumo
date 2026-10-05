"""Registered exact-profile finalized transaction participation lookup."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .id_resolution import resolve_lineage_transaction_id
from .participation_read import TransactionParticipationIndexRepositoryFactory, get_transaction_participation
from .read_access import resolve_ledger_read_access
from .tracking_projection import LedgerParticipationProjection as LedgerParticipationEntryProjection

LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID = "ledger.participation"


class LedgerParticipationRequest(CredentialFreeOperationRequest):
    """An exact profile and a current or superseded transaction handle."""

    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")


class LedgerParticipationProjection(BaseModel):
    """Only the canonical resolved handle and its finalized participation entries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_prefix: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
    transaction_id: TransactionId
    participations: tuple[LedgerParticipationEntryProjection, ...]


class LedgerParticipationExecutor:
    """Read the persisted finalized-revision inverse index inside profile custody."""

    def __init__(
        self, ports: LedgerActionPortsFactory, participation: TransactionParticipationIndexRepositoryFactory
    ) -> None:
        """Retain only the explicit profile-bound composition capability."""
        self._ports = ports
        self._participation = participation

    async def execute(
        self, request: OperationRequest[LedgerParticipationRequest], context: OperationExecutorContext
    ) -> str:
        """Publish an encrypted read result with no domain mutation effect."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID)

        def read() -> LedgerParticipationProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            selected = resolve_lineage_transaction_id(payload.transaction_prefix, ports.transaction_repository.load())
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
            return LedgerParticipationProjection(
                profile_id=payload.profile_id,
                transaction_prefix=payload.transaction_prefix,
                transaction_id=selected,
                participations=tuple(
                    LedgerParticipationEntryProjection.from_participation(item) for item in index.participations
                ),
            )

        return await capture_read_result(context, read, task_name="ledger-participation")


def build_ledger_participation_definition(
    ports: LedgerActionPortsFactory, participation: TransactionParticipationIndexRepositoryFactory
) -> OperationDefinition:
    """Declare one local read without COMMIT or external-provider capability."""
    return build_single_phase_definition(
        definition_id=LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
        request_type=LedgerParticipationRequest,
        result_type=LedgerParticipationProjection,
        executor_type=LedgerParticipationExecutor,
        build=lambda: LedgerParticipationExecutor(ports, participation),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_ledger_participation_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict result facts and the complete-profile read permission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerParticipationProjection,
        access_resolver=resolve_ledger_participation_access,
    )


def resolve_ledger_participation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Protect finalized participation across all declaration periods."""
    if request.definition_id != LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerParticipationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
