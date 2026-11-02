"""Registered read of which movement settles which invoice, and the choices for a by-hand link.

It proposes and ranks; it links nothing and writes nothing. The answer names movements and invoices
by id, so the caller shows the records it already holds. Staged links the person has not saved yet
are taken as given: a movement or invoice one of them takes is offered to nothing else.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.identity.hex_ids import InvoiceId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.payment_matching import (
    PICK_HORIZON_DAYS,
    PaymentPair,
    PaymentSuggestion,
    invoice_choices,
    movement_choices,
    suggest_payments,
)
from ..ledger.read_access import resolve_ledger_request_read_access
from ..ledger.transaction_repository import transaction_catalogue_repository
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .inspection_read_ports import InvoiceInspectionReadPortsFactory

LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID: Final = "ledger.invoice.match"

# A window holds a handful of staged links at a time; the bound keeps the read small.
_MAX_STAGED_LINKS: Final = 1_024


class LedgerInvoiceMatchStagedLink(BaseModel):
    """A link the person has staged and not saved: the movement and the invoice it takes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    invoice_id: InvoiceId


class LedgerInvoiceMatchRequest(CredentialFreeOperationRequest):
    """What to propose, given the links already staged.

    With ``invoice_id`` only that invoice is weighed, and the open movements near its issue day come
    back as choices. With ``transaction_id`` the invoices of that movement's flow come back as
    choices, and only that movement's suggestion is returned.
    """

    profile_id: UUID
    staged: Annotated[tuple[LedgerInvoiceMatchStagedLink, ...], Field(max_length=_MAX_STAGED_LINKS)] = ()
    invoice_id: InvoiceId | None = None
    transaction_id: TransactionId | None = None


class LedgerInvoiceMatchPair(BaseModel):
    """One movement and one invoice that settle each other, and the evidence the pair stands on."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    invoice_id: InvoiceId
    #: The description names the invoice's number.
    number: bool
    #: Days from the invoice's date to the movement's; negative when paid first.
    gap: int
    #: The counterparty names overlap.
    counterparty: bool


class LedgerInvoiceMatchSuggestion(LedgerInvoiceMatchPair):
    """A movement's best invoice, with what competes with it."""

    #: Another candidate ranks exactly as well: the person chooses.
    ambiguous: bool
    #: Pairs ranking exactly as well that share this movement or this invoice.
    ties: tuple[LedgerInvoiceMatchPair, ...]
    #: The movement's other candidates.
    others: tuple[LedgerInvoiceMatchPair, ...]


class LedgerInvoiceMatchInvoiceChoice(BaseModel):
    """An invoice the movement may be linked to by hand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: InvoiceId
    #: The movement settles it by flow, currency and amount.
    settles: bool
    #: The movement a staged link already gives it to, when not this one.
    staged_for: TransactionId | None
    #: How many other movements are already linked to it.
    linked: int


class LedgerInvoiceMatchMovementChoice(BaseModel):
    """A movement the invoice may be linked to by hand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    settles: bool


class LedgerInvoiceMatchResult(BaseModel):
    """The suggestions newest movement first, and the choices the request asked for."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    suggestions: tuple[LedgerInvoiceMatchSuggestion, ...]
    #: How many days either side of an invoice's issue day the movement choices reach.
    window_days: int
    #: Invoices for the movement named by ``transaction_id``; None when none was named or it is gone.
    invoice_choices: tuple[LedgerInvoiceMatchInvoiceChoice, ...] | None = None
    #: Movements for the invoice named by ``invoice_id``; None when none was named or it is gone.
    movement_choices: tuple[LedgerInvoiceMatchMovementChoice, ...] | None = None


class LedgerInvoiceMatchExecutionResult(BaseModel):
    """Worker-side envelope of the answer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerInvoiceMatchResult


def _pair_out(pair: PaymentPair) -> LedgerInvoiceMatchPair:
    return LedgerInvoiceMatchPair(
        transaction_id=pair.transaction.transaction_id,
        invoice_id=pair.invoice.invoice_id,
        number=pair.number,
        gap=pair.gap,
        counterparty=pair.counterparty,
    )


def _suggestion_out(found: PaymentSuggestion) -> LedgerInvoiceMatchSuggestion:
    return LedgerInvoiceMatchSuggestion(
        **_pair_out(found.pair).model_dump(),
        ambiguous=found.ambiguous,
        ties=tuple(_pair_out(pair) for pair in found.ties),
        others=tuple(_pair_out(pair) for pair in found.others),
    )


class LedgerInvoiceMatchExecutor:
    """Weigh the exact profile's open movements against its unmatched invoices."""

    def __init__(self, factory: InvoiceInspectionReadPortsFactory) -> None:
        """Retain the declared invoice reader."""
        self._factory = factory

    def _answer(
        self, payload: LedgerInvoiceMatchRequest, operation: PinnedAuthorityOperation
    ) -> LedgerInvoiceMatchResult:
        profile = str(payload.profile_id)
        ports = self._factory(bucket_id=profile, operation=operation)
        if ports.bucket_id != profile or ports.invoices.bucket_id != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        catalogue = ports.invoices.load_authenticated()
        if any(bucket_id != profile for bucket_id in catalogue.attributed_bucket_ids()):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        stored = (catalogue.get(invoice_id) for invoice_id in sorted(catalogue.invoice_ids()))
        invoices = tuple(invoice for invoice in stored if invoice is not None)
        transactions = tuple(transaction_catalogue_repository(bucket_id=profile).load().values())
        staged = {link.transaction_id: link.invoice_id for link in payload.staged}
        weighed = tuple(invoice for invoice in invoices if payload.invoice_id in (None, invoice.invoice_id))
        found = suggest_payments(transactions, weighed, staged=staged)
        chosen_invoice = next((invoice for invoice in invoices if invoice.invoice_id == payload.invoice_id), None)
        chosen_movement = next(
            (transaction for transaction in transactions if transaction.transaction_id == payload.transaction_id),
            None,
        )
        return LedgerInvoiceMatchResult(
            profile_id=payload.profile_id,
            window_days=PICK_HORIZON_DAYS,
            suggestions=tuple(
                _suggestion_out(suggestion)
                for suggestion in found
                if payload.transaction_id in (None, suggestion.pair.transaction.transaction_id)
            ),
            invoice_choices=None
            if chosen_movement is None
            else tuple(
                LedgerInvoiceMatchInvoiceChoice(
                    invoice_id=choice.invoice.invoice_id,
                    settles=choice.settles,
                    staged_for=choice.staged_for,
                    linked=choice.linked,
                )
                for choice in invoice_choices(chosen_movement, invoices, staged=staged)
            ),
            movement_choices=None
            if chosen_invoice is None
            else tuple(
                LedgerInvoiceMatchMovementChoice(
                    transaction_id=choice.transaction.transaction_id, settles=choice.settles
                )
                for choice in movement_choices(chosen_invoice, transactions, staged=frozenset(staged))
            ),
        )

    async def execute(
        self,
        request: OperationRequest[LedgerInvoiceMatchRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from its stored movements and invoices."""
        payload = request.payload
        if request.definition_id != LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID)
        result = await asyncio.to_thread(self._answer, payload, context.authority_operation)
        return await context.operands.put(LedgerInvoiceMatchExecutionResult(result=result), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerInvoiceMatchExecutionResult:
        raise ValueError("invalid ledger invoice match result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger invoice match has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_invoice_match_definition(factory: InvoiceInspectionReadPortsFactory) -> OperationDefinition:
    """Declare the exact-profile read of which movement settles which invoice."""
    return build_single_phase_definition(
        definition_id=LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID,
        request_type=LedgerInvoiceMatchRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerInvoiceMatchExecutionResult,
        executor_type=LedgerInvoiceMatchExecutor,
        build=lambda: LedgerInvoiceMatchExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_ledger_invoice_match_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID,
        request_type=LedgerInvoiceMatchRequest,
    )


def build_ledger_invoice_match_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerInvoiceMatchResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_invoice_match_access,
    )


__all__ = [
    "LEDGER_INVOICE_MATCH_OPERATION_DEFINITION_ID",
    "LedgerInvoiceMatchExecutor",
    "LedgerInvoiceMatchInvoiceChoice",
    "LedgerInvoiceMatchMovementChoice",
    "LedgerInvoiceMatchPair",
    "LedgerInvoiceMatchRequest",
    "LedgerInvoiceMatchResult",
    "LedgerInvoiceMatchStagedLink",
    "LedgerInvoiceMatchSuggestion",
    "build_ledger_invoice_match_definition",
    "build_ledger_invoice_match_registration",
    "resolve_ledger_invoice_match_access",
]
