"""Exact-profile registered release of the purchase evidence linked to one ledger movement."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_RESULT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import TransactionIdPrefixError, TransactionNotFoundError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
    terminal_receipt_matches,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.result_size import refuse_oversized_result
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from .id_resolution import resolve_transaction_id
from .manual_read import ledger_transaction_result_payload
from .models import ManualLedgerTransactionResult
from .persistence_ports import LedgerPersistenceConflictError
from .purchase_evidence_release import (
    PurchaseEvidenceDisposition,
    PurchaseEvidenceReleaseCause,
    PurchaseEvidenceReleaseNextStep,
    PurchaseEvidenceReleaseRefusedError,
    release_manual_transaction_purchase_evidence,
)
from .read_access import resolve_ledger_request_commit_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID = "ledger.purchase_evidence.release"
LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE = "REFUSED_LEDGER_PURCHASE_EVIDENCE_RELEASE"
_PERSON_FRONTEND_ACTOR = "cli"
# A release changes only the movement's evidence slot and, to keep the document,
# adds one attachment, so the manual-update writer records at most these events.
_RELEASE_EVENT_TYPES = (BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED, BucketEventType.ATTACHMENT_LINKED)

_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=64)]
_EvidenceId = Annotated[str, Field(min_length=1, max_length=64)]
_Timestamp = Annotated[str, Field(min_length=1, max_length=64)]
_EventId = Annotated[str, Field(min_length=1, max_length=64)]
_InvoiceId = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerPurchaseEvidenceReleaseRequest(BaseModel):
    """Private exact-profile request to release one movement's linked purchase evidence.

    ``expected_purchase_invoice_evidence_id`` and ``expected_modified_at`` are the
    evidence and the ``modified_at`` the person's opened movement showed; a movement
    that no longer matches them is refused. ``disposition`` says whether the
    evidence is unlinked (``detach``) or kept on the movement as an ordinary
    document (``keep_as_document``).

    The request names no actor: an automation's session is recorded under its own
    session label, and a person's under the operation's own label for a person.

    ``output_language`` is the language the result's transaction link fields are named in.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    expected_purchase_invoice_evidence_id: _EvidenceId
    expected_modified_at: _Timestamp
    disposition: PurchaseEvidenceDisposition
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    @field_validator("expected_modified_at")
    @classmethod
    def _aware_instant(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("expected_modified_at must be the movement's ISO-8601 modified_at") from None
        if parsed.tzinfo is None:
            raise ValueError("expected_modified_at must carry its UTC offset")
        return value

    def expected_modified_instant(self) -> datetime:
        """Return the opened movement's ``modified_at`` as an instant."""
        return datetime.fromisoformat(self.expected_modified_at)


class LedgerPurchaseEvidenceReleaseRefusal(BaseModel):
    """Why the release was refused, what the person can do, and what blocks it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    cause: PurchaseEvidenceReleaseCause
    next_step: PurchaseEvidenceReleaseNextStep
    finalized_revisions: Annotated[tuple[LedgerAttachmentStaleRevisionProjection, ...], Field(max_length=4096)] = ()
    """The finalized calculations that cite the movement, for ``finalized_calculation_reference``."""
    invoice_ids: Annotated[tuple[_InvoiceId, ...], Field(max_length=256)] = ()
    """The canonical invoices the evidence was confirmed into, for ``evidence_confirmed_into_invoice``."""

    @model_validator(mode="after")
    def _facts_match_cause(self) -> LedgerPurchaseEvidenceReleaseRefusal:
        if (self.cause is PurchaseEvidenceReleaseCause.FINALIZED_CALCULATION_REFERENCE) != bool(
            self.finalized_revisions
        ):
            raise ValueError("only a finalized-calculation refusal names the citing revisions")
        if (self.cause is PurchaseEvidenceReleaseCause.EVIDENCE_CONFIRMED_INTO_INVOICE) != bool(self.invoice_ids):
            raise ValueError("only a confirmed-invoice refusal names the invoices")
        return self


class LedgerPurchaseEvidenceReleaseResult(BaseModel):
    """The released movement, or the typed refusal decided before any write."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "refused"]
    profile_id: UUID
    disposition: PurchaseEvidenceDisposition
    released_evidence_id: _EvidenceId
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: Annotated[tuple[_EventId, ...], Field(max_length=len(_RELEASE_EVENT_TYPES))] = ()
    refusal: LedgerPurchaseEvidenceReleaseRefusal | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerPurchaseEvidenceReleaseResult:
        if self.outcome == "updated":
            if (
                self.transaction is None
                or self.review_status is None
                or not self.bucket_event_ids
                or self.refusal is not None
                or self.transaction.purchase_invoice_evidence_id is not None
            ):
                raise ValueError("a released movement carries its row, events and no refusal")
        elif (
            self.refusal is None
            or self.transaction is not None
            or self.review_status is not None
            or self.bucket_event_ids
        ):
            raise ValueError("a refused release carries only its refusal")
        return self


class LedgerPurchaseEvidenceReleaseExecutionResult(BaseModel):
    """Private encrypted wrapper whose public result is checked against its receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerPurchaseEvidenceReleaseResult


class LedgerPurchaseEvidenceReleaseExecutor:
    """Release one movement's linked purchase evidence through the canonical service."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the profile-specific ledger ports and the session host's caller reader."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[LedgerPurchaseEvidenceReleaseRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve the movement, release its evidence in one guarded commit, and record the effect."""
        payload = request.payload
        if (
            request.definition_id != LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID
            or not isinstance(payload, LedgerPurchaseEvidenceReleaseRequest)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        bucket_id = str(payload.profile_id)
        await context.events.phase(LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_PERSON_FRONTEND_ACTOR)
        operation: PinnedAuthorityOperation = context.authority_operation
        ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
        require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
        try:
            catalogue = await asyncio.to_thread(ports.transaction_repository.load)
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
        except (TransactionIdPrefixError, TransactionNotFoundError):
            await context.events.effect(OperationEffect.NONE)
            return await _publish_refusal(
                context,
                payload,
                PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.TRANSACTION_NOT_FOUND),
            )

        async def commit() -> LedgerPurchaseEvidenceReleaseResult | PurchaseEvidenceReleaseRefusedError:
            async with context.cancellation.irreversible_section():
                # Every refusal is decided before the canonical writer's single
                # transaction+event batch; past that point the outcome is
                # unknown until the batch returns.
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        release_manual_transaction_purchase_evidence,
                        bucket_id=bucket_id,
                        transaction_id=transaction_id,
                        expected_purchase_invoice_evidence_id=payload.expected_purchase_invoice_evidence_id,
                        expected_modified_at=payload.expected_modified_instant(),
                        disposition=payload.disposition,
                        actor=actor,
                        source_command="aeat app ledger evidence release",
                        ports=ports,
                    )
                except PurchaseEvidenceReleaseRefusedError as refusal:
                    await context.events.effect(OperationEffect.NONE)
                    return refusal
                except LedgerPersistenceConflictError:
                    # The guarded replacement compares the opened row with the
                    # stored one and rolls the whole batch back on a change.
                    await context.events.effect(OperationEffect.NONE)
                    return PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED)
                await context.events.effect(OperationEffect.UPDATED)
                released = _released_result(payload, result)
                _check_result_size(LedgerPurchaseEvidenceReleaseExecutionResult(result=released))
                return released

        settled = await await_cancellation_complete(
            commit(), task_name=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID
        )
        if isinstance(settled, PurchaseEvidenceReleaseRefusedError):
            return await _publish_refusal(context, payload, settled)
        return await context.operands.put(
            LedgerPurchaseEvidenceReleaseExecutionResult(result=settled), written_at=now()
        )


