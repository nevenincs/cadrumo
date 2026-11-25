"""``aeat app ledger evidence verify`` and ``release`` submit their registered writes and correlate the result.

The check keeps a finding on one evidence record; the release unlinks a
movement's purchase evidence, or keeps its document on the movement, against the
evidence and the modification time the person saw. A refusal surfaces as the
release's own typed error with its cause and next step.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast, get_args

import pytest
import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from ....application.ledger.evidence_read_operation import LedgerEvidenceRecordProjection
from ....application.ledger.evidence_readability import readable_finding
from ....application.ledger.evidence_verify_operation import (
    LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
    LedgerEvidenceVerifyChecked,
    LedgerEvidenceVerifyProjection,
    LedgerEvidenceVerifyRefusal,
    LedgerEvidenceVerifyRequest,
)
from ....application.ledger.manual_read import ledger_transaction_payload
from ....application.ledger.purchase_evidence_release import (
    PurchaseEvidenceDisposition,
    PurchaseEvidenceReleaseCause,
    PurchaseEvidenceReleaseNextStep,
    PurchaseEvidenceReleaseRefusedError,
)
from ....application.ledger.purchase_evidence_release_operation import (
    LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
    LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE,
    LedgerPurchaseEvidenceReleaseRefusal,
    LedgerPurchaseEvidenceReleaseRequest,
    LedgerPurchaseEvidenceReleaseResult,
)
from ....application.ledger.tests.evidence_mutation_support import (
    EVIDENCE_MUTATION_PROFILE,
    evidence_mutation_record,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.operations.models import OperationId
from ....application.review.filter import LedgerReviewStatus
from ....core.document_shape import DocumentShape
from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.tests.rental_link_rows import rental_row
from .. import ledger_evidence_commands as commands
from .. import operation_ledger_evidence_mutation as verify_bridge
from .. import operation_ledger_purchase_evidence_release as release_bridge
from ..app_ledger_evidence_command_specs import RELEASE_DISPOSITIONS
from ..command_specs import COMMAND_GRAPH
from ..ledger_business_payloads import EvidenceRemoveResult, EvidenceVerifyResult
from ..ledger_results import LedgerPurchaseEvidenceReleaseResult as ReleaseEnvelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = EVIDENCE_MUTATION_PROFILE
_EVIDENCE_ID = "evidence-target"
_EXPECTED_MODIFIED_AT = datetime(filing_year_envelope().horizon, 5, 8, 10, 15, tzinfo=UTC).isoformat()
_CHECKED_AT = datetime(filing_year_envelope().horizon, 5, 9, 8, 0, tzinfo=UTC)
_CTX = cast(typer.Context, cast(object, None))


def _checked_record() -> LedgerEvidenceRecordProjection:
    record = evidence_mutation_record()
    found = readable_finding(
        shape=DocumentShape.PDF_TEXT_LAYER, checked_sha256=record.source_sha256, checked_at=_CHECKED_AT
    )
    return LedgerEvidenceRecordProjection.from_record(record.model_copy(update={"readability": found}))


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
    bridge: object,
    definition_id: str,
    completion: RegisteredOperationCompletion[BaseModel],
) -> tuple[list[BaseModel], list[dict[str, object]]]:
    """Answer the bridge's one submission with ``completion`` and capture what the command emits."""
    submitted: list[BaseModel] = []
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: SimpleNamespace(profile_id=_PROFILE))

    def submit(_client: object, request: BaseModel, **kwargs: object) -> RegisteredOperationCompletion[BaseModel]:
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["allow_refusal_detail"] is True
        submitted.append(request)
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    monkeypatch.setattr(commands, "emit_envelope", lambda _ctx, **kwargs: emitted.append(kwargs))
    return submitted, emitted


def _released_transaction() -> LedgerTransactionProjection:
    return LedgerTransactionProjection.from_payload(
        ledger_transaction_payload(rental_row(provider_id="released")), language=OutputLanguage.EN
    )


def test_both_commands_are_registered_for_their_operations_with_positional_subjects() -> None:
    nodes = {node.path: node for node in COMMAND_GRAPH.nodes()}

    verify = nodes[("aeat", "app", "ledger", "evidence", "verify")]
    release = nodes[("aeat", "app", "ledger", "evidence", "release")]

    assert verify.spec.result_schema.identity == LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID
    assert [parameter.name for parameter in verify.spec.parameters] == ["evidence_id"]
    assert release.spec.result_schema.identity == LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID
    assert [parameter.name for parameter in release.spec.parameters] == [
        "transaction_id",
        "disposition",
        "expected_evidence_id",
        "expected_modified_at",
    ]
    (disposition,) = (parameter for parameter in release.spec.parameters if parameter.name == "disposition")
    assert disposition.value.choices == RELEASE_DISPOSITIONS


def test_the_disposition_choices_are_the_release_request_tokens() -> None:
    assert get_args(PurchaseEvidenceDisposition) == RELEASE_DISPOSITIONS


def test_a_checked_record_is_emitted_with_the_finding_it_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _checked_record()
    projection = LedgerEvidenceVerifyProjection(
        profile_id=_PROFILE,
        outcome=LedgerEvidenceVerifyChecked(record=record, bucket_event_ids=("e" * 64,)),
    )
    submitted, emitted = _bind(
        monkeypatch,
        verify_bridge,
        LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        _completion(projection, condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.UPDATED),
    )

    commands.evidence_verify(_CTX, _EVIDENCE_ID)

    assert submitted == [LedgerEvidenceVerifyRequest(profile_id=_PROFILE, evidence_id=_EVIDENCE_ID)]
    (envelope,) = emitted
    assert envelope["command"] == "ledger.evidence.verify"
    result = envelope["result"]
    assert isinstance(result, EvidenceVerifyResult)
    assert (result.readability, result.document_shape, result.unreadable_cause) == ("readable", "pdf_text_layer", None)
    assert result.bucket_event_ids == ["e" * 64]
    assert "readability\treadable" in cast("list[str]", envelope["lines"])


