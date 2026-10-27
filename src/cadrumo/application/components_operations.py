"""Profile-admitted component reads and digest-bound, human-reviewed setup.

The native engine owns component state and the installation-wide files. These
operations own admission, the journal, review, cancellation and effect facts.
The port speaks application contracts; native wire types stay in composition.
"""

from __future__ import annotations

import secrets
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field, NonNegativeInt

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.errors.hierarchy import CadrumoError
from ..core.hashing import sha256_hex
from ..core.hex import Hex64Str
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..core.time.clock import now
from .dependency_contracts import (
    DependencyHostName,
    DependencyItemId,
    DependencyItemKind,
    DependencySetupStep,
    DependencyStatusRow,
)
from .operations.access_resolution import (
    COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    OBSERVATION_DISCLOSING_ACTIONS,
    OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
)
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.interactions import OperationConsumedInteraction, OperationResponseIntentValue
from .operations.models import CredentialFreeOperationRequest, OperationRequest
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from .operations.persistence.journal import serialize_operation_operand
from .operations.person_acts import is_persons_frontend
from .operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from .operations.subject_reference import OperationSubjectReferenceV1
from .user_profile.access_errors import ProfileAccessRefusedError

COMPONENTS_OPERATION_SUBJECT = "components:installation"
COMPONENTS_STATUS_OPERATION_ID = "config.provision.status"
COMPONENTS_VERIFY_OPERATION_ID = "config.provision.verify"
COMPONENTS_SETUP_OPERATION_ID = "config.provision.setup"
COMPONENTS_REMOVE_OPERATION_ID = "config.provision.remove"


class ProvisionCommand(StrEnum):
    """The application acts delegated to the component engine."""

    STATUS = "status"
    VERIFY = "verify"
    PLAN = "plan"
    SETUP = "setup"
    REMOVE = "remove"


class ProvisionOutcome(StrEnum):
    """Closed engine outcomes and the explicit rejection of a review."""

    OK = "ok"
    NOTHING_TO_DO = "nothing_to_do"
    COMPLETED = "completed"
    NEEDS_APPROVAL = "needs_approval"
    PLAN_CHANGED = "plan_changed"
    BUSY = "busy"
    REFUSED = "refused"
    FAILED = "failed"
    FOLLOWED_PLAN_MISMATCH = "followed_plan_mismatch"
    CANCELLED = "cancelled"
    REMOVED = "removed"
    REJECTED = "rejected"
    INVALID_REQUEST = "invalid_request"


class ProvisionReadRequest(CredentialFreeOperationRequest):
    """Read every item, or the explicitly named items."""

    items: tuple[DependencyItemKind, ...] = Field(default=(), max_length=2)


class ProvisionMutationRequest(CredentialFreeOperationRequest):
    """Python changes only the browser; local AI remains desktop-owned."""

    items: tuple[Literal[DependencyItemKind.BROWSER], ...] = Field(
        default=(DependencyItemKind.BROWSER,),
        min_length=1,
        max_length=1,
    )


class ProvisionPlanPart(BaseModel):
    """One downloadable part and the destinations the person reviews."""

    model_config = STRICT_FROZEN_CONFIG
    part_id: str = Field(min_length=1, max_length=64)
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...]
    destination: Literal["playwright-browsers", "ollama-models", "local-ai-program"] | None
    installs_outside_program: bool
    target_version: str | None


class ProvisionPlanEntry(BaseModel):
    """One installation item in the proposed plan."""

    model_config = STRICT_FROZEN_CONFIG
    item_id: DependencyItemId
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...]
    destination: Literal["playwright-browsers", "ollama-models", "local-ai-program"] | None
    installs_outside_program: bool
    target_version: str | None
    parts: tuple[ProvisionPlanPart, ...]


class ProvisionPlanSpace(BaseModel):
    """The engine observation of storage required by the plan."""

    model_config = STRICT_FROZEN_CONFIG
    free_bytes: NonNegativeInt | None
    required_bytes: NonNegativeInt
    sufficient: bool


class ProvisionPlan(BaseModel):
    """Installation facts presented to the person, separate from wire framing."""

    model_config = STRICT_FROZEN_CONFIG
    contract_version: Literal[3]
    entries: tuple[ProvisionPlanEntry, ...] = Field(min_length=1)
    known_download_bytes: NonNegativeInt
    has_unknown_size: bool
    installs_outside_program: bool
    space: ProvisionPlanSpace


