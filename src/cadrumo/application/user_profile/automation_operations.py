"""Registered automation administration through the existing operation owner.

Runtime composition supplies a connection-bound administration service. Missing
runtime dependencies refuse explicitly. Secret proposals and passwords use the
existing ephemeral broker; journals contain only safe routing/review identities.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, SecretBytes, ValidationError

from ...core.async_cleanup import await_cancellation_complete, close_async_resources
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
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import (
    AutomationGrantProjection,
    AutomationInventory,
    AutomationInventoryProjection,
    AutomationKeyProjection,
    AutomationPeriodProjection,
    AutomationProposalProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentReceipt,
    EnrollmentTransition,
)
from .automation_execution import AutomationAdministrationExecution

AUTOMATION_REQUEST_OPERATION_DEFINITION_ID = "user-profile.automation-request"
AUTOMATION_ROTATE_OPERATION_DEFINITION_ID = "user-profile.automation-rotate"
AUTOMATION_RENEW_OPERATION_DEFINITION_ID = "user-profile.automation-renew"
AUTOMATION_SCOPE_OPERATION_DEFINITION_ID = "user-profile.automation-scope"
AUTOMATION_APPROVE_OPERATION_DEFINITION_ID = "user-profile.automation-approve"
AUTOMATION_DECLINE_OPERATION_DEFINITION_ID = "user-profile.automation-decline"
AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID = "user-profile.automation-inventory"

_HUMAN_DEFINITIONS = frozenset(
    {
        AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
        AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
        AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
    }
)
_REVIEWED_HUMAN_DEFINITIONS = frozenset(
    {AUTOMATION_APPROVE_OPERATION_DEFINITION_ID, AUTOMATION_DECLINE_OPERATION_DEFINITION_ID}
)

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


type AutomationAdministrationFactory = Callable[[OperationExecutorContext, UUID], AutomationAdministrationExecution]
type AutomationInventoryReader = Callable[[OperationExecutorContext, UUID], Awaitable[AutomationInventory]]


def _project_scope(scope: AccessScope) -> AutomationScopeProjection:
    return AutomationScopeProjection(
        operations=tuple(sorted(scope.operations)),
        actions=tuple(sorted(scope.actions)),
        disclosures=tuple(
            sorted(scope.disclosures, key=lambda item: (str(item.destination_id), item.projection_id, item.category))
        ),
        periods=None
        if scope.periods is None
        else tuple(
            AutomationPeriodProjection(filing_year=item.filing_year, code=str(item.code))
            for item in sorted(scope.periods, key=lambda item: (item.filing_year, str(item.code)))
        ),
        allow_period_independent=scope.allow_period_independent,
        allow_delegation=scope.allow_delegation,
    )


def project_automation_inventory_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the human-authorized inventory for the settled profile."""
    if not isinstance(result, AutomationInventory):
        raise TypeError("unexpected automation inventory result")
    subject = receipt.identity.subject_ref
    profile_ids = (
        *(item.profile_id for item in result.grants),
        *(item.profile_id for item in result.keys),
        *(item.receipt.profile_id for item in result.requests),
    )
    if any(profile_operation_subject(str(profile_id)) != subject for profile_id in profile_ids):
        raise ValueError("automation inventory does not match its settled subject")
    return AutomationInventoryProjection(
        grants=tuple(
            AutomationGrantProjection(
                grant_id=item.grant_id,
                profile_id=item.profile_id,
                client_id=item.client_id,
                state=item.state,
                scope=_project_scope(item.scope),
                valid_from=item.valid_from,
                expires_at=item.expires_at,
                unattended=item.unattended,
                allow_os_lock=item.allow_os_lock,
            )
            for item in result.grants
        ),
        keys=tuple(
            AutomationKeyProjection(
                key_id=item.key_id,
                grant_id=item.grant_id,
                profile_id=item.profile_id,
                state=item.state,
                valid_from=item.valid_from,
                expires_at=item.expires_at,
                last_used_at=item.last_used_at,
            )
            for item in result.keys
        ),
        requests=tuple(
            AutomationReviewProjection(
                receipt=AutomationReceiptProjection(
                    request_id=item.receipt.request_id,
                    profile_id=item.receipt.profile_id,
                    stage=item.receipt.stage,
                    review_digest=item.receipt.review_digest,
                    grant_id=item.receipt.grant_id,
                    key_id=item.receipt.key_id,
                    credential_reference=item.receipt.credential_reference,
                ),
                client_id=item.client_id,
                destination_id=item.destination_id,
                proposal=AutomationProposalProjection(
                    kind=item.proposal.kind,
                    scope=_project_scope(item.proposal.scope),
                    expires_at=item.proposal.expires_at,
                    key_expires_at=item.proposal.key_expires_at,
                    unattended=item.proposal.unattended,
                    allow_os_lock=item.proposal.allow_os_lock,
                    target_grant_id=item.proposal.target_grant_id,
                    target_key_id=item.proposal.target_key_id,
                ),
                expires_at=item.expires_at,
            )
            for item in result.requests
        ),
    )


