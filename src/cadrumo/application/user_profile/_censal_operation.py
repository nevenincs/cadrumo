"""Resumable censo acquisition, exact review, and cotejo application."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    content_hash_hex,
    require_active_bucket_id,
)
from ...core.async_cleanup import AsyncCloseable
from ...core.identity import ContentDigest, ContentDigestOrAbsent, ProfileId
from ...domain.user_profile import UserProfileRecord
from ..operations import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationOwnedResource,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSchemaBindingV1,
    OperationSensitiveInputPolicy,
    operation_public_schema_reference,
)
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ._capsule_record import ProfileRecordConflictError
from ._censal_observation import CensalObservation
from ._censo_sync import (
    CENSAL_ADOPTABLE_PATHS,
    CENSO_SOURCE_TAG,
    censal_facts_from_read,
    reconcile_censal_read,
)
from ._cotejo_apply import apply_cotejo
from ._profile_record_repository import ProfileRecordRepository
from ._projections import record_to_effective_facts

CENSAL_OPERATION_DEFINITION_ID = "user-profile.censo-review"
CENSAL_PHASE_PREFLIGHT = "censo.preflight"
CENSAL_PHASE_CLAVE_DEVICE_WAIT = "censo.clave-device-wait"
CENSAL_PHASE_REMOTE_READ = "censo.remote-read"
CENSAL_PHASE_PROPOSAL = "censo.proposal"
CENSAL_PHASE_INTERACTION_WAIT = "censo.interaction-wait"
CENSAL_PHASE_APPLY = "censo.apply"
CENSAL_PHASE_REJECT = "censo.reject"
CENSAL_PHASE_SETTLEMENT = "censo.settlement"
_CENSAL_PHASES = (
    CENSAL_PHASE_PREFLIGHT,
    CENSAL_PHASE_CLAVE_DEVICE_WAIT,
    CENSAL_PHASE_REMOTE_READ,
    CENSAL_PHASE_PROPOSAL,
    CENSAL_PHASE_INTERACTION_WAIT,
    CENSAL_PHASE_APPLY,
    CENSAL_PHASE_REJECT,
    CENSAL_PHASE_SETTLEMENT,
)


class CensalFieldIntent(StrEnum):
    """Closed operator intent for one reviewed censo-derived profile field."""

    ADOPT = "adopt"
    PRESERVE = "preserve"


class CensalReviewedFieldIntent(BaseModel):
    """One exact field decision retained with the reviewed observation."""

    model_config = STRICT_FROZEN_CONFIG

    path: str = Field(min_length=3, max_length=160)
    intent: CensalFieldIntent

    @field_validator("path")
    @classmethod
    def _require_adoptable_path(cls, value: str) -> str:
        if value not in CENSAL_ADOPTABLE_PATHS:
            raise ValueError("censal field intent must target a canonical adoptable profile path")
        return value


class CensalProfileBaseline(BaseModel):
    """Exact immutable profile revision against which the proposal was reviewed."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest

    @classmethod
    def from_record(cls, record: UserProfileRecord) -> CensalProfileBaseline:
        """Capture the canonical revision and self-verifying content digest."""
        return cls(
            profile_id=record.profile_id,
            record_revision=record.record_revision,
            content_digest=record.content_digest,
        )


#: Wire version of the reviewed-operand record. Named rather than written as a
#: bare default so the number has one home: a reader can find every site bound
#: to this shape, and a bump cannot land on the model while a writer stamping
#: the old number silently disagrees with it.
CENSAL_REVIEWED_OPERAND_SCHEMA_VERSION: Final[int] = 1


