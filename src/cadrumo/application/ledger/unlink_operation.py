"""Exact-profile registered removal of one movement's invoice link."""

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
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.buckets.event import BucketActorLabel
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.errors import TransactionIdPrefixError, TransactionNotFoundError
from ..invoices.catalogue_selection import InvoiceLookupRefusedError, select_catalogue_invoice_id
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
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
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import build_manual_ledger_result, resolve_invoice_repository
from .attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from .export_link_operation_ports import resolve_export_link_access
from .id_resolution import resolve_transaction_id
from .invoice_unlink import (
    InvoiceUnlinkCause,
    InvoiceUnlinkNextStep,
    InvoiceUnlinkRefusedError,
    InvoiceUnlinkResult,
    unlink_manual_transaction_invoice,
)
from .manual_read import ledger_transaction_result_payload
from .transaction_projection import LedgerTransactionProjection

LEDGER_UNLINK_OPERATION_DEFINITION_ID = "ledger.unlink"
LEDGER_UNLINK_REFUSAL_CODE = "REFUSED_LEDGER_UNLINK"
_SOURCE_COMMAND = "aeat app ledger unlink"
_MAX_LINKED_TRANSACTIONS = 4096

_Identifier = Annotated[str, Field(min_length=1, max_length=64)]
_Timestamp = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerUnlinkRequest(BaseModel):
    """Private exact-profile request to remove one movement's link to one invoice.

    ``transaction_id`` is the movement's id or an unambiguous prefix and
    ``invoice_id`` the invoice's id or an unambiguous prefix.
    ``expected_modified_at`` is the ``modified_at`` the person's opened movement
    showed and ``expected_invoice_linked_transaction_ids`` the movements the
    opened invoice listed; a movement or invoice that no longer matches them is
    refused.

    ``actor`` is recorded as sent for a person's session. An automation's session is
    recorded under its own session label, whatever the request carries.

    ``output_language`` is the language the result's transaction link fields are named in.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _Identifier
    invoice_id: _Identifier
    expected_modified_at: _Timestamp
    expected_invoice_linked_transaction_ids: Annotated[
        tuple[_Identifier, ...], Field(max_length=_MAX_LINKED_TRANSACTIONS)
    ]
    actor: Annotated[str, Field(max_length=64)] | None = None
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


class LedgerUnlinkRefusal(BaseModel):
    """Why the unlink was refused, what the person can do, and what blocks it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    cause: InvoiceUnlinkCause
    next_step: InvoiceUnlinkNextStep
    finalized_revisions: Annotated[tuple[LedgerAttachmentStaleRevisionProjection, ...], Field(max_length=4096)] = ()
    """The finalized calculations that cite the movement, for ``finalized_calculation_reference``."""

    @model_validator(mode="after")
    def _facts_match_cause(self) -> LedgerUnlinkRefusal:
        if (self.cause is InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE) != bool(self.finalized_revisions):
            raise ValueError("only a finalized-calculation refusal names the citing revisions")
        return self


class LedgerUnlinkResult(BaseModel):
    """The unlinked movement and the invoice's remaining links, or the typed refusal.

    ``invoice_id`` is the selector the person supplied for a refusal and the one
    resolved invoice id for a completed unlink.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["unlinked", "refused"]
    profile_id: UUID
    transaction_id: _Identifier
    invoice_id: _Identifier
    actor: BucketActorLabel | None = None
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    invoice_linked_transaction_ids: Annotated[tuple[_Identifier, ...], Field(max_length=_MAX_LINKED_TRANSACTIONS)] = ()
    bucket_event_ids: Annotated[tuple[_Identifier, ...], Field(max_length=1)] = ()
    refusal: LedgerUnlinkRefusal | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerUnlinkResult:
        if self.outcome == "unlinked":
            if (
                self.transaction is None
                or self.review_status is None
                or self.actor is None
                or len(self.bucket_event_ids) != 1
                or self.refusal is not None
                or self.transaction.invoice_id is not None
                or self.transaction.transaction_id in self.invoice_linked_transaction_ids
                or not self.transaction.transaction_id.startswith(self.transaction_id.strip().lower())
            ):
                raise ValueError("an unlinked movement carries its unlinked row, one event and no refusal")
        elif (
            self.refusal is None
            or self.transaction is not None
            or self.review_status is not None
            or self.actor is not None
            or self.invoice_linked_transaction_ids
            or self.bucket_event_ids
        ):
            raise ValueError("a refused unlink carries only its refusal")
        return self


class LedgerUnlinkExecutionResult(BaseModel):
    """Private encrypted wrapper whose public result is checked against its receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerUnlinkResult


class LedgerUnlinkExecutor:
    """Remove one movement's invoice link through the canonical service."""

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
        request: OperationRequest[LedgerUnlinkRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve both records, remove the link in one guarded commit, and record the effect."""
        payload = request.payload
        if (
            request.definition_id != LEDGER_UNLINK_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_UNLINK_OPERATION_DEFINITION_ID
            or not isinstance(payload, LedgerUnlinkRequest)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        bucket_id = str(payload.profile_id)
        await context.events.phase(LEDGER_UNLINK_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_supplied_actor(payload.actor))
        operation: PinnedAuthorityOperation = context.authority_operation
        ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
        require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
        try:
            catalogue = await asyncio.to_thread(ports.transaction_repository.load)
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            invoice_id = await asyncio.to_thread(_resolved_invoice_id, payload.invoice_id, ports, bucket_id)
        except (TransactionIdPrefixError, TransactionNotFoundError, InvoiceLookupRefusedError):
            await context.events.effect(OperationEffect.NONE)
            return await _publish_refusal(
                context, payload, InvoiceUnlinkRefusedError(InvoiceUnlinkCause.LINK_NOT_FOUND)
            )

        def unlink() -> InvoiceUnlinkResult:
            with validating_governed_facts(operation):
                return unlink_manual_transaction_invoice(
                    bucket_id=bucket_id,
                    transaction_id=transaction_id,
                    invoice_id=invoice_id,
                    expected_modified_at=payload.expected_modified_instant(),
                    expected_invoice_linked_transaction_ids=payload.expected_invoice_linked_transaction_ids,
                    actor=actor,
                    source_command=_SOURCE_COMMAND,
                    ports=ports,
                )

        async def commit() -> LedgerUnlinkResult | InvoiceUnlinkRefusedError:
            async with context.cancellation.irreversible_section():
                # Every refusal is decided before the single transaction, invoice
                # and event batch; past that point the outcome is unknown until
                # the batch returns.
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(unlink)
                except InvoiceUnlinkRefusedError as refusal:
                    await context.events.effect(OperationEffect.NONE)
                    return refusal
                await context.events.effect(OperationEffect.UPDATED)
                unlinked = _unlinked_result(payload, result, bucket_id=bucket_id, invoice_id=invoice_id, actor=actor)
                _check_result_size(LedgerUnlinkExecutionResult(result=unlinked))
                return unlinked

        settled = await await_cancellation_complete(commit(), task_name=LEDGER_UNLINK_OPERATION_DEFINITION_ID)
        if isinstance(settled, InvoiceUnlinkRefusedError):
            return await _publish_refusal(context, payload, settled)
        return await context.operands.put(LedgerUnlinkExecutionResult(result=settled), written_at=now())


def _supplied_actor(actor: str | None) -> str:
    return (actor or "operator").strip() or "operator"


def _resolved_invoice_id(selector: str, ports: LedgerActionPorts, bucket_id: str) -> str:
    """Resolve an exact invoice id or unambiguous prefix through the catalogue selection rule."""
    invoices = resolve_invoice_repository(bucket_id=bucket_id, repository=ports.invoice_repository).load()
    return select_catalogue_invoice_id(invoices.invoices.keys(), selector)


def _unlinked_result(
    payload: LedgerUnlinkRequest,
    result: InvoiceUnlinkResult,
    *,
    bucket_id: str,
    invoice_id: str,
    actor: str,
) -> LedgerUnlinkResult:
    """Copy the canonical unlinked row through the bounded public projection."""
    canonical = ledger_transaction_result_payload(
        build_manual_ledger_result(bucket_id, result.transaction, result.bucket_event_ids)
    )
    if canonical.bucket_id != bucket_id or result.transaction.transaction_id != canonical.transaction_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerUnlinkResult(
        outcome="unlinked",
        profile_id=payload.profile_id,
        transaction_id=payload.transaction_id,
        invoice_id=invoice_id,
        actor=actor,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction, language=payload.output_language),
        review_status=canonical.review_status,
        invoice_linked_transaction_ids=result.invoice.linked_transaction_ids,
        bucket_event_ids=result.bucket_event_ids,
    )


async def _publish_refusal(
    context: OperationExecutorContext,
    payload: LedgerUnlinkRequest,
    refusal: InvoiceUnlinkRefusedError,
) -> OperationRefusalEvidence:
    """Store one typed pre-write refusal as the receipt's refusal detail."""
    result = LedgerUnlinkResult(
        outcome="refused",
        profile_id=payload.profile_id,
        transaction_id=payload.transaction_id,
        invoice_id=payload.invoice_id,
        refusal=LedgerUnlinkRefusal(
            cause=refusal.cause,
            next_step=refusal.next_step,
            finalized_revisions=tuple(
                LedgerAttachmentStaleRevisionProjection.from_blocker(blocker) for blocker in refusal.blockers
            ),
        ),
    )
    execution_result = LedgerUnlinkExecutionResult(result=result)
    _check_result_size(execution_result)
    detail_ref = await context.operands.put(execution_result, written_at=now())
    return OperationRefusalEvidence(refusal_code=LEDGER_UNLINK_REFUSAL_CODE, detail_ref=detail_ref)


def _check_result_size(result: LedgerUnlinkExecutionResult) -> None:
    """Keep encrypted receipts within the bounded operation-result budget."""
    refuse_oversized_result(result, PROJECTION_RESULT_MAX_BYTES - 128)


def project_ledger_unlink_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerUnlinkResult:
    """Release only the result whose profile, outcome and effect match the receipt."""
    if type(result) is not LedgerUnlinkExecutionResult:
        raise ValueError("invalid ledger unlink execution result")
    projected = result.result
    subject_ref = profile_operation_subject(str(projected.profile_id))
    if projected.outcome == "refused":
        if (
            not terminal_receipt_matches(
                receipt,
                definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
                subject_ref=subject_ref,
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.NONE,
            )
            or receipt.refusal_ref != LEDGER_UNLINK_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
        ):
            raise ValueError("ledger unlink refusal has an incompatible terminal receipt")
        return projected
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        effect=OperationEffect.UPDATED,
        message="ledger unlink success has an incompatible terminal receipt",
    )
    return projected


