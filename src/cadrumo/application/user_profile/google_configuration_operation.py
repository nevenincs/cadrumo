"""Human Google configuration through exact-profile registered worker authority."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes, content_hash_hex
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.interactions import OperationConsumedInteraction, OperationInteractionRequest
from ..operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from .access_errors import ProfileAccessRefusedError
from .google_configuration_operation_contracts import (
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID,
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_INPUT_KIND,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConfigurationRequest,
    GoogleConsentProposal,
    GoogleConsentResponse,
    GoogleConsentReviewProjection,
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from .google_configuration_operation_ports import GoogleConfigurationOperationPortsFactory
from .google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationRefusalProjection,
    GoogleConfigurationRefusedError,
)

_CONTRACTS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID: (
        GoogleCredentialSourceSetRequest,
        GoogleCredentialSourceSetProjection,
    ),
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID: (
        GoogleCredentialSourceViewRequest,
        GoogleCredentialSourceViewProjection,
    ),
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID: (GoogleFolderSetRequest, GoogleFolderSetProjection),
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID: (GoogleFolderViewRequest, GoogleFolderViewProjection),
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID: (GoogleLoginRequest, GoogleLoginProjection),
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID: (GoogleLogoutRequest, GoogleLogoutProjection),
    GOOGLE_PROBE_OPERATION_DEFINITION_ID: (GoogleProbeRequest, GoogleProbeProjection),
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID: (GoogleRegisterRequest, GoogleRegisterProjection),
    GOOGLE_STATUS_OPERATION_DEFINITION_ID: (GoogleStatusRequest, GoogleStatusProjection),
}
_REQUEST_TYPES = (
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetRequest,
    GoogleFolderViewRequest,
    GoogleLoginRequest,
    GoogleLogoutRequest,
    GoogleProbeRequest,
    GoogleRegisterRequest,
    GoogleStatusRequest,
)
GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".review",
    schema_version=1,
    model_type=GoogleConsentReviewProjection,
)
GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".response", schema_version=1, model_type=GoogleConsentResponse
)


class GoogleConfigurationExecutionResult(BaseModel):
    """Encrypted complete result bound to the actual invocation and effect."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    projection: GoogleConfigurationOutcome
    effect: Literal["none", "updated", "partial", "unknown"]


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> GoogleConfigurationRequest:
    pair = _CONTRACTS.get(request.definition_id)
    payload = request.payload
    if pair is None or type(payload) is not pair[0] or not isinstance(payload, _REQUEST_TYPES):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
        or request.subject_ref != profile_operation_subject(str(payload.profile_id))
        or require_active_bucket_id() != str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


class GoogleConfigurationExecutor:
    """Admit every boundary separately and wait for owned work before settlement."""

    def __init__(self, factory: GoogleConfigurationOperationPortsFactory) -> None:
        """Bind the canonical owning services without constructing credentials."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Run ordinary leaves; consent first yields its exact human checkpoint."""
        payload = _require_profile(request, context)
        await context.events.phase(request.definition_id)
        await context.events.effect(OperationEffect.NONE)
        if isinstance(payload, GoogleLoginRequest) and not payload.refresh_only:
            try:
                async with context.cancellation.irreversible_section():
                    _require_profile(request, context)
                    ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
                    if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
                        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                    await await_cancellation_complete(
                        asyncio.to_thread(ports.prepare_consent), task_name="google.consent.prepare"
                    )
            except GoogleConfigurationRefusedError as error:
                if type(error) is not GoogleConfigurationRefusedError:
                    raise
                return await self._store_refusal(request, context, error.projection, OperationEffect.NONE)
            proposal = GoogleConsentProposal(identity=context.identity, revision=context.revision + 1, request=payload)
            await context.interactions.publish_review(
                interaction_id=secrets.token_hex(32),
                identity=context.identity,
                revision=proposal.revision,
                presentation_code=GOOGLE_CONSENT_PRESENTATION_CODE,
                response_schema_ref=operation_public_schema_reference(GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING.identity),
                continuation_digest=proposal.digest,
                expires_at=now() + timedelta(minutes=5),
                reviewed_operand=proposal,
                baseline_digest=content_hash_hex(payload.model_dump(mode="json")),
                proposed_effect_digest=proposal.digest,
            )
            return None
        return await self._run(request, context, terminal_admission=None)

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> OperationExecutorResult:
        """Require the exact consumed human terminal acknowledgement before browser consent."""
        payload = _require_profile(request, context)
        if not isinstance(payload, GoogleLoginRequest) or payload.refresh_only:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not checkpoint.consumed:
            return None
        if type(checkpoint) is not OperationConsumedInteraction or not isinstance(
            checkpoint, OperationConsumedInteraction
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        consumed = OperationConsumedInteraction.model_validate(checkpoint.model_dump(mode="python"), strict=True)
        proposal = await context.operands.resolve(consumed.reviewed_proposal_digest, GoogleConsentProposal)

        def terminal_admission() -> None:
            _require_profile(request, context)
            pending = consumed.checkpoint
            if (
                consumed.response_action != "apply"
                or proposal.identity != context.identity
                or proposal.request != payload
                or pending.request.identity != proposal.identity
                or pending.request.revision != proposal.revision
                or proposal.revision > context.revision
                or pending.reviewed_proposal_digest != proposal.digest
                or pending.request.continuation_digest != proposal.digest
                or pending.proposed_effect_digest != proposal.digest
                or pending.baseline_digest != content_hash_hex(payload.model_dump(mode="json"))
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)

        terminal_admission()
        return await self._run(request, context, terminal_admission=terminal_admission)

    async def _run(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
        *,
        terminal_admission: Callable[[], None] | None,
    ) -> OperationExecutorResult:
        payload = _require_profile(request, context)
        loop = asyncio.get_running_loop()
        local_changed = 0
        remote_changed = 0
        pending: list[tuple[str, bool]] = []
        local_uncertain = False

        def effect() -> OperationEffect:
            if pending or local_uncertain:
                return OperationEffect.UNKNOWN
            return OperationEffect.UPDATED if local_changed or remote_changed else OperationEffect.NONE

        async def admit(action: str, writes: bool) -> None:
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)
                pending.append((action, writes))
                await context.events.effect(OperationEffect.UNKNOWN)

        def before_handoff(action: str, *, writes: bool = False) -> None:
            asyncio.run_coroutine_threadsafe(admit(action, writes), loop).result()

        async def acknowledge(action: str, writes: bool) -> None:
            nonlocal remote_changed
            if not pending or pending[-1] != (action, writes):
                raise ValueError("Google acknowledgement has no matching admitted boundary")
            pending.pop()
            remote_changed += int(writes)
            await context.events.effect(effect())

        def acknowledged(action: str, *, writes: bool = False) -> None:
            asyncio.run_coroutine_threadsafe(acknowledge(action, writes), loop).result()

        async def save_local[ResultT](save: Callable[[], ResultT], changed: Callable[[ResultT], bool]) -> ResultT:
            nonlocal local_changed, local_uncertain
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)
                local_uncertain = True
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(save)
                local_changed += int(changed(result))
                local_uncertain = False
                await context.events.effect(effect())
                return result

        def commit[ResultT](save: Callable[[], ResultT], *, changed: Callable[[ResultT], bool]) -> ResultT:
            return asyncio.run_coroutine_threadsafe(save_local(save, changed), loop).result()

        async def run(secret: memoryview | None) -> OperationExecutorResult:
            try:
                ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
                if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                try:
                    projection = await asyncio.to_thread(
                        ports.run,
                        payload,
                        secret=secret,
                        commit=commit,
                        before_handoff=before_handoff,
                        acknowledged=acknowledged,
                        terminal_admission=terminal_admission,
                    )
                except GoogleConfigurationRefusedError as error:
                    if type(error) is not GoogleConfigurationRefusedError:
                        raise
                    settled = effect()
                    if settled is OperationEffect.UPDATED:
                        settled = OperationEffect.PARTIAL
                    return await self._store_refusal(request, context, error.projection, settled)
                if (
                    type(projection) is not _CONTRACTS[request.definition_id][1]
                    or projection.profile_id != payload.profile_id
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                # A canonical probe may report an uncertain provider refusal.
                settled = OperationEffect.UNKNOWN if pending or local_uncertain else effect()
                private = GoogleConfigurationExecutionResult(
                    identity=context.identity,
                    projection=GoogleConfigurationOutcome(
                        profile_id=payload.profile_id, outcome="succeeded", result=projection
                    ),
                    effect=settled.value,
                )
                if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                async with context.cancellation.irreversible_section():
                    _require_profile(request, context)
                    await context.events.effect(settled)
                    return await context.operands.put(private, written_at=now())
            except BaseException:
                current = effect()
                if current is OperationEffect.UPDATED:
                    current = OperationEffect.PARTIAL
                await context.events.effect(current)
                raise

        async def owned() -> OperationExecutorResult:
            if isinstance(payload, GoogleRegisterRequest):
                requirement = context.ephemeral_secret.requirement
                if requirement.identity != context.identity or requirement.secret_kind != GOOGLE_REGISTER_INPUT_KIND:
                    raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
                async with context.ephemeral_secret.consume() as secret:
                    return await run(secret)
            return await run(None)

        return await await_cancellation_complete(owned(), task_name=request.definition_id)

    async def _store_refusal(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
        refusal: GoogleConfigurationRefusalProjection,
        effect: OperationEffect,
    ) -> OperationRefusalEvidence:
        """Retain closed provider detail only after renewed exact-profile release authority."""
        payload = _require_profile(request, context)
        if refusal.profile_id != payload.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        private = GoogleConfigurationExecutionResult(
            identity=context.identity,
            projection=GoogleConfigurationOutcome(profile_id=payload.profile_id, outcome="refused", refusal=refusal),
            effect=effect.value,
        )
        if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        async with context.cancellation.irreversible_section():
            _require_profile(request, context)
            await context.events.effect(effect)
            detail_ref = await context.operands.put(private, written_at=now())
        return OperationRefusalEvidence(refusal_code=GOOGLE_CONFIGURATION_REFUSAL_CODE, detail_ref=detail_ref)


def project_google_configuration_result(value: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release complete human facts only from the exact invocation/effect receipt."""
    if type(value) is not GoogleConfigurationExecutionResult or not isinstance(
        value, GoogleConfigurationExecutionResult
    ):
        raise ValueError("invalid Google configuration execution result")
    private = GoogleConfigurationExecutionResult.model_validate(value.model_dump(mode="python"), strict=True)
    pair = _CONTRACTS.get(receipt.identity.definition_id)
    projection = private.projection
    if (
        pair is None
        or private.identity != receipt.identity
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect.value != private.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("Google configuration outcome differs from its terminal receipt")
    if projection.outcome == "succeeded":
        if (
            projection.result is None
            or type(projection.result) is not pair[1]
            or receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
        ):
            raise ValueError("Google success differs from its terminal receipt")
    elif (
        projection.refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != GOOGLE_CONFIGURATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
    ):
        raise ValueError("Google refusal differs from its terminal receipt")
    return projection


def project_google_consent_review(value: BaseModel, interaction: OperationInteractionRequest, /) -> BaseModel:
    """Disclose only the exact profile/revision proposal acknowledged by this terminal."""
    if type(value) is not GoogleConsentProposal or not isinstance(value, GoogleConsentProposal):
        raise ValueError("invalid Google consent proposal")
    proposal = GoogleConsentProposal.model_validate(value.model_dump(mode="python"), strict=True)
    if (
        proposal.identity != interaction.identity
        or proposal.revision != interaction.revision
        or proposal.digest != interaction.continuation_digest
    ):
        raise ValueError("Google consent proposal differs from its interaction")
    return GoogleConsentReviewProjection(
        identity=proposal.identity,
        revision=proposal.revision,
        profile_id=proposal.request.profile_id,
        reviewed_proposal_digest=proposal.digest,
    )


def resolve_google_configuration_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human whole-profile authority and both current private disclosure classes."""
    pair = _CONTRACTS.get(request.definition_id)
    if pair is None or type(request.payload) is not pair[0] or not isinstance(request.payload, _REQUEST_TYPES):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    disclosures = resolved.policy.disclosures
    if context.action in {AccessAction.RESULT, AccessAction.REVIEW, AccessAction.RESPOND}:
        schema = (
            context.contract.result_schema
            if context.action is AccessAction.RESULT
            else context.contract.review_projection_schema
        )
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id, projection_id=schema.schema_id, category=category
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return replace(
        resolved,
        policy=OperationAccessPolicy.model_validate(
            {
                **dict(resolved.policy),
                "actions": resolved.policy.actions
                | {AccessAction.COMMIT}
                | (
                    {AccessAction.REVIEW, AccessAction.RESPOND}
                    if request.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
                    else set()
                ),
                "requires_human": True,
                "disclosures": disclosures,
            }
        ),
    )


def build_google_configuration_definitions(
    factory: GoogleConfigurationOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll exactly the nine existing human CLI configuration leaves."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _projection_type) in _CONTRACTS.items():
        consent = definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        definitions.append(
            OperationDefinition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=GoogleConfigurationExecutionResult,
                executor_factory=OperationExecutorFactory(
                    request_type=request_type,
                    executor_type=GoogleConfigurationExecutor,
                    build=lambda: GoogleConfigurationExecutor(factory),
                ),
                phase_codes=(definition_id,),
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}) if consent else frozenset(),
                capabilities=OperationCapabilities(
                    durability=OperationDurability.RESUMABLE if consent else OperationDurability.RECORDED,
                    cancellation=OperationCancellation.UNSUPPORTED,
                    deadline=OperationDeadline.ABSENT,
                    replay=OperationReplayPolicy.RESUMABLE if consent else OperationReplayPolicy.IDEMPOTENT_SUBMIT,
                    baseline=OperationBaselinePolicy.EXACT_APPROVAL if consent else OperationBaselinePolicy.NONE,
                    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
                    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                    owned_resources=frozenset(),
                    permitted_effects=frozenset(OperationEffect),
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
                if consent
                else OperationReconciliationPolicy.INTERRUPT,
                permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
                refusal_detail_codes=frozenset({GOOGLE_CONFIGURATION_REFUSAL_CODE}),
                ephemeral_secret=OperationEphemeralSecretDeclaration(
                    secret_kind=GOOGLE_REGISTER_INPUT_KIND, lifetime=timedelta(minutes=5)
                )
                if definition_id == GOOGLE_REGISTER_OPERATION_DEFINITION_ID
                else None,
            )
        )
    return tuple(definitions)


def build_google_configuration_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Compile closed request/result schemas and exact human consent projections."""
    request_type, _projection_type = _CONTRACTS[definition.definition_id]
    consent = definition.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=request_type
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=GoogleConfigurationOutcome
        ),
        review_projection_schema=GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING if consent else None,
        interaction_response_schema=GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING if consent else None,
        access_resolver=resolve_google_configuration_access,
        result_projector=project_google_configuration_result,
        review_projector=project_google_consent_review if consent else None,
        reviewed_operand_type=GoogleConsentProposal if consent else None,
    )


__all__ = [
    "GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING",
    "GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING",
    "GoogleConfigurationExecutionResult",
    "GoogleConfigurationExecutor",
    "build_google_configuration_definitions",
    "build_google_configuration_registration",
    "project_google_configuration_result",
    "project_google_consent_review",
    "resolve_google_configuration_access",
]