def test_a_check_of_a_missing_record_is_refused_as_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceVerifyProjection(profile_id=_PROFILE, outcome=LedgerEvidenceVerifyRefusal())
    _, emitted = _bind(
        monkeypatch,
        verify_bridge,
        LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        _completion(
            projection,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_code=LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE,
        ),
    )

    with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
        commands.evidence_verify(_CTX, _EVIDENCE_ID)

    assert emitted == []


def test_a_check_settled_without_its_effect_is_not_presented(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceVerifyProjection(
        profile_id=_PROFILE,
        outcome=LedgerEvidenceVerifyChecked(record=_checked_record(), bucket_event_ids=("e" * 64,)),
    )
    _, emitted = _bind(
        monkeypatch,
        verify_bridge,
        LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        _completion(projection, condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.NONE),
    )

    with pytest.raises(CliRefusedBoundaryError):
        commands.evidence_verify(_CTX, _EVIDENCE_ID)

    assert emitted == []


@pytest.mark.parametrize("disposition", RELEASE_DISPOSITIONS)
def test_a_release_emits_the_released_movement_and_what_became_of_the_evidence(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation, disposition: str
) -> None:
    del authority_operation
    transaction = _released_transaction()
    result = LedgerPurchaseEvidenceReleaseResult(
        outcome="updated",
        profile_id=_PROFILE,
        disposition=cast(PurchaseEvidenceDisposition, disposition),
        released_evidence_id=_EVIDENCE_ID,
        transaction=transaction,
        review_status=LedgerReviewStatus.REVIEWED,
        bucket_event_ids=("e" * 64,),
    )
    submitted, emitted = _bind(
        monkeypatch,
        release_bridge,
        LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        _completion(result, condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.UPDATED),
    )

    commands.evidence_release(
        _CTX,
        transaction.transaction_id[:12],
        disposition,
        expected_evidence_id=_EVIDENCE_ID,
        expected_modified_at=_EXPECTED_MODIFIED_AT,
    )

    (request,) = submitted
    assert isinstance(request, LedgerPurchaseEvidenceReleaseRequest)
    assert (
        request.transaction_id,
        request.expected_purchase_invoice_evidence_id,
        request.expected_modified_at,
        request.disposition,
    ) == (transaction.transaction_id[:12], _EVIDENCE_ID, _EXPECTED_MODIFIED_AT, disposition)
    (envelope,) = emitted
    assert envelope["command"] == "ledger.purchase_evidence.release"
    served = envelope["result"]
    assert isinstance(served, ReleaseEnvelope)
    assert (served.transaction_id, served.disposition, served.released_evidence_id) == (
        transaction.transaction_id,
        disposition,
        _EVIDENCE_ID,
    )
    assert served.transaction.purchase_invoice_evidence_id is None
    assert served.bucket_event_ids == ["e" * 64]


def test_a_refused_release_raises_its_cause_and_next_step_in_the_registered_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = LedgerPurchaseEvidenceReleaseResult(
        outcome="refused",
        profile_id=_PROFILE,
        disposition="detach",
        released_evidence_id=_EVIDENCE_ID,
        refusal=LedgerPurchaseEvidenceReleaseRefusal(
            cause=PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED,
            next_step=PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION,
        ),
    )
    _, emitted = _bind(
        monkeypatch,
        release_bridge,
        LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        _completion(
            result,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_code=LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE,
        ),
    )

    with pytest.raises(PurchaseEvidenceReleaseRefusedError) as raised:
        commands.evidence_release(
            _CTX,
            "abc123",
            "detach",
            expected_evidence_id=_EVIDENCE_ID,
            expected_modified_at=_EXPECTED_MODIFIED_AT,
        )

    assert emitted == []
    assert raised.value.cause is PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED
    assert raised.value.context == {"cause": "transaction_changed", "next_step": "reopen_transaction"}
    code = get_registered_error_code(raised.value)
    assert code.code == LEDGER_PURCHASE_EVIDENCE_RELEASE_REFUSAL_CODE
    assert code.message_key == "errors.refused.ledger_purchase_evidence_release"
    assert (
        resolve_error_message(raised.value, code, locale="en")
        == "The document can't be removed from this movement: transaction_changed."
    )


def test_a_refusal_under_another_receipt_is_not_presented_as_the_release_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = LedgerPurchaseEvidenceReleaseResult(
        outcome="refused",
        profile_id=_PROFILE,
        disposition="detach",
        released_evidence_id=_EVIDENCE_ID,
        refusal=LedgerPurchaseEvidenceReleaseRefusal(
            cause=PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED,
            next_step=PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION,
        ),
    )
    _bind(
        monkeypatch,
        release_bridge,
        LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        _completion(result, condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.UNKNOWN),
    )

    with pytest.raises(CliRefusedBoundaryError):
        commands.evidence_release(
            _CTX,
            "abc123",
            "detach",
            expected_evidence_id=_EVIDENCE_ID,
            expected_modified_at=_EXPECTED_MODIFIED_AT,
        )


def test_the_evidence_envelopes_take_the_record_with_its_readability() -> None:
    payload = {**_checked_record().model_dump(mode="json"), "bucket_event_ids": ["e" * 64]}

    removed = EvidenceRemoveResult.model_validate(payload)

    assert (removed.readability, removed.document_shape) == ("readable", "pdf_text_layer")
    assert removed.readability_checked_at == payload["readability_checked_at"]