class ProvisionResult(BaseModel):
    """The engine's closed outcome and renderer-neutral component rows."""

    model_config = STRICT_FROZEN_CONFIG
    outcome: ProvisionOutcome
    rows: tuple[DependencyStatusRow, ...] = ()
    setup_complete: bool | None = None
    plan: ProvisionPlan | None = None
    plan_digest: Hex64Str | None = None
    failure_category: DependencyFailureCategory | None = None
    item_id: DependencyItemId | None = None
    items: tuple[DependencyItemId, ...] | None = None


class ProvisionReviewedOperand(BaseModel):
    """The role's exact plan and digest, kept across the one review checkpoint."""

    model_config = STRICT_FROZEN_CONFIG
    items: tuple[Literal[DependencyItemKind.BROWSER], ...]
    plan: ProvisionPlan
    plan_digest: Hex64Str


class ProvisionReviewProjection(BaseModel):
    """Bearer-free view of the exact proposal the person may answer."""

    model_config = STRICT_FROZEN_CONFIG
    projection_version: Literal[1] = 1
    reviewed_proposal_digest: Hex64Str
    plan: ProvisionPlan
    plan_digest: Hex64Str


class ProvisionReviewResponse(BaseModel):
    """A public intent carrying no response authority itself."""

    model_config = STRICT_FROZEN_CONFIG
    response_version: Literal[1]
    intent: OperationResponseIntentValue


PROVISION_REVIEW_SCHEMA = OperationSchemaBindingV1.bind(
    schema_id=COMPONENTS_SETUP_OPERATION_ID + ".review",
    schema_version=1,
    model_type=ProvisionReviewProjection,
)
PROVISION_RESPONSE_SCHEMA = OperationSchemaBindingV1.bind(
    schema_id=COMPONENTS_SETUP_OPERATION_ID + ".response",
    schema_version=1,
    model_type=ProvisionReviewResponse,
)


class ComponentsOperationRefusedError(CadrumoError):
    """A closed role refusal; plan drift requires a new reviewed invocation."""

    def __init__(self, outcome: ProvisionOutcome, *, result: ProvisionResult | None = None) -> None:
        """Bind the declared collaborators without starting any work."""
        super().__init__(
            context={
                "outcome": outcome.value,
                "new_setup_required": outcome
                in {
                    ProvisionOutcome.PLAN_CHANGED,
                    ProvisionOutcome.FOLLOWED_PLAN_MISMATCH,
                },
                **({} if result is None else result.model_dump(mode="json", exclude_none=True)),
            },
            translated_message=(
                "cli.config.provision.outcome.plan_changed"
                if outcome is ProvisionOutcome.PLAN_CHANGED
                else "cli.config.provision.outcome.followed_plan_mismatch"
                if outcome is ProvisionOutcome.FOLLOWED_PLAN_MISMATCH
                else None
            ),
        )


class ComponentsOperationPort(Protocol):
    """The composition-owned component role, held through terminal cleanup."""

    async def run(
        self,
        command: ProvisionCommand,
        items: tuple[DependencyItemKind, ...],
        context: OperationExecutorContext,
        *,
        approve: str | None = None,
    ) -> ProvisionResult:
        """Own one role until terminal/safe cleanup, relaying its events to the context."""
        ...


async def _cancelled(context: OperationExecutorContext) -> bool:
    if context.cancellation.cancellation_requested:
        await context.cancellation.acknowledge_cancellation()
        return True
    return False


async def _result(result: ProvisionResult, context: OperationExecutorContext) -> str:
    return await context.operands.put(result, written_at=now())


async def _mutation_result(result: ProvisionResult, context: OperationExecutorContext) -> str | None:
    if result.outcome in {ProvisionOutcome.COMPLETED, ProvisionOutcome.REMOVED}:
        await context.events.effect(OperationEffect.UPDATED)
    elif result.outcome in {
        ProvisionOutcome.NOTHING_TO_DO,
        ProvisionOutcome.PLAN_CHANGED,
        ProvisionOutcome.NEEDS_APPROVAL,
        ProvisionOutcome.INVALID_REQUEST,
        ProvisionOutcome.REFUSED,
    }:
        await context.events.effect(OperationEffect.NONE)
    if await _cancelled(context):
        return None
    if result.outcome not in {ProvisionOutcome.COMPLETED, ProvisionOutcome.REMOVED, ProvisionOutcome.NOTHING_TO_DO}:
        raise ComponentsOperationRefusedError(result.outcome, result=result)
    return await _result(result, context)


