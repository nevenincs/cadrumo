"""Invoice and transaction records, and invoice links, through the installed TUI's retained runtime session.

Every read and write is a registered operation submitted for the exact profile
and session the workbench was admitted under. Neither registered update takes
the record the operator saw, so each write first re-reads the record and
refuses when it differs from that baseline; a change landing between that
re-read and the write is not detected here.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from cadrumo.application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_REFUSAL_CODE,
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceViewProjection,
    InvoiceViewRefusal,
    InvoiceViewRequest,
    InvoiceViewSuccess,
)
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from cadrumo.application.invoices.catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveRequest,
    InvoiceRemoveResult,
)
from cadrumo.application.invoices.catalogue_selection import InvoiceLookupRefusedError
from cadrumo.application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdatePatch,
    InvoiceUpdateRequest,
    InvoiceUpdateResult,
)
from cadrumo.application.ledger.link_operation import (
    LEDGER_LINK_OPERATION_DEFINITION_ID,
    LEDGER_LINK_VALIDATION_REFUSAL_CODE,
    LedgerLinkOperationResult,
    LedgerLinkRequest,
    LedgerLinkValidationRefusedError,
)
from cadrumo.application.ledger.transaction_projection import LedgerTransactionProjection
from cadrumo.application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
    LedgerUpdateOperationResult,
    LedgerUpdatePatch,
    LedgerUpdatePatchField,
    LedgerUpdateRequest,
)
from cadrumo.application.ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewProjection,
    LedgerViewRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.entrypoints.tui.ledger.models import (
    LedgerLinkResultV1,
    LedgerLinkSubmissionV1,
    LedgerLinkSubmitterV1,
    LedgerRecordDoorsV1,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession

_STALE_RECORD_KEY = "tui.ledger.records.stale"
"""The refusal shown when a record changed after the operator opened it."""

_INVOICE_PATCH_ECHOED = ("payment_status", "operation_type", "operation_date")
"""Typed patch fields the committed snapshot must carry exactly as sent; text fields may be normalised."""

type _Settle[ResultT] = Callable[[ResultT, OperationTerminalCondition, OperationPublicProjectionV1, str], None]


def _succeeded(
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    effect: OperationEffect,
) -> bool:
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.failure_error_code is None
        and terminal.effect is effect
    )


def _refused_with(
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    code: str,
) -> bool:
    return (
        condition is OperationTerminalCondition.REFUSED
        and terminal.refusal_ref == code
        and terminal.effect is OperationEffect.NONE
    )


def _invalid() -> RefusalError:
    return RefusalError(RefusalCode.INVALID_FRAME)


def _patch_is_echoed(invoice: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch) -> bool:
    """Whether every selected field the snapshot carries verbatim holds the patched value."""
    return all(
        getattr(invoice, name) == getattr(patch, name)
        for name in _INVOICE_PATCH_ECHOED
        if name in patch.model_fields_set
    )


class RuntimeLedgerRecordDoorsV1:
    """Read, correct and remove the exact TUI profile's invoices, and read and correct its transactions."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request names."""
        return self._session.profile_id

    async def invoices(self) -> tuple[CatalogueInvoiceSnapshot, ...]:
        """List the whole invoice catalogue through ``ledger.invoice.list``."""
        request = InvoiceListRequest(profile_id=self.profile_id)

        def settle(
            result: InvoiceListProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                _succeeded(condition, terminal, OperationEffect.NONE)
                and result.profile_id == request.profile_id
                and result.kind is request.kind
            ):
                raise _invalid()

        result = await self._run(request, INVOICE_LIST_OPERATION_DEFINITION_ID, InvoiceListProjection, settle)
        return result.invoices

    async def invoice(self, invoice_id: str) -> CatalogueInvoiceSnapshot:
        """Resolve one invoice through ``ledger.invoice.view``, raising its lookup refusal."""
        request = InvoiceViewRequest(profile_id=self.profile_id, invoice_id=invoice_id)

        def settle(
            result: InvoiceViewProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if result.profile_id != request.profile_id or result.invoice_id != request.invoice_id:
                raise _invalid()
            outcome = result.outcome
            if isinstance(outcome, InvoiceViewRefusal):
                if not _refused_with(condition, terminal, INVOICE_VIEW_REFUSAL_CODE):
                    raise _invalid()
                raise InvoiceLookupRefusedError(
                    reason=outcome.reason, invoice_id=request.invoice_id, candidate_ids=outcome.candidate_ids
                )
            if not _succeeded(condition, terminal, OperationEffect.NONE) or outcome.invoice.invoice_id != invoice_id:
                raise _invalid()

        result = await self._run(
            request, INVOICE_VIEW_OPERATION_DEFINITION_ID, InvoiceViewProjection, settle, allow_refusal_detail=True
        )
        if not isinstance(result.outcome, InvoiceViewSuccess):
            raise _invalid()
        return result.outcome.invoice

    async def _require_current_invoice(self, baseline: CatalogueInvoiceSnapshot) -> None:
        if await self.invoice(baseline.invoice_id) != baseline:
            raise InvoiceValidationError(translated_message=_STALE_RECORD_KEY, context={})

    async def update_invoice(
        self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch
    ) -> CatalogueInvoiceSnapshot:
        """Correct the invoice the operator saw through ``ledger.invoice.update``."""
        await self._require_current_invoice(baseline)
        request = InvoiceUpdateRequest(
            profile_id=self.profile_id, invoice_id=baseline.invoice_id, patch=InvoiceUpdatePatch.from_patch(patch)
        )

        def settle(
            result: InvoiceUpdateResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                _succeeded(condition, terminal, OperationEffect.UPDATED)
                and result.profile_id == request.profile_id
                and result.invoice_id == request.invoice_id
                and result.invoice.invoice_id == baseline.invoice_id
                and _patch_is_echoed(result.invoice, patch)
            ):
                raise _invalid()

        result = await self._run(request, INVOICE_UPDATE_OPERATION_DEFINITION_ID, InvoiceUpdateResult, settle)
        return result.invoice

    async def remove_invoice(self, baseline: CatalogueInvoiceSnapshot) -> CatalogueInvoiceSnapshot:
        """Remove the invoice the operator saw through ``ledger.invoice.remove``."""
        await self._require_current_invoice(baseline)
        request = InvoiceRemoveRequest(profile_id=self.profile_id, invoice_id=baseline.invoice_id)

        def settle(
            result: InvoiceRemoveResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                _succeeded(condition, terminal, OperationEffect.UPDATED)
                and result.profile_id == request.profile_id
                and result.invoice_id == request.invoice_id
                and result.invoice.invoice_id == baseline.invoice_id
            ):
                raise _invalid()

        result = await self._run(request, INVOICE_REMOVE_OPERATION_DEFINITION_ID, InvoiceRemoveResult, settle)
        return result.invoice

    async def transaction(self, transaction_id: str) -> LedgerTransactionProjection:
        """Resolve one transaction through ``ledger.view``."""
        request = LedgerViewRequest(profile_id=self.profile_id, transaction_prefix=transaction_id)

        def settle(
            result: LedgerViewProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                _succeeded(condition, terminal, OperationEffect.NONE)
                and result.profile_id == request.profile_id
                and result.transaction_prefix == request.transaction_prefix
            ):
                raise _invalid()

        result = await self._run(request, LEDGER_VIEW_OPERATION_DEFINITION_ID, LedgerViewProjection, settle)
        return result.transaction

    async def update_transaction(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> LedgerTransactionProjection:
        """Apply the selected fields to the transaction the operator saw through ``ledger.update``."""
        if await self.transaction(baseline.transaction_id) != baseline:
            raise TransactionValidationError(translated_message=_STALE_RECORD_KEY, context={})
        request = LedgerUpdateRequest(
            profile_id=self.profile_id, transaction_id=baseline.transaction_id, patch=patch, patch_fields=fields
        )

        def settle(
            result: LedgerUpdateOperationResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if result.profile_id != request.profile_id:
                raise _invalid()
            if result.outcome == "validation_error":
                if not _refused_with(condition, terminal, LEDGER_UPDATE_VALIDATION_REFUSAL_CODE):
                    raise _invalid()
                raise TransactionValidationError(
                    translated_message="tui.ledger.records.update_refused",
                    context={"detail": "; ".join(result.validation_messages)},
                )
            effect = OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
            if not (
                _succeeded(condition, terminal, effect)
                and result.source_transaction_id == baseline.transaction_id
                and result.transaction is not None
            ):
                raise _invalid()

        result = await self._run(
            request,
            LEDGER_UPDATE_OPERATION_DEFINITION_ID,
            LedgerUpdateOperationResult,
            settle,
            allow_refusal_detail=True,
        )
        if result.transaction is None:
            raise _invalid()
        return result.transaction

    async def _run[ResultT: BaseModel](
        self,
        request: BaseModel,
        definition_id: str,
        result_type: type[ResultT],
        settle: _Settle[ResultT],
        *,
        allow_refusal_detail: bool = False,
    ) -> ResultT:
        return await self._session.run_operation(
            request,
            definition_id=definition_id,
            result_type=result_type,
            settle=settle,
            allow_refusal_detail=allow_refusal_detail,
            explain_failure=True,
        )


class RuntimeLedgerLinkSubmitterV1:
    """Link one invoice to one transaction of the exact TUI profile through ``ledger.link``."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every link."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        """Submit the admitted pair and release only its settled identities."""
        if submission.action.action_id != lookup_action("operator.ledger.link").action_id:
            raise _invalid()
        request = LedgerLinkRequest(
            profile_id=self._session.profile_id,
            transaction_id=submission.transaction_id,
            invoice_id=submission.invoice_id,
        )

        def settle(
            result: LedgerLinkOperationResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if (
                result.profile_id != request.profile_id
                or result.transaction_id != request.transaction_id
                or result.invoice_id != request.invoice_id
            ):
                raise _invalid()
            if result.outcome == "refused":
                if not _refused_with(condition, terminal, LEDGER_LINK_VALIDATION_REFUSAL_CODE) or result.reason is None:
                    raise _invalid()
                raise LedgerLinkValidationRefusedError(
                    translated_message=f"tui.ledger.link.refused.{result.reason}", context={}
                )
            projection = result.projection
            if (
                not _succeeded(condition, terminal, OperationEffect.UPDATED)
                or projection is None
                or projection.transaction_id != request.transaction_id
                or projection.transaction.invoice_id != request.invoice_id
            ):
                raise _invalid()

        await self._session.run_operation(
            request,
            definition_id=LEDGER_LINK_OPERATION_DEFINITION_ID,
            result_type=LedgerLinkOperationResult,
            settle=settle,
            allow_refusal_detail=True,
            explain_failure=True,
        )
        return LedgerLinkResultV1(transaction_id=submission.transaction_id, invoice_id=submission.invoice_id)


def compose_runtime_ledger_record_doors(client: FrontendClient, *, profile_label: str) -> LedgerRecordDoorsV1:
    """Bind the invoice catalogue and record detail screens to the workbench's runtime client."""
    return RuntimeLedgerRecordDoorsV1(client, profile_label=profile_label)


def compose_runtime_ledger_link_submitter(client: FrontendClient, *, profile_label: str) -> LedgerLinkSubmitterV1:
    """Bind the reconciliation link flow to the workbench's runtime client."""
    return RuntimeLedgerLinkSubmitterV1(client, profile_label=profile_label)


__all__ = [
    "RuntimeLedgerLinkSubmitterV1",
    "RuntimeLedgerRecordDoorsV1",
    "compose_runtime_ledger_link_submitter",
    "compose_runtime_ledger_record_doors",
]
