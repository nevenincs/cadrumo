"""Registered automation administration through the existing operation owner.

Runtime composition supplies a connection-bound administration service. Missing
runtime dependencies refuse explicitly. Secret proposals and passwords use the
existing ephemeral broker; journals contain only safe routing/review identities.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from pydantic import SecretBytes, ValidationError

from ...core.errors.hierarchy import CadrumoError
from ...core.identity.digest import ContentDigest
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
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
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from .automation_administration import AutomationAdministrationService
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import AutomationInventory, EnrollmentKind, EnrollmentProposal, EnrollmentReceipt

AUTOMATION_REQUEST_OPERATION_DEFINITION_ID = "user-profile.automation-request"
AUTOMATION_ROTATE_OPERATION_DEFINITION_ID = "user-profile.automation-rotate"
AUTOMATION_RENEW_OPERATION_DEFINITION_ID = "user-profile.automation-renew"
AUTOMATION_SCOPE_OPERATION_DEFINITION_ID = "user-profile.automation-scope"
AUTOMATION_APPROVE_OPERATION_DEFINITION_ID = "user-profile.automation-approve"
AUTOMATION_DECLINE_OPERATION_DEFINITION_ID = "user-profile.automation-decline"
AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID = "user-profile.automation-inventory"

_PROPOSALS = {
    AUTOMATION_REQUEST_OPERATION_DEFINITION_ID: EnrollmentKind.ENROLL,
    AUTOMATION_ROTATE_OPERATION_DEFINITION_ID: EnrollmentKind.ROTATE,
    AUTOMATION_RENEW_OPERATION_DEFINITION_ID: EnrollmentKind.RENEW,
    AUTOMATION_SCOPE_OPERATION_DEFINITION_ID: EnrollmentKind.CHANGE_SCOPE,
}


class AutomationOperationRequest(CredentialFreeOperationRequest):
    """Safe invocation coordinates; private consent is sealed in custody."""

    profile_id: UUID
    request_id: UUID
    review_digest: ContentDigest | None = None


type AutomationAdministrationFactory = Callable[[OperationExecutorContext, UUID], AutomationAdministrationService]


class AutomationAdministrationRefusedError(CadrumoError):
    """Safe operation refusal; private adapter diagnostics never enter the journal."""


class AutomationAdministrationExecutor:
    """Dispatch real application services without accepting caller authority facts."""

    def __init__(self, factory: AutomationAdministrationFactory | None) -> None:
        """Retain only the trusted composition capability, never ambient authorization."""
        self.factory = factory

    async def execute(
        self, request: OperationRequest[AutomationOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Consume ephemeral input and record only safe effect/phase facts."""
        try:
            return await self._execute(request, context)
        except AutomationCustodyError as error:
            raise AutomationAdministrationRefusedError(error.reason.value) from None

    async def _execute(
        self, request: OperationRequest[AutomationOperationRequest], context: OperationExecutorContext
    ) -> str:
        payload, identity = request.payload, request.definition_id
        if request.subject_ref != profile_operation_subject(str(payload.profile_id)):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        if self.factory is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        service = self.factory(context, payload.profile_id)
        if service.owner.facts().profile.binding.profile_id != payload.profile_id:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        await context.events.phase(identity + ".execute")
        if identity == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID:
            inventory = await asyncio.to_thread(service.inventory)
            # Inventory is human-only private metadata in the existing encrypted
            # result store; observing an operation never grants new authority.
            return await context.operands.put(inventory, written_at=now())
        await context.events.effect(OperationEffect.UNKNOWN)
        if identity in _PROPOSALS:
            async with context.ephemeral_secret.consume() as raw:
                try:
                    proposal = EnrollmentProposal.model_validate_json(bytes(raw))
                except ValidationError:
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
                if proposal.kind is not _PROPOSALS[identity]:
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID)
                await asyncio.to_thread(service.request, payload.request_id, proposal)
        elif identity == AUTOMATION_APPROVE_OPERATION_DEFINITION_ID:
            if payload.review_digest is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            async with context.ephemeral_secret.consume() as raw:
                await asyncio.to_thread(
                    service.approve,
                    payload.request_id,
                    review_digest=payload.review_digest,
                    password=SecretBytes(bytes(raw)),
                )
        elif identity == AUTOMATION_DECLINE_OPERATION_DEFINITION_ID:
            if payload.review_digest is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            await asyncio.to_thread(service.decline, payload.request_id, review_digest=payload.review_digest)
        else:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        await context.events.effect(OperationEffect.UPDATED)
        # Pre-unlock custody is independent of the process-global profile store.
        # Reconcile the durable receipt through authorized inventory, never by
        # reconstructing a lost secret or a response-control capability.
        return request.subject_ref


def build_automation_operation_definitions(
    factory: AutomationAdministrationFactory | None = None,
) -> tuple[OperationDefinition, ...]:
    """Enroll implemented executors; native/runtime capability is separately required."""
    result: list[OperationDefinition] = []
    for identity in (
        *_PROPOSALS,
        AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
        AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
        AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    ):
        secret_kind = (
            "automation.proposal"
            if identity in _PROPOSALS
            else "automation.password"
            if identity == AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
            else None
        )
        result.append(
            OperationDefinition(
                definition_id=identity,
                request_type=AutomationOperationRequest,
                result_type=AutomationInventory
                if identity == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
                else EnrollmentReceipt,
                executor_factory=OperationExecutorFactory(
                    request_type=AutomationOperationRequest,
                    executor_type=AutomationAdministrationExecutor,
                    build=lambda: AutomationAdministrationExecutor(factory),
                ),
                phase_codes=(identity + ".execute",),
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
                    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
                permitted_frontends=frozenset(OperationFrontendProjection),
                ephemeral_secret=None
                if secret_kind is None
                else OperationEphemeralSecretDeclaration(secret_kind=secret_kind, lifetime=timedelta(minutes=5)),
            )
        )
    return tuple(result)


def build_automation_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind existing discovery contracts without claiming a private result projector."""
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_only(
            definition=item, request_schema_id=item.definition_id + ".request"
        )
        for item in definitions
    )