class CensalReviewedOperand(BaseModel):
    """Encrypted exact preimage approved or rejected by the operator."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    schema_version: Literal[1] = CENSAL_REVIEWED_OPERAND_SCHEMA_VERSION
    observation: CensalObservation
    baseline: CensalProfileBaseline
    field_intents: tuple[CensalReviewedFieldIntent, ...]
    proposed_effect_digest: ContentDigestOrAbsent = ""

    @field_validator("field_intents")
    @classmethod
    def _require_unique_field_intents(
        cls,
        value: tuple[CensalReviewedFieldIntent, ...],
    ) -> tuple[CensalReviewedFieldIntent, ...]:
        paths = tuple(item.path for item in value)
        if paths != CENSAL_ADOPTABLE_PATHS:
            raise ValueError(
                "censal reviewed operand field intents must cover every canonical "
                "adoptable path exactly once and in canonical order"
            )
        return value

    @model_validator(mode="after")
    def _bind_proposed_effect(self) -> CensalReviewedOperand:
        expected = self._expected_proposed_effect_digest()
        if not self.proposed_effect_digest:
            object.__setattr__(self, "proposed_effect_digest", expected)
        elif self.proposed_effect_digest != expected:
            raise ValueError("censal proposed-effect digest does not match the reviewed operand")
        return self

    def _expected_proposed_effect_digest(self) -> ContentDigest:
        return content_hash_hex(
            self.model_dump(
                mode="json",
                exclude={"proposed_effect_digest"},
                exclude_defaults=False,
                exclude_none=False,
                exclude_unset=False,
            )
        )


class CensalOperationRequest(BaseModel):
    """Exact preflight baseline and review choices with no bearer material."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: CensalProfileBaseline
    field_intents: tuple[CensalReviewedFieldIntent, ...]

    @field_validator("field_intents")
    @classmethod
    def _require_complete_intents(
        cls, value: tuple[CensalReviewedFieldIntent, ...]
    ) -> tuple[CensalReviewedFieldIntent, ...]:
        if tuple(item.path for item in value) != CENSAL_ADOPTABLE_PATHS:
            raise ValueError("censal operation request must decide every adoptable path in canonical order")
        return value