def _released_result(
    payload: LedgerPurchaseEvidenceReleaseRequest,
    result: ManualLedgerTransactionResult,
) -> LedgerPurchaseEvidenceReleaseResult:
    """Copy the canonical released row through the bounded public projection."""
    canonical = ledger_transaction_result_payload(result)
    if canonical.bucket_id != str(payload.profile_id) or result.transaction.transaction_id != canonical.transaction_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerPurchaseEvidenceReleaseResult(
        outcome="updated",
        profile_id=payload.profile_id,
        disposition=payload.disposition,
        released_evidence_id=payload.expected_purchase_invoice_evidence_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction, language=payload.output_language),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
    )


async def _publish_refusal(
    context: OperationExecutorContext,
    payload: LedgerPurchaseEvidenceReleaseRequest,
    refusal: PurchaseEvidenceReleaseRefusedError,
) -> OperationRefusalEvidence:
    """Store one typed pre-write refusal as the receipt's refusal detail."""
    result = LedgerPurchaseEvidenceReleaseResult(
        outcome="refused",
        profile_id=payload.profile_id,
        disposition=payload.disposition,
        released_evidence_id=payload.expected_purchase_invoice_evidence_id,
        refusal=LedgerPurchaseEvidenceReleaseRefusal(
            cause=refusal.cause,
            next_step=refusal.next_step,
            finalized_revisions=tuple(
                LedgerAttachmentStaleRevisionProjection.from_blocker(blocker) for blocker in refusal.blockers
            ),
            invoice_ids=refusal.invoice_ids,
        ),
    )
    execution_result = LedgerPurchaseEvidenceReleaseExecutionResult(result=result)
    _check_result_size(execution_result)
    detail_ref = await context.operands.put(execution_result, written_at=now())
    return OperationRefusalEvidence(refusal_code=LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE, detail_ref=detail_ref)


