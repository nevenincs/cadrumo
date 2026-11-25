"""Exact-session dispatch and receipt correlation for the invoice and transaction record doors and the link submitter."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

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
from cadrumo.application.invoices.catalogue_selection import InvoiceLookupRefusalReason, InvoiceLookupRefusedError
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
    LedgerLinkProjection,
    LedgerLinkRequest,
    LedgerLinkValidationRefusedError,
)
from cadrumo.application.ledger.transaction_projection import LedgerTransactionProjection
from cadrumo.application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
    LedgerUpdateOperationResult,
    LedgerUpdatePatch,
    LedgerUpdateRequest,
)
from cadrumo.application.ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewProjection,
    LedgerViewRequest,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.invoices.enums import PaymentStatus
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.models import LedgerFlowState, LedgerLinkResultV1, LedgerLinkSubmissionV1
from cadrumo.entrypoints.tui.ledger.reconciliation import LedgerReconciliationScreen
from cadrumo.entrypoints.tui.ledger.tests.invoices_fixtures import (
    INVOICES_PROFILE_ID,
    invoice_snapshot,
    transaction_projection,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    LEDGER_SUGGESTED_INVOICE,
    ledger_reconciled_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1
from cadrumo.entrypoints.tui.tests.settling import settle
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.runtime_ledger_records import (
    RuntimeLedgerLinkSubmitterV1,
    RuntimeLedgerRecordDoorsV1,
    compose_runtime_ledger_link_submitter,
)
from .ledger_invoices_runtime_harness import (
    LAPSED_SESSION_ID,
    OTHER_PROFILE_ID,
    PROFILE_LABEL,
    Boundary,
    Settled,
    client_of,
    install,
)
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INVOICE = invoice_snapshot()
_INVOICE_ID = _INVOICE.invoice_id
_TRANSACTION = transaction_projection()
_TRANSACTION_ID = _TRANSACTION.transaction_id
_STALE_KEY = "tui.ledger.records.stale"
_REFUSAL_CODE = "ERROR_INVOICE_VALIDATION"
"""A registered refusal no record door reads as declared detail."""

type _Call = Callable[[RuntimeLedgerRecordDoorsV1, RuntimeLedgerLinkSubmitterV1], Coroutine[Any, Any, object]]


def _doors(boundary: Boundary) -> RuntimeLedgerRecordDoorsV1:
    return RuntimeLedgerRecordDoorsV1(client_of(boundary), profile_label=PROFILE_LABEL)


def _submitter(boundary: Boundary) -> RuntimeLedgerLinkSubmitterV1:
    return RuntimeLedgerLinkSubmitterV1(client_of(boundary), profile_label=PROFILE_LABEL)


def _unscoped(snapshot: CatalogueInvoiceSnapshot) -> CatalogueInvoiceSnapshot:
    """The snapshot without a bucket, so a result for another profile can carry it."""
    return snapshot.model_copy(update={"bucket_id": None})


def _list(profile: UUID = INVOICES_PROFILE_ID) -> InvoiceListProjection:
    invoices = (_INVOICE,) if profile == INVOICES_PROFILE_ID else (_unscoped(_INVOICE),)
    return InvoiceListProjection(profile_id=profile, kind=None, invoices=invoices)


def _view(snapshot: CatalogueInvoiceSnapshot = _INVOICE, profile: UUID = INVOICES_PROFILE_ID) -> InvoiceViewProjection:
    return InvoiceViewProjection(
        profile_id=profile, invoice_id=snapshot.invoice_id, outcome=InvoiceViewSuccess(invoice=snapshot)
    )


def _updated(snapshot: CatalogueInvoiceSnapshot, profile: UUID = INVOICES_PROFILE_ID) -> InvoiceUpdateResult:
    return InvoiceUpdateResult(
        profile_id=profile, invoice_id=snapshot.invoice_id, invoice=snapshot, bucket_event_ids=("e1",)
    )


def _removed(snapshot: CatalogueInvoiceSnapshot = _INVOICE, profile: UUID = INVOICES_PROFILE_ID) -> InvoiceRemoveResult:
    return InvoiceRemoveResult(profile_id=profile, invoice_id=snapshot.invoice_id, invoice=snapshot)


def _ledger_view(
    transaction: LedgerTransactionProjection = _TRANSACTION, profile: UUID = INVOICES_PROFILE_ID
) -> LedgerViewProjection:
    return LedgerViewProjection(
        profile_id=profile,
        transaction_prefix=_TRANSACTION_ID,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        latest_llm_rejection=None,
    )


def _ledger_updated(
    transaction: LedgerTransactionProjection, profile: UUID = INVOICES_PROFILE_ID
) -> LedgerUpdateOperationResult:
    return LedgerUpdateOperationResult(
        outcome="updated",
        profile_id=profile,
        source_transaction_id=_TRANSACTION_ID,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e1",),
    )


def _linked(profile: UUID = INVOICES_PROFILE_ID, invoice_id: str = _INVOICE_ID) -> LedgerLinkOperationResult:
    linked = transaction_projection(invoice_id=invoice_id)
    return LedgerLinkOperationResult(
        profile_id=profile,
        transaction_id=_TRANSACTION_ID,
        invoice_id=invoice_id,
        outcome="linked",
        projection=LedgerLinkProjection(
            profile_id=profile,
            bucket_id=str(profile),
            transaction_id=_TRANSACTION_ID,
            invoice_id=invoice_id,
            actor="operator",
            bucket_event_ids=("e1",),
            review_status=LedgerReviewStatus.PENDING,
            transaction=linked,
        ),
    )


def _link_submission(action_id: str = "operator.ledger.link") -> LedgerLinkSubmissionV1:
    return LedgerLinkSubmissionV1(
        action=ActionReference(action_id=lookup_action(action_id).action_id),
        transaction_id=_TRANSACTION_ID,
        invoice_id=_INVOICE_ID,
    )


_NOTES = CatalogueInvoicePatch(notes="corrected")
_PAID = CatalogueInvoicePatch(payment_status=PaymentStatus.PAID)
_DESCRIPTION = LedgerUpdatePatch(description="corrected")


def _call_invoices(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.invoices()


def _call_invoice(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.invoice(_INVOICE_ID)


def _call_update_invoice(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.update_invoice(_INVOICE, _NOTES)


def _call_mark_paid(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.update_invoice(_INVOICE, _PAID)


def _call_remove_invoice(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.remove_invoice(_INVOICE)


def _call_transaction(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.transaction(_TRANSACTION_ID)


def _call_update_transaction(
    doors: RuntimeLedgerRecordDoorsV1, _link: RuntimeLedgerLinkSubmitterV1
) -> Coroutine[Any, Any, object]:
    return doors.update_transaction(_TRANSACTION, _DESCRIPTION, ("description",))


def _call_link(_doors: RuntimeLedgerRecordDoorsV1, link: RuntimeLedgerLinkSubmitterV1) -> Coroutine[Any, Any, object]:
    return link(_link_submission())


def _run(call: _Call, boundary: Boundary) -> object:
    return asyncio.run(call(_doors(boundary), _submitter(boundary)))


# --- success: the exact request goes out and the settled result comes back -------------------------


def test_invoices_lists_the_catalogue_for_the_pinned_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = install(monkeypatch, Settled(INVOICE_LIST_OPERATION_DEFINITION_ID, _list()))
    assert asyncio.run(_doors(boundary).invoices()) == (_INVOICE,)
    assert boundary.payloads == [InvoiceListRequest(profile_id=INVOICES_PROFILE_ID)]
    assert boundary.reads == [(InvoiceListProjection, False)]


def test_invoice_reads_one_snapshot_and_raises_a_lookup_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = install(monkeypatch, Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()))
    assert asyncio.run(_doors(boundary).invoice(_INVOICE_ID)) == _INVOICE
    assert boundary.payloads == [InvoiceViewRequest(profile_id=INVOICES_PROFILE_ID, invoice_id=_INVOICE_ID)]
    assert boundary.reads == [(InvoiceViewProjection, True)]

    missing = InvoiceViewProjection(
        profile_id=INVOICES_PROFILE_ID,
        invoice_id=_INVOICE_ID,
        outcome=InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.NOT_FOUND),
    )
    boundary = install(
        monkeypatch,
        Settled(
            INVOICE_VIEW_OPERATION_DEFINITION_ID,
            missing,
            condition=OperationTerminalCondition.REFUSED,
            refusal_ref=INVOICE_VIEW_REFUSAL_CODE,
        ),
    )
    with pytest.raises(InvoiceLookupRefusedError) as raised:
        asyncio.run(_doors(boundary).invoice(_INVOICE_ID))
    assert raised.value.reason is InvoiceLookupRefusalReason.NOT_FOUND


def test_update_invoice_rereads_the_baseline_then_sends_only_the_patched_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrected = _INVOICE.model_copy(update={"notes": "corrected"})
    boundary = install(
        monkeypatch,
        Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
        Settled(INVOICE_UPDATE_OPERATION_DEFINITION_ID, _updated(corrected), effect=OperationEffect.UPDATED),
    )
    assert asyncio.run(_doors(boundary).update_invoice(_INVOICE, _NOTES)) == corrected
    assert boundary.definitions == [INVOICE_VIEW_OPERATION_DEFINITION_ID, INVOICE_UPDATE_OPERATION_DEFINITION_ID]
    assert boundary.payloads[1] == InvoiceUpdateRequest(
        profile_id=INVOICES_PROFILE_ID, invoice_id=_INVOICE_ID, patch=InvoiceUpdatePatch.from_patch(_NOTES)
    )


def test_remove_invoice_rereads_the_baseline_then_removes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = install(
        monkeypatch,
        Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
        Settled(INVOICE_REMOVE_OPERATION_DEFINITION_ID, _removed(), effect=OperationEffect.UPDATED),
    )
    assert asyncio.run(_doors(boundary).remove_invoice(_INVOICE)) == _INVOICE
    assert boundary.payloads[1] == InvoiceRemoveRequest(profile_id=INVOICES_PROFILE_ID, invoice_id=_INVOICE_ID)


def test_transaction_reads_and_update_transaction_corrects_the_seen_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrected = transaction_projection(description="corrected")
    boundary = install(
        monkeypatch,
        Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
        Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
        Settled(LEDGER_UPDATE_OPERATION_DEFINITION_ID, _ledger_updated(corrected), effect=OperationEffect.UPDATED),
    )
    doors = _doors(boundary)
    assert asyncio.run(doors.transaction(_TRANSACTION_ID)) == _TRANSACTION
    assert asyncio.run(doors.update_transaction(_TRANSACTION, _DESCRIPTION, ("description",))) == corrected
    assert boundary.payloads[0] == LedgerViewRequest(profile_id=INVOICES_PROFILE_ID, transaction_prefix=_TRANSACTION_ID)
    assert boundary.payloads[2] == LedgerUpdateRequest(
        profile_id=INVOICES_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        patch=_DESCRIPTION,
        patch_fields=("description",),
    )
    assert boundary.reads[2] == (LedgerUpdateOperationResult, True)


def test_a_transaction_validation_refusal_is_raised_with_its_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = LedgerUpdateOperationResult(
        outcome="validation_error", profile_id=INVOICES_PROFILE_ID, validation_messages=("amount: must be positive",)
    )
    boundary = install(
        monkeypatch,
        Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
        Settled(
            LEDGER_UPDATE_OPERATION_DEFINITION_ID,
            refused,
            condition=OperationTerminalCondition.REFUSED,
            refusal_ref=LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
        ),
    )
    with pytest.raises(TransactionValidationError) as raised:
        asyncio.run(_doors(boundary).update_transaction(_TRANSACTION, _DESCRIPTION, ("description",)))
    assert raised.value.translated_message == "tui.ledger.records.update_refused"
    assert raised.value.context == {"detail": "amount: must be positive"}


def test_link_submits_the_admitted_pair_and_raises_a_missing_invoice(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = install(
        monkeypatch, Settled(LEDGER_LINK_OPERATION_DEFINITION_ID, _linked(), effect=OperationEffect.UPDATED)
    )
    assert asyncio.run(_submitter(boundary)(_link_submission())) == LedgerLinkResultV1(
        transaction_id=_TRANSACTION_ID, invoice_id=_INVOICE_ID
    )
    assert boundary.payloads == [
        LedgerLinkRequest(profile_id=INVOICES_PROFILE_ID, transaction_id=_TRANSACTION_ID, invoice_id=_INVOICE_ID)
    ]
    assert boundary.reads == [(LedgerLinkOperationResult, True)]

    missing = LedgerLinkOperationResult(
        profile_id=INVOICES_PROFILE_ID,
        transaction_id=_TRANSACTION_ID,
        invoice_id=_INVOICE_ID,
        outcome="refused",
        reason="missing_invoice",
    )
    boundary = install(
        monkeypatch,
        Settled(
            LEDGER_LINK_OPERATION_DEFINITION_ID,
            missing,
            condition=OperationTerminalCondition.REFUSED,
            refusal_ref=LEDGER_LINK_VALIDATION_REFUSAL_CODE,
        ),
    )
    with pytest.raises(LedgerLinkValidationRefusedError) as raised:
        asyncio.run(_submitter(boundary)(_link_submission()))
    assert raised.value.translated_message == "tui.ledger.link.refused.missing_invoice"


def test_link_refuses_a_submission_under_another_action(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = install(monkeypatch)
    with pytest.raises(RefusalError) as raised:
        asyncio.run(_submitter(boundary)(_link_submission("operator.ledger.classify")))
    assert raised.value.reason is RefusalCode.INVALID_FRAME
    assert boundary.submissions == []


# --- stale baseline: a record that changed since it was opened is never written --------------------


@pytest.mark.parametrize(
    ("call", "reread", "error"),
    [
        (
            _call_update_invoice,
            Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view(invoice_snapshot(notes="theirs"))),
            InvoiceValidationError,
        ),
        (
            _call_remove_invoice,
            Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view(invoice_snapshot(notes="theirs"))),
            InvoiceValidationError,
        ),
        (
            _call_update_transaction,
            Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view(transaction_projection(description="theirs"))),
            TransactionValidationError,
        ),
    ],
)
def test_a_write_against_a_changed_record_is_refused_with_a_reload_hint(
    monkeypatch: pytest.MonkeyPatch,
    call: _Call,
    reread: Settled,
    error: type[Exception],
) -> None:
    boundary = install(monkeypatch, reread)
    with pytest.raises(error) as raised:
        _run(call, boundary)
    assert getattr(raised.value, "translated_message", None) == _STALE_KEY
    assert boundary.definitions == [reread.definition_id]


# --- correlation: a result the receipt does not support is refused ---------------------------------


@pytest.mark.parametrize(
    ("call", "script"),
    [
        # Another profile's result.
        (_call_invoices, (Settled(INVOICE_LIST_OPERATION_DEFINITION_ID, _list(OTHER_PROFILE_ID)),)),
        (
            _call_invoice,
            (Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view(_unscoped(_INVOICE), OTHER_PROFILE_ID)),),
        ),
        (
            _call_update_invoice,
            (
                Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
                Settled(
                    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
                    _updated(_unscoped(_INVOICE), OTHER_PROFILE_ID),
                    effect=OperationEffect.UPDATED,
                ),
            ),
        ),
        (
            _call_remove_invoice,
            (
                Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
                Settled(
                    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
                    _removed(_unscoped(_INVOICE), OTHER_PROFILE_ID),
                    effect=OperationEffect.UPDATED,
                ),
            ),
        ),
        (_call_transaction, (Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view(profile=OTHER_PROFILE_ID)),)),
        (
            _call_update_transaction,
            (
                Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
                Settled(
                    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
                    _ledger_updated(_TRANSACTION, OTHER_PROFILE_ID),
                    effect=OperationEffect.UPDATED,
                ),
            ),
        ),
        (
            _call_link,
            (Settled(LEDGER_LINK_OPERATION_DEFINITION_ID, _linked(OTHER_PROFILE_ID), effect=OperationEffect.UPDATED),),
        ),
        # A wrong effect: a read that claims a change, a write that claims none.
        (_call_invoices, (Settled(INVOICE_LIST_OPERATION_DEFINITION_ID, _list(), effect=OperationEffect.UPDATED),)),
        (_call_invoice, (Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view(), effect=OperationEffect.UPDATED),)),
        (
            _call_update_invoice,
            (
                Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
                Settled(INVOICE_UPDATE_OPERATION_DEFINITION_ID, _updated(_INVOICE), effect=OperationEffect.NONE),
            ),
        ),
        (
            _call_remove_invoice,
            (
                Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
                Settled(INVOICE_REMOVE_OPERATION_DEFINITION_ID, _removed(), effect=OperationEffect.NONE),
            ),
        ),
        (
            _call_transaction,
            (Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view(), effect=OperationEffect.UPDATED),),
        ),
        (
            _call_update_transaction,
            (
                Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
                Settled(
                    LEDGER_UPDATE_OPERATION_DEFINITION_ID, _ledger_updated(_TRANSACTION), effect=OperationEffect.NONE
                ),
            ),
        ),
        (_call_link, (Settled(LEDGER_LINK_OPERATION_DEFINITION_ID, _linked(), effect=OperationEffect.NONE),)),
        # A committed correction that does not carry the value sent.
        (
            _call_mark_paid,
            (
                Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
                Settled(INVOICE_UPDATE_OPERATION_DEFINITION_ID, _updated(_INVOICE), effect=OperationEffect.UPDATED),
            ),
        ),
    ],
)
def test_a_result_its_receipt_does_not_support_is_refused(
    monkeypatch: pytest.MonkeyPatch, call: _Call, script: tuple[Settled, ...]
) -> None:
    boundary = install(monkeypatch, *script)
    # The last scripted operation is the one whose result is refused; earlier ones are its fresh reads.
    with raises_unsupported_result(script[-1].effect, script[-1].contract):
        _run(call, boundary)


_CALLS_AND_DEFINITIONS: tuple[tuple[_Call, tuple[str, ...]], ...] = (
    (_call_invoices, (INVOICE_LIST_OPERATION_DEFINITION_ID,)),
    (_call_invoice, (INVOICE_VIEW_OPERATION_DEFINITION_ID,)),
    (_call_update_invoice, (INVOICE_VIEW_OPERATION_DEFINITION_ID, INVOICE_UPDATE_OPERATION_DEFINITION_ID)),
    (_call_remove_invoice, (INVOICE_VIEW_OPERATION_DEFINITION_ID, INVOICE_REMOVE_OPERATION_DEFINITION_ID)),
    (_call_transaction, (LEDGER_VIEW_OPERATION_DEFINITION_ID,)),
    (_call_update_transaction, (LEDGER_VIEW_OPERATION_DEFINITION_ID, LEDGER_UPDATE_OPERATION_DEFINITION_ID)),
    (_call_link, (LEDGER_LINK_OPERATION_DEFINITION_ID,)),
)


def _prior_reads(definitions: tuple[str, ...]) -> tuple[Settled, ...]:
    """The successful re-read a write performs before its own submission."""
    if definitions[0] == INVOICE_VIEW_OPERATION_DEFINITION_ID and len(definitions) > 1:
        return (Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),)
    if definitions[0] == LEDGER_VIEW_OPERATION_DEFINITION_ID and len(definitions) > 1:
        return (Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),)
    return ()


@pytest.mark.parametrize(("call", "definitions"), _CALLS_AND_DEFINITIONS)
def test_a_refusal_receipt_raises_its_recorded_error_or_bare_code(
    monkeypatch: pytest.MonkeyPatch, call: _Call, definitions: tuple[str, ...]
) -> None:
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_REFUSAL_CODE,
        message_key="errors.error.error_invoice_validation",
        context=(),
    )
    refused = Settled(definitions[-1], None, condition=OperationTerminalCondition.REFUSED, refusal_ref=_REFUSAL_CODE)
    boundary = install(monkeypatch, *_prior_reads(definitions), replace(refused, detail=detail))
    with pytest.raises(RecordedRegisteredError) as recorded:
        _run(call, boundary)
    assert recorded.value.recorded_code == _REFUSAL_CODE
    assert boundary.definitions == list(definitions)

    boundary = install(monkeypatch, *_prior_reads(definitions), refused)
    with pytest.raises(FrontendRefusedError) as bare:
        _run(call, boundary)
    assert bare.value.reason == _REFUSAL_CODE


@pytest.mark.parametrize(("call", "definitions"), _CALLS_AND_DEFINITIONS)
def test_a_lapsed_session_submits_nothing(
    monkeypatch: pytest.MonkeyPatch, call: _Call, definitions: tuple[str, ...]
) -> None:
    del definitions
    boundary = install(monkeypatch)
    doors, submitter = _doors(boundary), _submitter(boundary)
    boundary.client.session_id = LAPSED_SESSION_ID
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(call(doors, submitter))
    assert boundary.submissions == []


def _successes(call: _Call) -> tuple[Settled, ...]:
    """The scripted terminal states that settle ``call`` successfully, re-reads included."""
    corrected = _INVOICE.model_copy(update={"notes": "corrected"})
    scripts: dict[_Call, tuple[Settled, ...]] = {
        _call_invoices: (Settled(INVOICE_LIST_OPERATION_DEFINITION_ID, _list()),),
        _call_invoice: (Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),),
        _call_update_invoice: (
            Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
            Settled(INVOICE_UPDATE_OPERATION_DEFINITION_ID, _updated(corrected), effect=OperationEffect.UPDATED),
        ),
        _call_remove_invoice: (
            Settled(INVOICE_VIEW_OPERATION_DEFINITION_ID, _view()),
            Settled(INVOICE_REMOVE_OPERATION_DEFINITION_ID, _removed(), effect=OperationEffect.UPDATED),
        ),
        _call_transaction: (Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),),
        _call_update_transaction: (
            Settled(LEDGER_VIEW_OPERATION_DEFINITION_ID, _ledger_view()),
            Settled(
                LEDGER_UPDATE_OPERATION_DEFINITION_ID,
                _ledger_updated(transaction_projection(description="corrected")),
                effect=OperationEffect.UPDATED,
            ),
        ),
        _call_link: (Settled(LEDGER_LINK_OPERATION_DEFINITION_ID, _linked(), effect=OperationEffect.UPDATED),),
    }
    return scripts[call]


@pytest.mark.parametrize(("call", "definitions"), _CALLS_AND_DEFINITIONS)
def test_each_door_reads_its_session_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch, call: _Call, definitions: tuple[str, ...]
) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    boundary = install(monkeypatch, *_successes(call))
    doors, submitter = _doors(boundary), _submitter(boundary)
    boundary.session_read_threads.clear()

    asyncio.run(call(doors, submitter))

    assert boundary.definitions == list(definitions)
    assert boundary.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in boundary.session_read_threads


@pytest.mark.asyncio
async def test_the_reconciliation_area_links_a_suggestion_through_the_runtime_submitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = install(
        monkeypatch,
        Settled(
            LEDGER_LINK_OPERATION_DEFINITION_ID,
            _linked(invoice_id=LEDGER_SUGGESTED_INVOICE),
            effect=OperationEffect.UPDATED,
        ),
    )
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        ledger_reconciled_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            link_action=ActionReference(action_id=lookup_action("operator.ledger.link").action_id),
            link_submitter=compose_runtime_ledger_link_submitter(client_of(boundary), profile_label=PROFILE_LABEL),
        ),
    )
    screen = LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
    assert boundary.payloads == [
        LedgerLinkRequest(
            profile_id=INVOICES_PROFILE_ID, transaction_id=_TRANSACTION_ID, invoice_id=LEDGER_SUGGESTED_INVOICE
        )
    ]
