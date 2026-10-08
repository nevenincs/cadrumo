"""Owner-only assembly of runtime operation authority into safe services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter

from ..user_profile.access_errors import ProfileAccessRefusedError
from .authorization import OperationExecutionAuthority
from .drain import OperationDrainResult
from .frontend_requests import OperationResponseControlRequestV1, OperationSubmissionReceiptV1
from .interactions import OperationActorReference
from .models import OperationId, OperationRequest, OperationStoredInvocation, new_operation_id
from .observation import OperationObservationService
from .persistence.financial_operand_custody import (
    OperationTypedFinancialOperandCustodyRepository,
)
from .persistence.journal import (
    OperationEventStream,
    OperationInventoryLimit,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationReader,
    OperationRecoveryInventoryPage,
    OperationSecureReferenceStore,
)
from .projection_services import (
    InspectionOnlyOperationSecureResponseAuthority,
    OperationCancellationService,
    OperationDetachService,
    OperationResponseAuthorityBroker,
    OperationResponseCapability,
    OperationResponseControlService,
    OperationResultProjectionService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
    UnavailableOperationSecureResponseAuthority,
    UnavailableSnapshot,
    read_snapshot,
)
from .provenance import OperationAdmissionProvenance
from .registry import OperationPublicContractSetV1, OperationRegistry
from .secret_submission import OperationSecretRequirement
from .supervisor import OperationSupervisor

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_ACTOR_REFERENCE_ADAPTER: TypeAdapter[OperationActorReference] = TypeAdapter(OperationActorReference)


@dataclass(frozen=True, slots=True)
class OperationSubmission:
    """Durable receipt; only a new invocation receives response authority.

    Idempotent replay returns the original receipt without reserving another
    capability or reviving a lost transaction-specific response bearer.
    """

    receipt: OperationSubmissionReceiptV1
    response_capability: OperationResponseCapability | None


class OperationSubmissionService:
    """Public submit/start door over the private canonical supervisor."""

    def __init__(self, supervisor: OperationSupervisor, authority_broker: OperationResponseAuthorityBroker) -> None:
        """Bind the operational supervisor and response-capability authority."""
        self.supervisor = supervisor
        self._authority_broker = authority_broker

    async def submit[RequestPayloadT: BaseModel](
        self,
        request: OperationRequest[RequestPayloadT],
        *,
        actor_ref: str,
        operation_id: OperationId | None = None,
        provenance: OperationAdmissionProvenance | None = None,
    ) -> OperationSubmission:
        """Durably submit one typed registered request without starting it."""
        validated_actor = _ACTOR_REFERENCE_ADAPTER.validate_python(actor_ref)
        proposed_id = operation_id or new_operation_id()
        submitted_id = await self.supervisor.submit(request, operation_id=proposed_id, provenance=provenance)
        snapshot = await self.supervisor.inspect(submitted_id)
        receipt = OperationSubmissionReceiptV1(
            operation_id=submitted_id, secret_requirement=snapshot.secret_requirement
        )
        return OperationSubmission(
            receipt=receipt,
            response_capability=(
                self._authority_broker.reserve(submitted_id, validated_actor) if submitted_id == proposed_id else None
            ),
        )

    async def submit_secret(self, requirement: OperationSecretRequirement, secret: bytearray) -> None:
        """Transfer one exact mutable secret buffer into runtime-only custody."""
        await self.supervisor.submit_ephemeral_secret(requirement, secret)

    async def require_secret_ready(self, requirement: OperationSecretRequirement) -> None:
        """Check the exact canonical wait before requesting protected bytes."""
        await self.supervisor.require_ephemeral_secret_ready(requirement)

    async def stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        """Resolve internal operands for fresh host authorization, without a response bearer."""
        return await self.supervisor.stored_invocation(operation_id, require_idle=require_idle)

    async def continue_operation(self, operation_id: OperationId) -> OperationId:
        """Reconcile freshly authorized intent and return no raw persisted state."""
        snapshot = await self.supervisor.continue_operation(operation_id)
        return snapshot.identity.operation_id

    async def start(self, operation_id: OperationId) -> OperationId:
        """Admit one submitted operation; it keeps running after this returns.

        Progress and the outcome are read through the observation service, or
        awaited with :meth:`settled`.
        """
        try:
            snapshot = await self.supervisor.start(operation_id)
        except ProfileAccessRefusedError as refusal:
            await self.supervisor.settle_refused_start(operation_id, refusal)
            raise
        return snapshot.identity.operation_id

    async def settled(self, operation_id: OperationId) -> OperationId:
        """Wait until one started operation has concluded, without exposing its raw snapshot.

        Cancelling this wait leaves the operation running.
        """
        snapshot = await self.supervisor.settled(operation_id)
        return snapshot.identity.operation_id


@dataclass(frozen=True, slots=True)
class OperationComposedServices:
    """The service family and exact public contracts of one registry graph."""

    public_contracts: OperationPublicContractSetV1
    submission: OperationSubmissionService
    observation: OperationObservationService
    review: OperationReviewProjectionService
    result: OperationResultProjectionService
    refresh: OperationWorkspaceRefreshTargetService
    cancellation: OperationCancellationService
    detach: OperationDetachService
    _response_factory: Callable[
        [OperationResponseControlRequestV1, OperationResponseCapability],
        Awaitable[OperationResponseControlService],
    ]
    _response_broker: OperationResponseAuthorityBroker
    _response_clock: Callable[[], datetime]
    _shutdown: Callable[[], Awaitable[OperationDrainResult]]
    _drain: Callable[[timedelta], Awaitable[OperationDrainResult]]
    _inventory: Callable[[OperationId | None, OperationInventoryLimit], Awaitable[OperationRecoveryInventoryPage]]

    async def shutdown(self) -> OperationDrainResult:
        """Close within the default bound and report remaining ownership."""
        return await self._shutdown()

    async def drain(self, timeout: timedelta) -> OperationDrainResult:
        """Fence admissions and return unresolved ownership within one deadline."""
        return await self._drain(timeout)

    async def recovery_inventory(
        self, *, after: OperationId | None, limit: OperationInventoryLimit
    ) -> OperationRecoveryInventoryPage:
        """Read one bounded page of existing canonical journal identities."""
        return await self._inventory(after, limit)

    async def response(
        self,
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability | None,
    ) -> OperationResponseControlService:
        """Bind caller identity to the exact process-local REVIEW authority."""
        if capability is None:
            # A receipt (including an idempotent replay) is not response proof.
            return OperationResponseControlService(
                reader=self.observation.reader,
                registry=self.observation.registry,
                authority=UnavailableOperationSecureResponseAuthority(),
                supervisor=self.submission.supervisor,
            )
        return await self._response_factory(request, capability)

    async def inspect_response(
        self,
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability | None,
    ) -> OperationResponseControlService:
        """Inspect a live REVIEW capability without consuming its one-shot bearer."""
        del request  # The returned service validates the exact request against current journal state.
        authority = (
            InspectionOnlyOperationSecureResponseAuthority(self._response_broker, capability, self._response_clock)
            if capability is not None
            else UnavailableOperationSecureResponseAuthority()
        )
        return OperationResponseControlService(
            reader=self.observation.reader,
            registry=self.observation.registry,
            authority=authority,
            supervisor=self.submission.supervisor,
        )


def compose_operation_services(
    *,
    registry: OperationRegistry,
    authority_operation: PinnedAuthorityOperation,
    journal: OperationJournal,
    reader: OperationObservationReader,
    event_stream: OperationEventStream,
    leases: OperationLeaseRepository,
    operands: OperationSecureReferenceStore,
    owner_id: str,
    lease_token_factory: Callable[[], str],
    clock: Callable[[], datetime],
    lease_duration: timedelta,
    execution_timeout: timedelta,
    cleanup_timeout: timedelta,
    typed_financial_operand_custody: OperationTypedFinancialOperandCustodyRepository | None = None,
    execution_authority: OperationExecutionAuthority | None = None,
) -> OperationComposedServices:
    """Bind one immutable registry to real runtime adapters and safe services.

    ``typed_financial_operand_custody`` is optional because only a registry holding a
    definition that declares transient financial operands needs it. The
    supervisor refuses to construct when such a definition is present without
    it, so omitting it stays a refusal rather than a silently operand-less
    supervisor.
    """
    public_contracts = registry.public_contract_set
    authority_broker = OperationResponseAuthorityBroker()
    supervisor = OperationSupervisor(
        registry=registry,
        authority_operation=authority_operation,
        journal=journal,
        event_stream=event_stream,
        leases=leases,
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lease_token_factory,
        clock=clock,
        lease_duration=lease_duration,
        execution_timeout=execution_timeout,
        cleanup_timeout=cleanup_timeout,
        response_authority_issuer=authority_broker,
        typed_financial_operand_custody=typed_financial_operand_custody,
        execution_authority=execution_authority,
    )
    observation = OperationObservationService(reader=reader, registry=registry)

    async def bind_response(
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability,
    ) -> OperationResponseControlService:
        snapshot = await read_snapshot(reader, request.operation_id)
        pending = (
            None if snapshot is None or isinstance(snapshot, UnavailableSnapshot) else snapshot.pending_interaction
        )
        authority = (
            UnavailableOperationSecureResponseAuthority()
            if pending is None
            else authority_broker.bind(request, pending, capability, clock=clock)
        )
        return OperationResponseControlService(
            reader=reader,
            registry=registry,
            authority=authority,
            supervisor=supervisor,
        )

    async def shutdown() -> OperationDrainResult:
        authority_broker.close()
        return await supervisor.shutdown()

    async def drain(timeout: timedelta) -> OperationDrainResult:
        authority_broker.close()
        return await supervisor.drain(timeout)

    async def inventory(after: OperationId | None, limit: OperationInventoryLimit) -> OperationRecoveryInventoryPage:
        return await journal.inventory_page(after=after, limit=limit)

    return OperationComposedServices(
        public_contracts=public_contracts,
        submission=OperationSubmissionService(supervisor, authority_broker),
        observation=observation,
        review=OperationReviewProjectionService(reader=reader, registry=registry, operands=operands, clock=clock),
        result=OperationResultProjectionService(reader=reader, registry=registry, operands=operands),
        refresh=OperationWorkspaceRefreshTargetService(reader=reader, registry=registry),
        cancellation=OperationCancellationService(reader=reader, registry=registry, supervisor=supervisor),
        detach=OperationDetachService(reader=reader, registry=registry, supervisor=supervisor),
        _response_factory=bind_response,
        _response_broker=authority_broker,
        _response_clock=clock,
        _shutdown=shutdown,
        _drain=drain,
        _inventory=inventory,
    )


__all__ = [
    "OperationComposedServices",
    "OperationSubmission",
    "OperationSubmissionService",
    "compose_operation_services",
]