def project_automation_enrollment_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only one settled human enrollment decision's nonsecret receipt."""
    if not isinstance(result, EnrollmentReceipt):
        raise TypeError("unexpected automation enrollment result")
    if profile_operation_subject(str(result.profile_id)) != receipt.identity.subject_ref:
        raise ValueError("automation receipt does not match its settled subject")
    return AutomationReceiptProjection.model_validate(result.model_dump())


class AutomationAdministrationRefusedError(CadrumoError):
    """Safe operation refusal; private adapter diagnostics never enter the journal."""


class _EnrollmentPublication:
    """Keep each publication and its effect recording under one operation owner."""

    def __init__(self, context: OperationExecutorContext, payload: AutomationOperationRequest) -> None:
        self.context, self.payload = context, payload
        self.published = False

    async def apply(
        self,
        publish: Callable[[], Awaitable[EnrollmentTransition | None]],
        *,
        terminal: bool,
        task_name: str,
    ) -> str | None:
        async def owned_publication() -> str | None:
            async with self.context.cancellation.irreversible_section():
                await self.context.events.effect(OperationEffect.UNKNOWN)
                transition = await publish()
                if transition is not None:
                    receipt = transition.receipt
                    if receipt.profile_id != self.payload.profile_id or receipt.request_id != self.payload.request_id:
                        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
                    self.published |= transition.published
                if terminal and transition is not None:
                    result_ref = await self.context.operands.put(transition.receipt, written_at=now())
                    await self.context.events.effect(
                        OperationEffect.UPDATED if self.published else OperationEffect.NONE
                    )
                    return result_ref
                if not self.published:
                    await self.context.events.effect(OperationEffect.NONE)
                # A staged candidate is not a completed approval. Keep its
                # effect UNKNOWN until activation and its receipt are durable.
                return None

        # Own the section, thread, effect and result write together. Cancelling
        # only the to_thread await can lose a successful publication's receipt.
        return await await_cancellation_complete(owned_publication(), task_name=task_name)


