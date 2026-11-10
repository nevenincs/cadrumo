"""Encrypted ledger selection under the exact profile and canonical filter scope."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, PositiveInt, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.transactions.models import Transaction
from ..aggregation.received_invoice_withholding import (
    MovementWithholding,
    received_invoice_movement_withholding,
    states_received_retencion,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..review.errors import FilterParseError
from ..review.filter import LedgerReviewFilterSpec
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import display_decimal
from .list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from .manual_read import ledger_transaction_payload
from .read_access import resolve_ledger_read_access
from .read_ports import LedgerReadPorts, LedgerReadPortsFactory
from .review_projection import ledger_transaction_review_status
from .transaction_projection import (
    LedgerMovementWithholdingProjection,
    LedgerTransactionProjection,
    LedgerTransactionReviewProjection,
    classification_reason_source,
    classification_reason_words,
)


def _withholding_projection(withholding: MovementWithholding) -> LedgerMovementWithholdingProjection:
    return LedgerMovementWithholdingProjection(
        invoice_id=withholding.invoice_id,
        invoice_number=withholding.invoice_number,
        modelo=withholding.modelo,
        scheme=None if withholding.scheme is None else withholding.scheme.value,
        retencion=None if withholding.retencion is None else display_decimal(withholding.retencion),
        recognised_on=None if withholding.recognised_on is None else withholding.recognised_on.isoformat(),
        held_back=None if withholding.held_back is None else withholding.held_back.value,
    )


def ledger_list_row(
    transaction: Transaction,
    *,
    withholding: tuple[MovementWithholding, ...] = (),
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
) -> LedgerTransactionReviewProjection:
    """One listed row: the canonical payload plus the list's own facts, its reason's words said in ``language``.

    ``withholding`` is what the invoices this movement pays leave on it, as the
    declarations read it; empty when it pays none that states a retención.
    """
    source = classification_reason_source(transaction.classification_reason)
    words = classification_reason_words(source, language)
    return LedgerTransactionReviewProjection(
        transaction=LedgerTransactionProjection.from_payload(ledger_transaction_payload(transaction)),
        review_status=ledger_transaction_review_status(transaction),
        group_label=transaction.group_label,
        own_account_id=transaction.own_account_id,
        classification_reason_source=source,
        classification_reason_words=words,
        classification_reason_words_language=language if words else None,
        withholding=tuple(_withholding_projection(item) for item in withholding),
    )


def listed_movement_withholding(
    transactions: tuple[Transaction, ...], *, bucket_id: str, ports: LedgerReadPorts
) -> Mapping[str, tuple[MovementWithholding, ...]]:
    """Read, for the listed ``transactions``, the retención each carries through the declarations' own reading.

    The whole movement catalogue is read only when some received invoice states
    a retención, because an invoice's retención is shared among all its payments
    and a payment outside the listed window changes each one's share.
    """
    invoices = ports.invoice_repository.load()
    if not states_received_retencion(invoices, bucket_id=bucket_id):
        return dict[str, tuple[MovementWithholding, ...]]()
    listed = {transaction.transaction_id for transaction in transactions}
    found = received_invoice_movement_withholding(invoices, ports.transaction_repository.load(), bucket_id=bucket_id)
    return {transaction_id: rows for transaction_id, rows in found.items() if transaction_id in listed}


LEDGER_LIST_OPERATION_DEFINITION_ID = "ledger.list"


class LedgerListRequest(BaseModel):
    """Private filter input stored only in the encrypted operand repository."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filters: tuple[str, ...] = ()
    group: str | None = None
    by_group: bool = False
    limit: PositiveInt | None = None
    offset: NonNegativeInt = 0
    sort_by: LedgerSortField | None = None
    sort_order: LedgerSortOrder = LedgerSortOrder.ASC
    exclude_llm_rejected: bool = False
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    def filter_spec(self) -> LedgerReviewFilterSpec:
        """Resolve scope and execution through the same canonical grammar."""
        try:
            return LedgerReviewFilterSpec.from_strings(self.filters)
        except FilterParseError:
            raise ValueError("invalid ledger selection filters") from None

    @model_validator(mode="after")
    def valid_filters(self) -> LedgerListRequest:
        """Refuse invalid clauses without echoing private values in diagnostics."""
        self.filter_spec()
        return self


class LedgerListProjection(BaseModel):
    """Canonical selected rows and truthful paging facts captured in custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: tuple[LedgerTransactionReviewProjection, ...]
    total: NonNegativeInt
    truncated: bool
    offset: NonNegativeInt
    limit: PositiveInt | None
    by_group: bool

    @model_validator(mode="after")
    def consistent_window(self) -> LedgerListProjection:
        """Reject impossible page totals or duplicated canonical rows."""
        available = max(self.total - self.offset, 0)
        shown = available if self.limit is None else min(available, self.limit)
        if len(self.rows) != shown:
            raise ValueError("ledger page length does not match its declared window")
        expected_truncated = self.offset > 0 or (self.limit is not None and self.offset + self.limit < self.total)
        if self.truncated != expected_truncated:
            raise ValueError("ledger page truncation does not match its declared window")
        if len({row.transaction.transaction_id for row in self.rows}) != len(self.rows):
            raise ValueError("ledger page repeats a transaction")
        return self


class LedgerListExecutor:
    """Host the canonical list query without frontend persistence access."""

    def __init__(self, ports: LedgerReadPortsFactory) -> None:
        """Retain the exact-profile port factory."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerListRequest], context: OperationExecutorContext) -> str:
        """Publish selected financial facts as an encrypted no-effect result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_LIST_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_LIST_OPERATION_DEFINITION_ID)

        def read() -> LedgerListProjection:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            page = query_ledger_transaction_list(
                LedgerTransactionListQuery(
                    spec=payload.filter_spec(),
                    group=payload.group,
                    by_group=payload.by_group,
                    limit=payload.limit,
                    offset=payload.offset,
                    sort_by=payload.sort_by,
                    sort_order=payload.sort_order,
                    exclude_llm_rejected=payload.exclude_llm_rejected,
                ),
                bucket_id=bucket_id,
                ports=ports,
            )
            if page.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            withholding = listed_movement_withholding(
                tuple(item.transaction for item in page.results), bucket_id=bucket_id, ports=ports
            )
            return LedgerListProjection(
                profile_id=payload.profile_id,
                rows=tuple(
                    ledger_list_row(
                        item.transaction,
                        withholding=withholding.get(item.transaction.transaction_id, ()),
                        language=payload.output_language,
                    )
                    for item in page.results
                ),
                total=page.total,
                truncated=page.truncated,
                offset=payload.offset,
                limit=payload.limit,
                by_group=payload.by_group,
            )

        return await capture_read_result(context, read, task_name="ledger-list")


def build_ledger_list_definition(ports: LedgerReadPortsFactory) -> OperationDefinition:
    """Register a private-query read without commit or provider authority."""
    return build_single_phase_definition(
        definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
        request_type=LedgerListRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerListProjection,
        executor_type=LedgerListExecutor,
        build=lambda: LedgerListExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Derive period authority from the immutable canonical filter, never caller scope hints."""
    if request.definition_id != LEDGER_LIST_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerListRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = request.payload.filter_spec().period
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset({period}) if period is not None else frozenset(),
    )


def build_ledger_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind encrypted selection schemas to canonical period-scope evaluation."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerListProjection,
        access_resolver=resolve_ledger_list_access,
    )