class ComponentsReadExecutor:
    """Read component facts without changing installed state."""

    def __init__(self, port: ComponentsOperationPort, command: ProvisionCommand) -> None:
        """Bind the declared collaborators without starting any work."""
        self.port, self.command = port, command

    async def execute(
        self, request: OperationRequest[ProvisionReadRequest], context: OperationExecutorContext
    ) -> str | None:
        """Run the declared act and store its typed result through the supervisor."""
        if await _cancelled(context):
            return None
        result = await self.port.run(self.command, request.payload.items, context)
        if await _cancelled(context):
            return None
        return await _result(result, context)


class ComponentsRemoveExecutor:
    """Remove browser files under operation commit authority."""

    def __init__(self, port: ComponentsOperationPort) -> None:
        """Bind the declared collaborators without starting any work."""
        self.port = port

    async def execute(
        self, request: OperationRequest[ProvisionMutationRequest], context: OperationExecutorContext
    ) -> str | None:
        """Run the declared act and store its typed result through the supervisor."""
        if await _cancelled(context):
            return None
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            result = await self.port.run(ProvisionCommand.REMOVE, request.payload.items, context)
        return await _mutation_result(result, context)


class ComponentsSetupExecutor:
    """Publish one engine plan and apply only its reviewed digest."""

    def __init__(self, port: ComponentsOperationPort) -> None:
        """Bind the declared collaborators without starting any work."""
        self.port = port

    async def execute(
        self, request: OperationRequest[ProvisionMutationRequest], context: OperationExecutorContext
    ) -> str | None:
        """Run the declared act and store its typed result through the supervisor."""
        if await _cancelled(context):
            return None
        planned = await self.port.run(ProvisionCommand.PLAN, request.payload.items, context)
        if await _cancelled(context):
            return None
        if planned.outcome is ProvisionOutcome.NOTHING_TO_DO:
            return await _result(planned, context)
        if planned.outcome is not ProvisionOutcome.OK or planned.plan is None or planned.plan_digest is None:
            raise ComponentsOperationRefusedError(planned.outcome, result=planned)
        operand = ProvisionReviewedOperand(
            items=request.payload.items, plan=planned.plan, plan_digest=planned.plan_digest
        )
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=context.revision + 1,
            presentation_code="config.provision.review",
            response_schema_ref=operation_public_schema_reference(PROVISION_RESPONSE_SCHEMA.identity),
            continuation_digest=sha256_hex(serialize_operation_operand(operand)),
            expires_at=None,
            reviewed_operand=operand,
            baseline_digest=operand.plan_digest,
            proposed_effect_digest=operand.plan_digest,
        )
        return None

    async def resume(
        self,
        request: OperationRequest[ProvisionMutationRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> str | None:
        """Consume an exact review without replaying an uncertain apply."""
        del request
        if not checkpoint.consumed or await _cancelled(context):
            return None
        if context.effect is not OperationEffect.NONE:
            raise ComponentsOperationRefusedError(ProvisionOutcome.FAILED)
        if not isinstance(checkpoint, OperationConsumedInteraction):
            raise ComponentsOperationRefusedError(ProvisionOutcome.REFUSED)
        pending = checkpoint.checkpoint
        claim = pending.review_claim
        if (
            claim is None
            or pending.request.identity != context.identity
            or pending.request.revision != claim.displayed_revision + 1
        ):
            raise ComponentsOperationRefusedError(ProvisionOutcome.REFUSED)
        operand = await context.operands.resolve(checkpoint.reviewed_proposal_digest, ProvisionReviewedOperand)
        if (
            pending.request.continuation_digest != sha256_hex(serialize_operation_operand(operand))
            or pending.baseline_digest != operand.plan_digest
            or pending.proposed_effect_digest != operand.plan_digest
        ):
            raise ComponentsOperationRefusedError(ProvisionOutcome.REFUSED)
        if checkpoint.response_action == "reject":
            await context.events.effect(OperationEffect.NONE)
            return await _result(
                ProvisionResult(outcome=ProvisionOutcome.REJECTED, plan_digest=operand.plan_digest), context
            )
        # A consumed continuation whose previous owner entered apply must never
        # blindly replay installation. Its uncertain effect is durable evidence.
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            result = await self.port.run(ProvisionCommand.SETUP, operand.items, context, approve=operand.plan_digest)
        return await _mutation_result(result, context)


def resolve_components_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind profile authority and require a person only for setup response actions."""
    definition_id = request.definition_id
    setup = definition_id == COMPONENTS_SETUP_OPERATION_ID
    mutation = setup or definition_id == COMPONENTS_REMOVE_OPERATION_ID
    expected = ProvisionMutationRequest if mutation else ProvisionReadRequest
    if (
        definition_id not in _COMMANDS
        or not isinstance(request.payload, expected)
        or request.subject_ref != COMPONENTS_OPERATION_SUBJECT
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    response = setup and context.action is AccessAction.RESPOND
    if response and not is_persons_frontend(context.frontend):
        raise ProfileAccessRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED)
    if setup and context.action in {AccessAction.REVIEW, AccessAction.RESPOND}:
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=PROVISION_REVIEW_SCHEMA.identity.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES,)
        )
    else:
        disclosures = operation_disclosures(
            context,
            observed_by=OBSERVATION_DISCLOSING_ACTIONS,
            result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
            result_schema_id=None,
        )
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=definition_id,
        actions=(COMMITTING_OPERATION_LIFECYCLE_ACTIONS if mutation else OPERATION_LIFECYCLE_ACTIONS)
        | (frozenset({AccessAction.REVIEW, AccessAction.RESPOND}) if setup else frozenset[AccessAction]()),
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=response,
        provider=Availability.NOT_REQUIRED,
    )


_COMMANDS = {
    COMPONENTS_STATUS_OPERATION_ID: ProvisionCommand.STATUS,
    COMPONENTS_VERIFY_OPERATION_ID: ProvisionCommand.VERIFY,
    COMPONENTS_SETUP_OPERATION_ID: ProvisionCommand.SETUP,
    COMPONENTS_REMOVE_OPERATION_ID: ProvisionCommand.REMOVE,
}


def build_components_definitions(port: ComponentsOperationPort) -> tuple[OperationDefinition, ...]:
    """Declare four operations with truthful effects and process ownership."""
    definitions: list[OperationDefinition] = []
    for definition_id, command in sorted(_COMMANDS.items()):
        setup = command is ProvisionCommand.SETUP
        mutation = command in {ProvisionCommand.SETUP, ProvisionCommand.REMOVE}
        request_type = ProvisionMutationRequest if mutation else ProvisionReadRequest
        executor_type = (
            ComponentsSetupExecutor if setup else ComponentsRemoveExecutor if mutation else ComponentsReadExecutor
        )

        def build(
            command: ProvisionCommand = command,
        ) -> ComponentsSetupExecutor | ComponentsRemoveExecutor | ComponentsReadExecutor:
            if command is ProvisionCommand.SETUP:
                return ComponentsSetupExecutor(port)
            if command is ProvisionCommand.REMOVE:
                return ComponentsRemoveExecutor(port)
            return ComponentsReadExecutor(port, command)

        capabilities = OperationCapabilities(
            durability=OperationDurability.RESUMABLE if setup else OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.RESUMABLE if setup else OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL if setup else OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE
            if setup
            else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE
            if setup
            else OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED})
            if mutation
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        )
        definitions.append(
            OperationDefinition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=ProvisionResult,
                subject_reference=OperationSubjectReferenceV1.fixed(COMPONENTS_OPERATION_SUBJECT),
                executor_factory=OperationExecutorFactory(
                    request_type=request_type, executor_type=executor_type, build=build
                ),
                phase_codes=(
                    definition_id,
                    *(
                        f"dependencies.setup.{item.value}.{step.value}"
                        for item in DependencyItemKind
                        for step in DependencySetupStep
                    ),
                ),
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}) if setup else frozenset(),
                capabilities=capabilities,
                reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
                if setup
                else OperationReconciliationPolicy.INTERRUPT,
                public_error_detail=True,
            )
        )
    return tuple(definitions)


def _review_projection(operand: BaseModel, interaction: object) -> BaseModel:
    del interaction
    reviewed = ProvisionReviewedOperand.model_validate(operand, strict=True)
    return ProvisionReviewProjection(
        reviewed_proposal_digest=sha256_hex(serialize_operation_operand(reviewed)),
        plan=reviewed.plan,
        plan_digest=reviewed.plan_digest,
    )


def build_components_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the public result and setup review schemas."""
    if definition.definition_id != COMPONENTS_SETUP_OPERATION_ID:
        return OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition, public_result_type=ProvisionResult, access_resolver=resolve_components_access
        )
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ProvisionMutationRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ProvisionResult
        ),
        review_projection_schema=PROVISION_REVIEW_SCHEMA,
        interaction_response_schema=PROVISION_RESPONSE_SCHEMA,
        reviewed_operand_type=ProvisionReviewedOperand,
        review_projector=_review_projection,
        access_resolver=resolve_components_access,
    )