class AutomationAdministrationExecutor:
    """Dispatch real application services without accepting caller authority facts."""

    def __init__(
        self,
        factory: AutomationAdministrationFactory | None,
        inventory_reader: AutomationInventoryReader | None = None,
    ) -> None:
        """Retain only the trusted composition capability, never ambient authorization."""
        self.factory = factory
        self.inventory_reader = inventory_reader

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
        await context.events.phase(identity + ".execute")
        if identity == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID:
            if self.inventory_reader is not None:
                inventory = await await_cancellation_complete(
                    self.inventory_reader(context, payload.profile_id),
                    task_name="automation-inventory-reader",
                )
            else:
                if self.factory is None:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                service = self.factory(context, payload.profile_id)
                await await_cancellation_complete(
                    service.require_profile(payload.profile_id), task_name="automation-profile-binding"
                )
                inventory = await await_cancellation_complete(
                    service.inventory(), task_name="automation-inventory-service"
                )
            # Inventory is human-only private metadata in the existing encrypted
            # result store; observing an operation never grants new authority.
            if type(inventory) is not AutomationInventory:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            result_ref = await await_cancellation_complete(
                context.operands.put(inventory, written_at=now()), task_name="automation-inventory-result"
            )
            await context.events.effect(OperationEffect.NONE)
            return result_ref
        if self.factory is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        service = self.factory(context, payload.profile_id)
        await await_cancellation_complete(
            service.require_profile(payload.profile_id), task_name="automation-profile-binding"
        )
        publication = _EnrollmentPublication(context, payload)
        if identity in _PROPOSALS:
            async with context.ephemeral_secret.consume() as raw:
                try:
                    proposal = EnrollmentProposal.model_validate_json(bytes(raw))
                except ValidationError:
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
                if proposal.kind is not _PROPOSALS[identity]:
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID)
                result_ref = await publication.apply(
                    lambda: service.request(payload.request_id, proposal),
                    terminal=True,
                    task_name="automation-request-publication",
                )
        elif identity == AUTOMATION_APPROVE_OPERATION_DEFINITION_ID:
            if payload.review_digest is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            approval = service.approval(payload.request_id, review_digest=payload.review_digest)
            try:
                async with context.ephemeral_secret.consume() as raw:
                    await await_cancellation_complete(
                        approval.prepare(SecretBytes(bytes(raw))),
                        task_name="automation-approval-proof",
                    )
                result_ref = await publication.apply(
                    approval.commit_review, terminal=True, task_name="automation-approval-review"
                )
                if result_ref is None:
                    needs_candidate = await await_cancellation_complete(
                        approval.inspect_recipient(), task_name="automation-recipient-inspection"
                    )
                    if needs_candidate:
                        await publication.apply(
                            approval.publish_candidate, terminal=False, task_name="automation-candidate-publication"
                        )
                    await await_cancellation_complete(
                        approval.deliver_and_verify(), task_name="automation-protected-delivery"
                    )
                    result_ref = await publication.apply(
                        approval.activate, terminal=True, task_name="automation-activation"
                    )
            finally:
                await close_async_resources(approval, task_name="automation-approval-close")
        elif identity == AUTOMATION_DECLINE_OPERATION_DEFINITION_ID:
            review_digest = payload.review_digest
            if review_digest is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            result_ref = await publication.apply(
                lambda: service.decline(payload.request_id, review_digest=review_digest),
                terminal=True,
                task_name="automation-decline-publication",
            )
        else:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        if result_ref is None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return result_ref


def build_automation_operation_definitions(
    factory: AutomationAdministrationFactory | None = None,
    *,
    inventory_reader: AutomationInventoryReader | None = None,
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
                    build=lambda: AutomationAdministrationExecutor(factory, inventory_reader),
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
                permitted_frontends=(
                    frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
                    if identity in _HUMAN_DEFINITIONS
                    else frozenset(OperationFrontendProjection)
                ),
                ephemeral_secret=None
                if secret_kind is None
                else OperationEphemeralSecretDeclaration(secret_kind=secret_kind, lifetime=timedelta(minutes=5)),
            )
        )
    return tuple(result)


def build_automation_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Expose human inventory, approval and decline with safe typed results."""
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=item,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=item.definition_id + ".request", schema_version=1, model_type=item.request_type
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=item.definition_id + ".result",
                schema_version=1,
                model_type=AutomationInventoryProjection
                if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
                else AutomationReceiptProjection,
            )
            if item.definition_id in _HUMAN_DEFINITIONS
            else None,
            result_projector=project_automation_inventory_result
            if item.definition_id == AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
            else project_automation_enrollment_result
            if item.definition_id in _REVIEWED_HUMAN_DEFINITIONS
            else None,
            access_resolver=resolve_automation_human_access if item.definition_id in _HUMAN_DEFINITIONS else None,
        )
        for item in definitions
    )


def resolve_automation_human_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact human profile authority for inventory and reviewed decisions."""
    payload = request.payload
    if not isinstance(payload, AutomationOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        request.definition_id not in _HUMAN_DEFINITIONS
        or payload.profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(payload.profile_id))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if request.definition_id in _REVIEWED_HUMAN_DEFINITIONS and payload.review_digest is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT and context.contract.result_schema is not None:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=context.contract.result_schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )
