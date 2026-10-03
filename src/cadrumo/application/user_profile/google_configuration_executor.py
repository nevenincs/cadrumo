"""Execute registered Google configuration leaves under profile and effect authority."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from datetime import timedelta
from functools import partial

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes, content_hash_hex
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ..operations.interactions import OperationConsumedInteraction
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..operations.registry import operation_public_schema_reference
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .access_contracts import AccessDenialCode
from .access_errors import ProfileAccessRefusedError
from .google_configuration_operation_contracts import (
    GOOGLE_CONFIGURATION_CONTRACTS,
    GOOGLE_CONFIGURATION_REQUEST_TYPES,
    GOOGLE_CONSENT_PRESENTATION_CODE,
    GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING,
    GOOGLE_REGISTER_INPUT_KIND,
    GoogleConfigurationExecutionResult,
    GoogleConfigurationOutcome,
    GoogleConfigurationProjection,
    GoogleConfigurationRequest,
    GoogleConsentProposal,
    GoogleLoginRequest,
    GoogleRegisterRequest,
)
from .google_configuration_operation_ports import GoogleConfigurationOperationPortsFactory
from .google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationRefusalProjection,
    GoogleConfigurationRefusedError,
)


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> GoogleConfigurationRequest:
    pair = GOOGLE_CONFIGURATION_CONTRACTS.get(request.definition_id)
    payload = request.payload
    if pair is None or type(payload) is not pair[0] or not isinstance(payload, GOOGLE_CONFIGURATION_REQUEST_TYPES):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    require_operation_profile(request, context, payload.profile_id)
    return payload


def _require_consent_proposal_matches(
    consumed: OperationConsumedInteraction,
    proposal: GoogleConsentProposal,
    context: OperationExecutorContext,
    payload: GoogleLoginRequest,
) -> None:
    if consumed.response_action != "apply" or proposal.identity != context.identity or proposal.request != payload:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


def _require_consent_checkpoint_matches(
    consumed: OperationConsumedInteraction,
    proposal: GoogleConsentProposal,
    context: OperationExecutorContext,
) -> None:
    pending = consumed.checkpoint
    if (
        pending.request.identity != proposal.identity
        or pending.request.revision != proposal.revision
        or proposal.revision > context.revision
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


def _require_consent_digests_match(
    consumed: OperationConsumedInteraction,
    proposal: GoogleConsentProposal,
    payload: GoogleLoginRequest,
) -> None:
    pending = consumed.checkpoint
    if pending.reviewed_proposal_digest != proposal.digest:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if pending.request.continuation_digest != proposal.digest:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if pending.proposed_effect_digest != proposal.digest:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if pending.baseline_digest != content_hash_hex(payload.model_dump(mode="json")):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


def _require_google_terminal_admission(
    *,
    request: OperationRequest[BaseModel],
    context: OperationExecutorContext,
    payload: GoogleLoginRequest,
    consumed: OperationConsumedInteraction,
    proposal: GoogleConsentProposal,
) -> None:
    _require_profile(request, context)
    _require_consent_proposal_matches(consumed, proposal, context, payload)
    _require_consent_checkpoint_matches(consumed, proposal, context)
    _require_consent_digests_match(consumed, proposal, payload)


class _GoogleConfigurationEffectTracker:
    """Serialize provider handoffs and local commits into honest effect events."""

    def __init__(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> None:
        self._request = request
        self._context = context
        self._loop = asyncio.get_running_loop()
        self._local_changed = 0
        self._remote_changed = 0
        self._pending: list[tuple[str, bool]] = []
        self._local_uncertain = False

    def effect(self) -> OperationEffect:
        if self._pending or self._local_uncertain:
            return OperationEffect.UNKNOWN
        if self._local_changed or self._remote_changed:
            return OperationEffect.UPDATED
        return OperationEffect.NONE

    async def _admit(self, action: str, writes: bool) -> None:
        async with self._context.cancellation.irreversible_section():
            _require_profile(self._request, self._context)
            self._pending.append((action, writes))
            await self._context.events.effect(OperationEffect.UNKNOWN)

    def before_handoff(self, action: str, *, writes: bool = False) -> None:
        asyncio.run_coroutine_threadsafe(self._admit(action, writes), self._loop).result()

    async def _acknowledge(self, action: str, writes: bool) -> None:
        if not self._pending or self._pending[-1] != (action, writes):
            raise ValueError("Google acknowledgement has no matching admitted boundary")
        self._pending.pop()
        self._remote_changed += int(writes)
        await self._context.events.effect(self.effect())

    def acknowledged(self, action: str, *, writes: bool = False) -> None:
        asyncio.run_coroutine_threadsafe(self._acknowledge(action, writes), self._loop).result()

    async def _save_local[ResultT](self, save: Callable[[], ResultT], changed: Callable[[ResultT], bool]) -> ResultT:
        async with self._context.cancellation.irreversible_section():
            _require_profile(self._request, self._context)
            self._local_uncertain = True
            await self._context.events.effect(OperationEffect.UNKNOWN)
            result = await asyncio.to_thread(save)
            self._local_changed += int(changed(result))
            self._local_uncertain = False
            await self._context.events.effect(self.effect())
            return result

    def commit[ResultT](self, save: Callable[[], ResultT], *, changed: Callable[[ResultT], bool]) -> ResultT:
        return asyncio.run_coroutine_threadsafe(self._save_local(save, changed), self._loop).result()

    async def record_failure(self) -> None:
        current = self.effect()
        if current is OperationEffect.UPDATED:
            current = OperationEffect.PARTIAL
        await self._context.events.effect(current)


class GoogleConfigurationExecutor:
    """Admit every provider boundary and settle effects after owned work completes."""

    def __init__(self, factory: GoogleConfigurationOperationPortsFactory) -> None:
        """Bind the canonical owning services without constructing credentials."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Run a configuration leaf or publish the exact consent checkpoint."""
        payload = _require_profile(request, context)
        await context.events.phase(request.definition_id)
        await context.events.effect(OperationEffect.NONE)
        if isinstance(payload, GoogleLoginRequest) and not payload.refresh_only:
            return await self._prepare_consent(request, context, payload)
        return await self._run(request, context, terminal_admission=None)

    async def _prepare_consent(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext, payload: GoogleLoginRequest
    ) -> OperationExecutorResult:
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

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> OperationExecutorResult:
        """Require the exact consumed human terminal acknowledgement before consent."""
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
        terminal_admission = partial(
            _require_google_terminal_admission,
            request=request,
            context=context,
            payload=payload,
            consumed=consumed,
            proposal=proposal,
        )
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
        tracker = _GoogleConfigurationEffectTracker(request, context)
        work = self._run_with_secret(request, context, payload, tracker, terminal_admission)
        return await await_cancellation_complete(work, task_name=request.definition_id)

    async def _run_with_secret(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
        payload: GoogleConfigurationRequest,
        tracker: _GoogleConfigurationEffectTracker,
        terminal_admission: Callable[[], None] | None,
    ) -> OperationExecutorResult:
        if not isinstance(payload, GoogleRegisterRequest):
            return await self._run_provider(request, context, payload, tracker, terminal_admission, secret=None)
        requirement = context.ephemeral_secret.requirement
        if requirement.identity != context.identity or requirement.secret_kind != GOOGLE_REGISTER_INPUT_KIND:
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        async with context.ephemeral_secret.consume() as secret:
            return await self._run_provider(request, context, payload, tracker, terminal_admission, secret=secret)

    async def _run_provider(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
        payload: GoogleConfigurationRequest,
        tracker: _GoogleConfigurationEffectTracker,
        terminal_admission: Callable[[], None] | None,
        *,
        secret: memoryview | None,
    ) -> OperationExecutorResult:
        try:
            ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
            if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            try:
                projection = await asyncio.to_thread(
                    ports.run,
                    payload,
                    secret=secret,
                    commit=tracker.commit,
                    before_handoff=tracker.before_handoff,
                    acknowledged=tracker.acknowledged,
                    terminal_admission=terminal_admission,
                )
            except GoogleConfigurationRefusedError as error:
                if type(error) is not GoogleConfigurationRefusedError:
                    raise
                settled = tracker.effect()
                if settled is OperationEffect.UPDATED:
                    settled = OperationEffect.PARTIAL
                return await self._store_refusal(request, context, error.projection, settled)
            return await self._store_success(request, context, payload, projection, tracker)
        except BaseException:
            await tracker.record_failure()
            raise

    async def _store_success(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
        payload: GoogleConfigurationRequest,
        projection: GoogleConfigurationProjection,
        tracker: _GoogleConfigurationEffectTracker,
    ) -> OperationExecutorResult:
        if (
            type(projection) is not GOOGLE_CONFIGURATION_CONTRACTS[request.definition_id][1]
            or projection.profile_id != payload.profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        settled = tracker.effect()
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


__all__ = ["GoogleConfigurationExecutor"]