def build_censal_operation_request(record: UserProfileRecord) -> CensalOperationRequest:
    """Bind the exact baseline and safe per-field defaults for frontend review."""
    effective = record_to_effective_facts(record)
    return CensalOperationRequest(
        baseline=CensalProfileBaseline.from_record(record),
        field_intents=tuple(
            CensalReviewedFieldIntent(
                path=path,
                intent=(
                    CensalFieldIntent.ADOPT
                    if (current := effective.get(path)) is None or current.source == CENSO_SOURCE_TAG
                    else CensalFieldIntent.PRESERVE
                ),
            )
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )


class CensalOperationOutcome(StrEnum):
    """Settled domain outcome represented by the executor result reference."""

    APPLIED = "applied"
    REJECTED = "rejected"


class CensalOperationResult(BaseModel):
    """Typed schema for the safe result referenced by a completed continuation."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: CensalOperationOutcome
    reviewed_proposal_digest: ContentDigest


class CensalReviewResponse(BaseModel):
    """Authority-free public decision submitted for a censal REVIEW."""

    model_config = STRICT_FROZEN_CONFIG

    response_version: Literal[1]
    intent: Literal["apply", "reject"]


class CensalReviewFieldProjectionV1(BaseModel):
    """One safe censo field displayed for an exact REVIEW decision."""

    model_config = STRICT_FROZEN_CONFIG

    path: str = Field(min_length=3, max_length=160)
    intent: CensalFieldIntent
    observed_value: str | None


class CensalReviewProjectionV1(BaseModel):
    """Bearer-free public projection of the encrypted censal proposal."""

    model_config = STRICT_FROZEN_CONFIG

    projection_version: Literal[1]
    fields: tuple[CensalReviewFieldProjectionV1, ...]


CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id="user-profile.censo-review.response",
    schema_version=1,
    model_type=CensalReviewResponse,
)

CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id="user-profile.censo-review.projection",
    schema_version=1,
    model_type=CensalReviewProjectionV1,
)


def _project_censal_review(
    operand: BaseModel,
    interaction: object,
) -> BaseModel:
    """Project only reviewed field values; discard custody and bearer facts."""
    del interaction
    reviewed = CensalReviewedOperand.model_validate(operand, strict=True)
    observed = {fact.path: str(fact.value) for fact in censal_facts_from_read(reviewed.observation)}
    return CensalReviewProjectionV1(
        projection_version=1,
        fields=tuple(
            CensalReviewFieldProjectionV1(
                path=item.path,
                intent=item.intent,
                observed_value=observed.get(item.path),
            )
            for item in reviewed.field_intents
        ),
    )


def build_censal_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the canonical censal definition to its public REVIEW contract."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="user-profile.censo-review.request",
            schema_version=1,
            model_type=CensalOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="user-profile.censo-review.result",
            schema_version=1,
            model_type=CensalOperationResult,
        ),
        review_projection_schema=CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
        interaction_response_schema=CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
        reviewed_operand_type=CensalReviewedOperand,
        review_projector=_project_censal_review,
    )


@dataclass(frozen=True, slots=True)
class CensalOperationAcquisition:
    """Completed read plus its idempotently closeable acquisition resource."""

    observation: CensalObservation
    resource: AsyncCloseable | None = None


def _load_exact_baseline(request: OperationRequest[CensalOperationRequest]) -> UserProfileRecord:
    profile_id = require_active_bucket_id()
    baseline = request.payload.baseline
    if request.subject_ref != str(baseline.profile_id) or profile_id != str(baseline.profile_id):
        raise ProfileRecordConflictError("censal operation baseline does not identify the active profile")
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    if (
        record.profile_id != baseline.profile_id
        or record.record_revision != baseline.record_revision
        or record.content_digest != baseline.content_digest
    ):
        raise ProfileRecordConflictError("censal operation baseline is stale")
    return record


async def _acknowledge_if_cancelled(context: OperationExecutorContext) -> bool:
    if not context.cancellation.cancellation_requested:
        return False
    await context.cancellation.acknowledge_cancellation()
    return True


class CensalOperationExecutor:
    """Acquire once, publish one durable review, and resume only from it."""

    def __init__(
        self,
        *,
        acquire: Callable[[], Awaitable[CensalObservation | CensalOperationAcquisition]] | None = None,
        apply: Callable[[CensalReviewedOperand], None] | None = None,
        before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._acquire = acquire or _pull_censal_datos
        self._apply = apply or _apply_reviewed_cotejo
        self._before_irreversible_section = before_irreversible_section or _ready_for_irreversible_section

    async def execute(
        self,
        request: OperationRequest[CensalOperationRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        if await _acknowledge_if_cancelled(context):
            return None
        await context.events.phase(CENSAL_PHASE_PREFLIGHT)
        record = _load_exact_baseline(request)
        if await _acknowledge_if_cancelled(context):
            return None
        await context.events.phase(CENSAL_PHASE_CLAVE_DEVICE_WAIT)
        await context.events.phase(CENSAL_PHASE_REMOTE_READ)
        acquired = await self._acquire()
        if isinstance(acquired, CensalOperationAcquisition):
            observation = acquired.observation
            if acquired.resource is not None:
                context.cleanup.own(acquired.resource, family=OperationOwnedResource.ASYNC_TASK)
                # Resume consumes only the durable operand, so a process-local
                # acquisition handle must be released before the detachable
                # review is published. Supervisor ownership remains the retry
                # path when this idempotent close does not complete.
                await acquired.resource.close()
        else:
            observation = acquired
        if await _acknowledge_if_cancelled(context):
            return None
        await context.events.phase(CENSAL_PHASE_PROPOSAL)
        current = _load_exact_baseline(request)
        reconcile_censal_read(
            current,
            censal_facts_from_read(observation),
            incoming_identity=observation.identity.nif,
        )
        operand = CensalReviewedOperand(
            observation=observation,
            baseline=CensalProfileBaseline.from_record(record),
            field_intents=request.payload.field_intents,
        )
        await context.events.phase(CENSAL_PHASE_INTERACTION_WAIT)
        continuation_digest = content_hash_hex(
            {
                "schema_version": 1,
                "operation_id": context.identity.operation_id,
                "proposed_effect_digest": operand.proposed_effect_digest,
            }
        )
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=context.revision + 1,
            presentation_code="censo.review.ready",
            response_schema_ref=operation_public_schema_reference(CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity),
            continuation_digest=continuation_digest,
            expires_at=None,
            reviewed_operand=operand,
            baseline_digest=content_hash_hex(operand.baseline.model_dump(mode="json")),
            proposed_effect_digest=operand.proposed_effect_digest,
        )
        return None

    async def resume(
        self,
        request: OperationRequest[CensalOperationRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        if await _acknowledge_if_cancelled(context):
            return None
        if not checkpoint.consumed:
            return None
        proposal_digest = checkpoint.reviewed_proposal_digest
        operand = await context.operands.resolve(proposal_digest, CensalReviewedOperand)
        if checkpoint.response_action == "reject":
            await context.events.phase(CENSAL_PHASE_REJECT)
            await context.events.effect(OperationEffect.NONE)
            await context.events.phase(CENSAL_PHASE_SETTLEMENT)
            return f"censo-review:{proposal_digest}:{CensalOperationOutcome.REJECTED.value}"
        await context.events.phase(CENSAL_PHASE_APPLY)
        if await _acknowledge_if_cancelled(context):
            return None
        _require_current_operand_baseline(operand)
        await self._before_irreversible_section()
        entered_irreversible_section = False
        stale_conflict: ProfileRecordConflictError | None = None
        try:
            async with context.cancellation.irreversible_section():
                entered_irreversible_section = True
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    self._apply(operand)
                except ProfileRecordConflictError as exc:
                    stale_conflict = exc
        except ValueError:
            if not entered_irreversible_section and context.cancellation.cancellation_requested:
                await context.cancellation.acknowledge_cancellation()
                return None
            raise
        if stale_conflict is not None:
            await context.events.effect(OperationEffect.NONE)
            raise stale_conflict
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(CENSAL_PHASE_SETTLEMENT)
        return f"censo-review:{proposal_digest}:{CensalOperationOutcome.APPLIED.value}"


async def _pull_censal_datos() -> CensalObservation:
    """Acquire through the sole public live application door."""
    from ..live import pull_censal_datos

    observation = await pull_censal_datos()
    if not isinstance(observation, CensalObservation):
        raise TypeError("censal acquisition returned an invalid observation")
    return observation


def _require_current_operand_baseline(operand: CensalReviewedOperand) -> None:
    """Keep proven stale state at NONE before entering the ambiguous write window."""
    profile_id = require_active_bucket_id()
    baseline = operand.baseline
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    if (
        profile_id != str(baseline.profile_id)
        or record.profile_id != baseline.profile_id
        or record.record_revision != baseline.record_revision
        or record.content_digest != baseline.content_digest
    ):
        raise ProfileRecordConflictError("reviewed censal proposal baseline is stale")


def _apply_reviewed_cotejo(operand: CensalReviewedOperand) -> None:
    """Delegate to the sole exact censal mutation authority."""
    apply_cotejo(None, reviewed_proposal=operand)


async def _ready_for_irreversible_section() -> None:
    """Default non-blocking boundary before irreversible profile apply."""


def build_censal_operation_definition(
    *,
    acquire: Callable[[], Awaitable[CensalObservation | CensalOperationAcquisition]] | None = None,
    apply: Callable[[CensalReviewedOperand], None] | None = None,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
) -> OperationDefinition:
    """Build the one CENSO registration with its outer live authorities bound."""

    def build() -> CensalOperationExecutor:
        return CensalOperationExecutor(
            acquire=acquire,
            apply=apply,
            before_irreversible_section=before_irreversible_section,
        )

    return OperationDefinition(
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        request_type=CensalOperationRequest,
        result_type=CensalOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CensalOperationRequest,
            executor_type=CensalOperationExecutor,
            build=build,
        ),
        phase_codes=_CENSAL_PHASES,
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RESUMABLE,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.RESUMABLE,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
    )


CENSAL_OPERATION_DEFINITION = build_censal_operation_definition()


__all__ = [
    "CENSAL_OPERATION_DEFINITION",
    "CENSAL_OPERATION_DEFINITION_ID",
    "CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING",
    "CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING",
    "CensalFieldIntent",
    "CensalOperationAcquisition",
    "CensalOperationExecutor",
    "CensalOperationOutcome",
    "CensalOperationRequest",
    "CensalOperationResult",
    "CensalProfileBaseline",
    "CensalReviewFieldProjectionV1",
    "CensalReviewProjectionV1",
    "CensalReviewResponse",
    "CensalReviewedFieldIntent",
    "CensalReviewedOperand",
    "build_censal_operation_definition",
    "build_censal_operation_registration",
    "build_censal_operation_request",
]
