"""``aeat app ledger unlink`` reads both records as seen, submits its registered write, and correlates the result.

The command resolves the movement and the invoice exactly as ``aeat app ledger
view`` and the invoice reads resolve them, so the write's ``expected_*``
fields are never invented. A refusal surfaces as the typed
:class:`InvoiceUnlinkRefusedError`, mapped to the operator's own words for its
cause and next step.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ....application.ledger.attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from ....application.ledger.invoice_unlink import InvoiceUnlinkCause, InvoiceUnlinkNextStep, InvoiceUnlinkRefusedError
from ....application.ledger.manual_read import ledger_transaction_payload
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.ledger.unlink_operation import (
    LEDGER_UNLINK_OPERATION_DEFINITION_ID,
    LEDGER_UNLINK_REFUSAL_CODE,
    LedgerUnlinkRefusal,
    LedgerUnlinkRequest,
)
from ....application.ledger.unlink_operation import LedgerUnlinkResult as LedgerUnlinkOperationResult
from ....application.ledger.view_operation import LedgerViewProjection
from ....application.operations.models import OperationId
from ....application.review.filter import LedgerReviewStatus
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.tests.rental_link_rows import rental_row
from .. import ledger_commands as commands
from .. import operation_ledger_unlink as unlink_bridge
from ..command_specs import COMMAND_GRAPH
from ..ledger_results import LedgerUnlinkResult as UnlinkEnvelope
from .ledger_invoice_snapshot_support import received_invoice_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_CTX = cast(typer.Context, cast(object, None))


def _transaction(**fields: object) -> LedgerTransactionProjection:
    return LedgerTransactionProjection.from_payload(
        ledger_transaction_payload(rental_row(provider_id="unlink-target", **fields)), language=OutputLanguage.EN
    )


def _stale_revision() -> LedgerAttachmentStaleRevisionProjection:
    return LedgerAttachmentStaleRevisionProjection(
        work_unit_id="a" * 64,
        calculation_revision_id="b" * 64,
        revision_state="FINALIZADA",
        modelo="303",
        filing_year=filing_year_envelope().horizon,
        period="1T",
    )


def _invoice(*, linked_transaction_ids: tuple[str, ...] = ()) -> CatalogueInvoiceSnapshot:
    return received_invoice_snapshot(counterparty_tax_id=None).model_copy(
        update={"invoice_id": "c" * 64, "linked_transaction_ids": linked_transaction_ids}
    )


def _completion(
    projection: BaseModel,
    *,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_code: str | None = None,
) -> RegisteredOperationCompletion[BaseModel]:
    return RegisteredOperationCompletion(
        operation_id=cast("OperationId", "f" * 64),
        projection=projection,
        effect=effect,
        terminal_condition=condition,
        refusal_code=refusal_code,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    transaction: LedgerTransactionProjection,
    invoice: CatalogueInvoiceSnapshot,
    completion: RegisteredOperationCompletion[BaseModel],
) -> tuple[list[BaseModel], list[dict[str, object]]]:
    """Answer the two reads and the one submission, and capture what the command emits."""
    submitted: list[BaseModel] = []
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(unlink_bridge, "bound_profile_client", lambda _ctx: SimpleNamespace(profile_id=_PROFILE))
    monkeypatch.setattr(
        unlink_bridge,
        "read_ledger_view_for_cli",
        lambda _ctx, *, transaction_id: LedgerViewProjection(
            profile_id=_PROFILE,
            transaction_prefix=transaction_id,
            transaction=transaction,
            review_status=LedgerReviewStatus.REVIEWED,
            latest_llm_rejection=None,
        ),
    )
    monkeypatch.setattr(
        unlink_bridge,
        "view_invoice_catalogue",
        lambda _ctx, *, invoice_id: SimpleNamespace(completion=None, invoice=invoice),
    )

    def submit(_client: object, request: BaseModel, **kwargs: object) -> RegisteredOperationCompletion[BaseModel]:
        assert kwargs["definition_id"] == LEDGER_UNLINK_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["allow_refusal_detail"] is True
        submitted.append(request)
        return completion

    monkeypatch.setattr(unlink_bridge, "run_registered_operation", submit)
    monkeypatch.setattr(commands, "emit_envelope", lambda _ctx, **kwargs: emitted.append(kwargs))
    return submitted, emitted


def test_the_command_is_registered_for_its_operation_with_positional_subjects() -> None:
    node = {node.path: node for node in COMMAND_GRAPH.nodes()}[("aeat", "app", "ledger", "unlink")]

    assert node.spec.result_schema.identity == LEDGER_UNLINK_OPERATION_DEFINITION_ID
    assert [parameter.name for parameter in node.spec.parameters] == ["transaction_id", "invoice_id", "actor"]


def test_an_unlink_reads_both_records_then_submits_their_expected_facts(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    del authority_operation
    transaction = _transaction()
    invoice = _invoice(linked_transaction_ids=(transaction.transaction_id, "d" * 64))
    result = LedgerUnlinkOperationResult(
        outcome="unlinked",
        profile_id=_PROFILE,
        transaction_id=transaction.transaction_id,
        invoice_id=invoice.invoice_id,
        actor="operator",
        transaction=transaction.model_copy(update={"invoice_id": None}),
        review_status=LedgerReviewStatus.REVIEWED,
        invoice_linked_transaction_ids=("d" * 64,),
        bucket_event_ids=("e" * 64,),
    )
    submitted, emitted = _bind(
        monkeypatch,
        transaction=transaction,
        invoice=invoice,
        completion=_completion(result, condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.UPDATED),
    )

    commands.ledger_unlink(_CTX, transaction.transaction_id[:12], invoice.invoice_id[:12], actor=None)

    (request,) = submitted
    assert isinstance(request, LedgerUnlinkRequest)
    assert (
        request.transaction_id,
        request.invoice_id,
        request.expected_modified_at,
        request.expected_invoice_linked_transaction_ids,
        request.actor,
    ) == (
        transaction.transaction_id,
        invoice.invoice_id,
        transaction.modified_at,
        (transaction.transaction_id, "d" * 64),
        "operator",
    )
    (envelope,) = emitted
    assert envelope["command"] == "ledger.unlink"
    served = envelope["result"]
    assert isinstance(served, UnlinkEnvelope)
    assert (served.transaction_id, served.invoice_id, served.actor) == (
        transaction.transaction_id,
        invoice.invoice_id,
        "operator",
    )
    assert served.invoice_linked_transaction_ids == ["d" * 64]
    assert served.bucket_event_ids == ["e" * 64]


@pytest.mark.parametrize(
    ("cause", "next_step"),
    [
        (InvoiceUnlinkCause.LINK_NOT_FOUND, InvoiceUnlinkNextStep.REOPEN_TRANSACTION),
        (InvoiceUnlinkCause.TRANSACTION_CHANGED, InvoiceUnlinkNextStep.REOPEN_TRANSACTION),
        (InvoiceUnlinkCause.INVOICE_CHANGED, InvoiceUnlinkNextStep.REOPEN_INVOICE),
        (InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE, InvoiceUnlinkNextStep.REOPEN_FINALIZED_CALCULATION),
    ],
)
def test_a_refusal_raises_the_operator_words_for_its_cause(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    cause: InvoiceUnlinkCause,
    next_step: InvoiceUnlinkNextStep,
) -> None:
    del authority_operation
    transaction = _transaction()
    invoice = _invoice()
    finalized_revisions = (_stale_revision(),) if cause is InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE else ()
    result = LedgerUnlinkOperationResult(
        outcome="refused",
        profile_id=_PROFILE,
        transaction_id=transaction.transaction_id,
        invoice_id=invoice.invoice_id,
        refusal=LedgerUnlinkRefusal(cause=cause, next_step=next_step, finalized_revisions=finalized_revisions),
    )
    _, emitted = _bind(
        monkeypatch,
        transaction=transaction,
        invoice=invoice,
        completion=_completion(
            result,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_code=LEDGER_UNLINK_REFUSAL_CODE,
        ),
    )

    with pytest.raises(typer.BadParameter) as raised:
        commands.ledger_unlink(_CTX, transaction.transaction_id[:12], invoice.invoice_id[:12], actor=None)

    assert emitted == []
    assert raised.value.message == tr(f"cli.ledger.unlink.errors.{cause.value}")


def test_a_refusal_under_another_receipt_is_not_presented_as_the_unlink_refusal(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    del authority_operation
    transaction = _transaction()
    invoice = _invoice()
    result = LedgerUnlinkOperationResult(
        outcome="refused",
        profile_id=_PROFILE,
        transaction_id=transaction.transaction_id,
        invoice_id=invoice.invoice_id,
        refusal=LedgerUnlinkRefusal(
            cause=InvoiceUnlinkCause.TRANSACTION_CHANGED, next_step=InvoiceUnlinkNextStep.REOPEN_TRANSACTION
        ),
    )
    _bind(
        monkeypatch,
        transaction=transaction,
        invoice=invoice,
        completion=_completion(result, condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.UNKNOWN),
    )

    with pytest.raises(CliRefusedBoundaryError):
        commands.ledger_unlink(_CTX, transaction.transaction_id[:12], invoice.invoice_id[:12], actor=None)


def test_a_settled_success_missing_its_effect_is_not_presented(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    del authority_operation
    transaction = _transaction()
    invoice = _invoice()
    result = LedgerUnlinkOperationResult(
        outcome="unlinked",
        profile_id=_PROFILE,
        transaction_id=transaction.transaction_id,
        invoice_id=invoice.invoice_id,
        actor="operator",
        transaction=transaction.model_copy(update={"invoice_id": None}),
        review_status=LedgerReviewStatus.REVIEWED,
        invoice_linked_transaction_ids=(),
        bucket_event_ids=("e" * 64,),
    )
    _bind(
        monkeypatch,
        transaction=transaction,
        invoice=invoice,
        completion=_completion(result, condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.NONE),
    )

    with pytest.raises(CliRefusedBoundaryError):
        commands.ledger_unlink(_CTX, transaction.transaction_id[:12], invoice.invoice_id[:12], actor=None)


def test_invoice_unlink_refused_error_renders_the_registered_catalogue_message() -> None:
    from ....core.errors.error_codes import get_registered_error_code, resolve_error_message

    error = InvoiceUnlinkRefusedError(InvoiceUnlinkCause.INVOICE_CHANGED)

    code = get_registered_error_code(error)

    assert code.code == LEDGER_UNLINK_REFUSAL_CODE
    assert code.message_key == "errors.refused.ledger_unlink"
    assert resolve_error_message(error, code, locale="en") == "The invoice link can't be removed: invoice_changed."
