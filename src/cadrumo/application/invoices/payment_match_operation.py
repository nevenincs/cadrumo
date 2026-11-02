"""Registered read of which movement settles which invoice, and the choices for a by-hand link.

It proposes and ranks; it links nothing and writes nothing. The answer names movements and invoices
by id, so the caller shows the records it already holds. Staged links the person has not saved yet
are taken as given: a movement or invoice one of them takes is offered to nothing else.

Links the person is about to make permanent may also be named: each comes back with where its
movement and invoice do not agree, so the caller states the differences without judging them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.identity.hex_ids import InvoiceId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.models import Invoice
from ...domain.invoices.payment_matching import (
    PICK_HORIZON_DAYS,
    LinkDifference,
    PaymentPair,
    PaymentSuggestion,
    invoice_choices,
    link_differences,
    movement_choices,
    suggest_payments,
)
from ...domain.transactions.models import Transaction
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
from ..operations.public_scalar import PublicDecimal, project_scalar
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
    #: Links to state the differences of; they take nothing from the suggestions.
    judge: Annotated[tuple[LedgerInvoiceMatchStagedLink, ...], Field(max_length=_MAX_STAGED_LINKS)] = ()


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


class LedgerInvoiceMatchMismatch(BaseModel):
    """One way a judged movement and invoice do not agree; the fields besides ``kind`` are the kind's own."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["amount", "currency", "counterparty", "linked_elsewhere"]
    #: ``amount``: the magnitude of the movement's amount less what the invoice settles for.
    difference: PublicDecimal | None = None
    #: ``currency``: the movement's currency.
    movement: str | None = None
    #: ``currency``: the invoice's currency.
    invoice: str | None = None
    #: ``linked_elsewhere``: how many other movements already hold the invoice.
    count: int | None = None


class LedgerInvoiceMatchJudgement(BaseModel):
    """What stands against one named link; ``found`` is false when the movement or the invoice is gone."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    invoice_id: InvoiceId
    found: bool
    mismatches: tuple[LedgerInvoiceMatchMismatch, ...] = ()


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
    #: One judgement per link named in ``judge``, in the order named.
    judgements: tuple[LedgerInvoiceMatchJudgement, ...] = ()


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


def _mismatch_out(found: LinkDifference) -> LedgerInvoiceMatchMismatch:
    return LedgerInvoiceMatchMismatch(
        kind=found.kind,
        difference=None if found.difference is None else project_scalar(found.difference),
        movement=found.movement_currency,
        invoice=found.invoice_currency,
        count=found.count,
    )


def _suggestion_out(found: PaymentSuggestion) -> LedgerInvoiceMatchSuggestion:
    return LedgerInvoiceMatchSuggestion(
        **_pair_out(found.pair).model_dump(),
        ambiguous=found.ambiguous,
        ties=tuple(_pair_out(pair) for pair in found.ties),
        others=tuple(_pair_out(pair) for pair in found.others),
    )


def _load_profile_records(
    factory: InvoiceInspectionReadPortsFactory, profile: str, operation: PinnedAuthorityOperation
) -> tuple[tuple[Invoice, ...], tuple[Transaction, ...]]:
    """Return the exact profile's invoices and movements, refusing any record of another profile."""
    ports = factory(bucket_id=profile, operation=operation)
    if ports.bucket_id != profile or ports.invoices.bucket_id != profile:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    catalogue = ports.invoices.load_authenticated()
    if any(bucket_id != profile for bucket_id in catalogue.attributed_bucket_ids()):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    stored = (catalogue.get(invoice_id) for invoice_id in sorted(catalogue.invoice_ids()))
    invoices = tuple(invoice for invoice in stored if invoice is not None)
    transactions = tuple(transaction_catalogue_repository(bucket_id=profile).load().values())
    return invoices, transactions


def _judgement_out(
    link: LedgerInvoiceMatchStagedLink,
    by_movement: Mapping[TransactionId, Transaction],
    by_invoice: Mapping[InvoiceId, Invoice],
) -> LedgerInvoiceMatchJudgement:
    transaction = by_movement.get(link.transaction_id)
    invoice = by_invoice.get(link.invoice_id)
    if transaction is None or invoice is None:
        return LedgerInvoiceMatchJudgement(transaction_id=link.transaction_id, invoice_id=link.invoice_id, found=False)
    return LedgerInvoiceMatchJudgement(
        transaction_id=link.transaction_id,
        invoice_id=link.invoice_id,
        found=True,
        mismatches=tuple(_mismatch_out(found) for found in link_differences(transaction, invoice)),
    )


def _found[K, V](records: Mapping[K, V], key: K | None) -> V | None:
    return None if key is None else records.get(key)


def _suggestions_out(
    found: tuple[PaymentSuggestion, ...], transaction_id: TransactionId | None
) -> tuple[LedgerInvoiceMatchSuggestion, ...]:
    return tuple(
        _suggestion_out(suggestion)
        for suggestion in found
        if transaction_id in (None, suggestion.pair.transaction.transaction_id)
    )


def _invoice_choices_out(
    movement: Transaction | None, invoices: tuple[Invoice, ...], staged: Mapping[str, str]
) -> tuple[LedgerInvoiceMatchInvoiceChoice, ...] | None:
    if movement is None:
        return None
    return tuple(
        LedgerInvoiceMatchInvoiceChoice(
            invoice_id=choice.invoice.invoice_id,
            settles=choice.settles,
            staged_for=choice.staged_for,
            linked=choice.linked,
        )
        for choice in invoice_choices(movement, invoices, staged=staged)
    )


def _movement_choices_out(
    invoice: Invoice | None, transactions: tuple[Transaction, ...], staged: Mapping[str, str]
) -> tuple[LedgerInvoiceMatchMovementChoice, ...] | None:
    if invoice is None:
        return None
    return tuple(
        LedgerInvoiceMatchMovementChoice(transaction_id=choice.transaction.transaction_id, settles=choice.settles)
        for choice in movement_choices(invoice, transactions, staged=frozenset(staged))
    )


class LedgerInvoiceMatchExecutor:
    """Weigh the exact profile's open movements against its unmatched invoices."""

    def __init__(self, factory: InvoiceInspectionReadPortsFactory) -> None:
        """Retain the declared invoice reader."""
        self._factory = factory

    def _answer(
        self, payload: LedgerInvoiceMatchRequest, operation: PinnedAuthorityOperation
    ) -> LedgerInvoiceMatchResult:
        invoices, transactions = _load_profile_records(self._factory, str(payload.profile_id), operation)
        staged = {link.transaction_id: link.invoice_id for link in payload.staged}
        weighed = tuple(invoice for invoice in invoices if payload.invoice_id in (None, invoice.invoice_id))
        found = suggest_payments(transactions, weighed, staged=staged)
        by_invoice = {invoice.invoice_id: invoice for invoice in invoices}
        by_movement = {transaction.transaction_id: transaction for transaction in transactions}
        return LedgerInvoiceMatchResult(
            profile_id=payload.profile_id,
            judgements=tuple(_judgement_out(link, by_movement, by_invoice) for link in payload.judge),
            window_days=PICK_HORIZON_DAYS,
            suggestions=_suggestions_out(found, payload.transaction_id),
            invoice_choices=_invoice_choices_out(_found(by_movement, payload.transaction_id), invoices, staged),
            movement_choices=_movement_choices_out(_found(by_invoice, payload.invoice_id), transactions, staged),
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
    "LedgerInvoiceMatchJudgement",
    "LedgerInvoiceMatchMismatch",
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