def _check_result_size(result: LedgerPurchaseEvidenceReleaseExecutionResult) -> None:
    """Keep encrypted receipts within the bounded operation-result budget."""
    refuse_oversized_result(result, PROJECTION_RESULT_MAX_BYTES - 128)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the result whose profile, outcome and effect match the receipt."""
    if type(result) is not LedgerPurchaseEvidenceReleaseExecutionResult:
        raise ValueError("invalid ledger purchase evidence release execution result")
    projected = result.result
    subject_ref = profile_operation_subject(str(projected.profile_id))
    if projected.outcome == "refused":
        if (
            not terminal_receipt_matches(
                receipt,
                definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
                subject_ref=subject_ref,
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.NONE,
            )
            or receipt.refusal_ref != LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
        ):
            raise ValueError("ledger purchase evidence release refusal has an incompatible terminal receipt")
        return projected
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        effect=OperationEffect.UPDATED,
        message="ledger purchase evidence release success has an incompatible terminal receipt",
    )
    return projected


def build_ledger_purchase_evidence_release_definition(
    ports_factory: LedgerActionPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare the receipt-backed release of one movement's linked purchase evidence."""
    return build_single_phase_definition(
        definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        request_type=LedgerPurchaseEvidenceReleaseRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerPurchaseEvidenceReleaseExecutionResult,
        executor_type=LedgerPurchaseEvidenceReleaseExecutor,
        build=lambda: LedgerPurchaseEvidenceReleaseExecutor(
            ports_factory, execution_caller_reader=execution_caller_reader
        ),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        refusal_detail_codes=frozenset({LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE}),
    )


def resolve_ledger_purchase_evidence_release_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile access plus COMMIT for the release."""
    return resolve_ledger_request_commit_access(
        request,
        context,
        definition_id=LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        request_type=LedgerPurchaseEvidenceReleaseRequest,
    )


def build_ledger_purchase_evidence_release_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the release's closed schemas and exact-profile resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerPurchaseEvidenceReleaseResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_purchase_evidence_release_access,
    )


__all__ = [
    "LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID",
    "LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE",
    "LedgerPurchaseEvidenceReleaseExecutionResult",
    "LedgerPurchaseEvidenceReleaseExecutor",
    "LedgerPurchaseEvidenceReleaseRefusal",
    "LedgerPurchaseEvidenceReleaseRequest",
    "LedgerPurchaseEvidenceReleaseResult",
    "build_ledger_purchase_evidence_release_definition",
    "build_ledger_purchase_evidence_release_registration",
    "resolve_ledger_purchase_evidence_release_access",
]
