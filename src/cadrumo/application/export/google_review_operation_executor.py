"""Publish saved financial reviews only after exact human disclosure admission."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.operations import OperationEffect, OperationInteractionKind
from ...core.time.clock import now
from ..operations.interactions import OperationConsumedInteraction, OperationPendingInteraction
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ..operations.persistence.journal import serialize_operation_operand
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult
from ..operations.registry import operation_public_schema_reference
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .google_operation import GoogleSheetsExportCapabilityDisabledError
from .google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
    GoogleReviewExecutionResult,
    GoogleReviewOperationPorts,
    GoogleReviewOperationPortsFactory,
    GoogleReviewProposal,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from .managed_artifact_ports import ManagedArtifactKind
from .publication_receipt import (
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
    ReadablePayloadCategory,
)
from .review_snapshot import CalculationReviewSelection, ReviewSnapshot


def require_review_request(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> GoogleReviewRequest:
    """Recheck exact profile and definition before reading or crossing effects."""
    payload = request.payload
    if request.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID or type(payload) is not GoogleReviewRequest:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    require_operation_profile(request, context, payload.profile_id)
    from ...core.capabilities import ServiceCapability
    from ..user_profile.capabilities import resolve_active_capability

    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
        raise GoogleSheetsExportCapabilityDisabledError("Google Sheets export capability is disabled")
    return payload


def require_review_approval(
    consumed: OperationConsumedInteraction,
    proposal: GoogleReviewProposal,
    request: OperationRequest[BaseModel],
    context: OperationExecutorContext,
) -> None:
    """Reject substituted proposals, foreign checkpoints and non-apply responses."""
    payload = require_review_request(request, context)
    pending = consumed.checkpoint
    if (
        consumed.response_action != "apply"
        or proposal.identity != context.identity
        or proposal.request != payload
        or pending.request.identity != proposal.identity
        or pending.request.revision != proposal.revision
        or proposal.revision > context.revision
        or pending.reviewed_proposal_digest != sha256_hex(serialize_operation_operand(proposal))
        or pending.request.continuation_digest != proposal.digest
        or pending.proposed_effect_digest != proposal.digest
        or pending.baseline_digest != content_hash_hex(payload.model_dump(mode="json"))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


class _PublicationEffects:
    """Renew admission at each provider handoff and physical receipt commit."""

    def __init__(self, context: OperationExecutorContext, admit: Callable[[], None]) -> None:
        self.context = context
        self.admit = admit
        self.loop = asyncio.get_running_loop()
        self.pending: list[tuple[str, bool]] = []
        self.changed = False
        self.local_uncertain = False

    def effect(self) -> OperationEffect:
        if self.pending or self.local_uncertain:
            return OperationEffect.UNKNOWN
        return OperationEffect.UPDATED if self.changed else OperationEffect.NONE

    async def _handoff(self, action: str, writes: bool) -> None:
        async with self.context.cancellation.irreversible_section():
            self.admit()
            self.pending.append((action, writes))
            await self.context.events.effect(OperationEffect.UNKNOWN)

    def before_handoff(self, action: str, *, writes: bool = False) -> None:
        asyncio.run_coroutine_threadsafe(self._handoff(action, writes), self.loop).result()

    async def _acknowledge(self, action: str, writes: bool) -> None:
        if not self.pending or self.pending[-1] != (action, writes):
            raise ValueError("publication acknowledgement has no matching boundary")
        self.pending.pop()
        self.changed |= writes
        await self.context.events.effect(self.effect())

    def acknowledged(self, action: str, *, writes: bool = False) -> None:
        asyncio.run_coroutine_threadsafe(self._acknowledge(action, writes), self.loop).result()

    async def _commit[ResultT](self, save: Callable[[], ResultT], changed: Callable[[ResultT], bool]) -> ResultT:
        async with self.context.cancellation.irreversible_section():
            self.admit()
            self.local_uncertain = True
            await self.context.events.effect(OperationEffect.UNKNOWN)
            result = await asyncio.to_thread(save)
            self.changed |= changed(result)
            self.local_uncertain = False
            await self.context.events.effect(self.effect())
            return result

    def commit[ResultT](self, save: Callable[[], ResultT], *, changed: Callable[[ResultT], bool]) -> ResultT:
        return asyncio.run_coroutine_threadsafe(self._commit(save, changed), self.loop).result()


class GoogleReviewExecutor:
    """Hold an immutable review through a durable, human-only response checkpoint."""

    def __init__(self, factory: GoogleReviewOperationPortsFactory) -> None:
        """Bind production ports while leaving credentials in the adapter."""
        self.factory = factory

    def _ports(self, payload: GoogleReviewRequest, context: OperationExecutorContext) -> GoogleReviewOperationPorts:
        ports = self.factory(profile_id=payload.profile_id, operation=context.authority_operation)
        if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return ports

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Resolve the selected saved revision locally and publish its disclosure."""
        payload = require_review_request(request, context)
        await context.events.phase(GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".prepare")
        await context.events.effect(OperationEffect.NONE)
        ports = self._ports(payload, context)
        if payload.filing_record_id is not None:
            if ports.load_filing_snapshot is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            snapshot = await asyncio.to_thread(
                ports.load_filing_snapshot, payload.calculation_revision_id, payload.filing_record_id
            )
        else:
            snapshot = await asyncio.to_thread(ports.load_snapshot, payload.calculation_revision_id)
        selection = snapshot.selection
        if (
            not isinstance(selection, CalculationReviewSelection)
            or selection.profile_id != payload.profile_id
            or selection.calculation_revision_id != payload.calculation_revision_id
            or (
                payload.filing_record_id is not None
                and (
                    snapshot.calculation_lifecycle is None
                    or snapshot.calculation_lifecycle.filing_record_id != payload.filing_record_id
                )
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        root = await asyncio.to_thread(ports.load_root)
        publication = PublicationReceipt(
            publication_id=payload.publication_id,
            profile_id=payload.profile_id,
            root=root,
            snapshot_digest=snapshot.snapshot_digest,
        )
        proposal = GoogleReviewProposal(
            identity=context.identity,
            revision=context.revision + 1,
            request=payload,
            snapshot_ref=await context.operands.put(snapshot, written_at=now()),
            snapshot_digest=snapshot.snapshot_digest,
            publication=publication,
            payload_categories=(ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER)
            if snapshot.ledger_rows
            else (ReadablePayloadCategory.CALCULATION,),
        )
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=proposal.revision,
            presentation_code="google.review.readable-publication",
            response_schema_ref=operation_public_schema_reference(GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING.identity),
            continuation_digest=proposal.digest,
            expires_at=now() + timedelta(minutes=10),
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
        """Publish only the approved frozen operand, never recalculate current values."""
        payload = require_review_request(request, context)
        if not checkpoint.consumed:
            # Only canonical owner-loss reconciliation resumes a pending
            # checkpoint. Its original human response capability cannot be
            # transferred to a fresh session. End this untouched publication
            # so a newly reviewed invocation can acquire the profile subject.
            if (
                type(checkpoint) is OperationPendingInteraction
                and checkpoint.request.identity == context.identity
                and checkpoint.request.kind is OperationInteractionKind.REVIEW
                and checkpoint.request.revision <= context.revision
                and checkpoint.request.response_schema_ref
                == operation_public_schema_reference(GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING.identity)
            ):
                await context.events.effect(OperationEffect.NONE)
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        if type(checkpoint) is not OperationConsumedInteraction:
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        consumed = OperationConsumedInteraction.model_validate(checkpoint.model_dump(mode="python"), strict=True)
        proposal = await context.operands.resolve(consumed.reviewed_proposal_digest, GoogleReviewProposal)

        def admit() -> None:
            require_review_approval(consumed, proposal, request, context)

        admit()
        snapshot = await context.operands.resolve(proposal.snapshot_ref, ReviewSnapshot)
        if snapshot.snapshot_digest != proposal.snapshot_digest:
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        ports = self._ports(payload, context)
        root = await asyncio.to_thread(ports.load_root)
        if root != proposal.publication.root:
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        authorization = ReadableExportAuthorization(
            profile_id=payload.profile_id,
            publication_id=payload.publication_id,
            root_folder_id=root.artifact_id,
            snapshot_digest=proposal.snapshot_digest,
            payload_categories=proposal.payload_categories,
            disclosure_digest=proposal.digest,
        )
        tracker = _PublicationEffects(context, admit)
        await context.events.phase(GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".publish")
        try:
            receipt = await await_cancellation_complete(
                asyncio.to_thread(
                    ports.publish,
                    snapshot,
                    proposal.publication,
                    authorization,
                    commit=tracker.commit,
                    before_handoff=tracker.before_handoff,
                    acknowledged=tracker.acknowledged,
                ),
                task_name="google.review.publish",
            )
            if (
                receipt.state is not PublicationState.PUBLISHED
                or receipt.publication_id != payload.publication_id
                or receipt.profile_id != payload.profile_id
                or receipt.root != root
                or receipt.snapshot_digest != proposal.snapshot_digest
                or receipt.package_digest != proposal.publication.package_digest
                or receipt.predecessor_publication_id != proposal.publication.predecessor_publication_id
            ):
                raise ValueError("publication did not return the approved verified receipt")
            admit()
            retained = await asyncio.to_thread(ports.load_publication, payload.publication_id)
            if retained != receipt:
                raise ValueError("publication lacks exact durable receipt custody")
            settled = tracker.effect()
            sheets = tuple(item for item in receipt.artifacts if item.kind is ManagedArtifactKind.REVIEW_SHEET)
            if len(sheets) != 1 or settled not in {OperationEffect.NONE, OperationEffect.UPDATED}:
                raise ValueError("publication lacks one settled native spreadsheet")
            result = GoogleReviewExecutionResult(
                identity=context.identity,
                effect="updated" if settled is OperationEffect.UPDATED else "none",
                result=GoogleReviewResult(
                    profile_id=payload.profile_id,
                    publication_id=payload.publication_id,
                    snapshot_digest=receipt.snapshot_digest,
                    root_folder_id=root.artifact_id,
                    spreadsheet_id=sheets[0].artifact_id,
                    spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{sheets[0].artifact_id}/edit",
                ),
            )
            async with context.cancellation.irreversible_section():
                admit()
                await context.events.effect(settled)
                return await context.operands.put(result, written_at=now())
        except BaseException:
            effect = tracker.effect()
            await context.events.effect(OperationEffect.PARTIAL if effect is OperationEffect.UPDATED else effect)
            raise