def resolve_ledger_unlink_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact whole-profile unlinkage and reviewed result destination consent, as the link does."""
    payload = request.payload
    if (
        request.definition_id != LEDGER_UNLINK_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerUnlinkRequest
        or not isinstance(payload, LedgerUnlinkRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_export_link_access(request, context, profile_id=payload.profile_id, periods=frozenset[Period]())


def build_ledger_unlink_definition(
    factory: LedgerActionPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare the receipt-backed removal of one movement's invoice link, with the link's capabilities."""
    return build_single_phase_definition(
        definition_id=LEDGER_UNLINK_OPERATION_DEFINITION_ID,
        request_type=LedgerUnlinkRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerUnlinkExecutionResult,
        executor_type=LedgerUnlinkExecutor,
        build=lambda: LedgerUnlinkExecutor(factory, execution_caller_reader=execution_caller_reader),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        refusal_detail_codes=frozenset({LEDGER_UNLINK_REFUSAL_CODE}),
    )


def build_ledger_unlink_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the unlink's closed schemas and exact-profile resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerUnlinkResult,
        result_projector=project_ledger_unlink_result,
        access_resolver=resolve_ledger_unlink_access,
    )


__all__ = [
    "LEDGER_UNLINK_OPERATION_DEFINITION_ID",
    "LEDGER_UNLINK_REFUSAL_CODE",
    "LedgerUnlinkExecutionResult",
    "LedgerUnlinkExecutor",
    "LedgerUnlinkRefusal",
    "LedgerUnlinkRequest",
    "LedgerUnlinkResult",
    "build_ledger_unlink_definition",
    "build_ledger_unlink_registration",
    "resolve_ledger_unlink_access",
]
