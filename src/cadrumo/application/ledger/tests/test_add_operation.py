"""Exact-profile manual-add wire, receipt, and secure CAS contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.ledger_add_command import resolve_ledger_add_prorrata_advisory_facts
from ....application.ledger.ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    LedgerAddExecutionResult,
    LedgerAddOperationResult,
    LedgerAddRequest,
)
from ....application.ledger.ledger_add_results import project_ledger_add_result
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.registry import OperationFrontendProjection, OperationRegistry
from ....application.prorrata_register.ports import (
    ProrrataRegisterServiceRepositoryProtocol,
)
from ....application.review.filter import LedgerReviewStatus
from ....application.user_profile.access_contracts import AccessAction, Availability
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.prorrata_vocabulary import require_input_classification
from ....domain.prorrata_register.register import ProrrataRegister
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from .. import add_operation
from ..own_account_ports import OwnAccountRepositoryProtocol

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "b" * 64
_OPERATION_ID = "a" * 64
_EVENT_ID = "e" * 64
_NOW = datetime(2026, 4, 15, 9, 30, tzinfo=UTC)


def _request() -> LedgerAddRequest:
    return LedgerAddRequest(
        profile_id=_PROFILE,
        booked_date="2026-04-15",
        amount="10.00",
        direction="OUTGOING",
        description="Office materials",
        iva_category="domestic_general",
        counterparty_identification_state="de",
    )


def _transaction() -> LedgerTransactionProjection:
    return LedgerTransactionProjection.model_validate(
        {
            "transaction_id": _TRANSACTION_ID,
            "date": "2026-04-15",
            "booked_date": "2026-04-15",
            "value_date": None,
            "amount": "10",
            "currency": "EUR",
            "direction": "OUTGOING",
            "counterparty": "",
            "description": "Office materials",
            "business_classification": "NOT_YET_PROCESSED",
            "business_pct": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "iva_category": "domestic_general",
            "counterparty_country": None,
            "counterparty_identification_state": "de",
            "irpf_category": None,
            "m210_income_classification": None,
            "usage_ratio_id": None,
            "prorrata_reference": None,
            "purchase_invoice_evidence_id": None,
            "invoice_id": None,
            "attachment_ids": (),
            "notes": "",
            "lifecycle_state": "ACTIVE",
            "classified_by": "auto",
            "classified_at": None,
            "classification_reason": "",
            "classification_confidence": None,
            "source_jurisdiction": None,
            "value_in_eur": None,
            "fx_rate": None,
            "created_at": "2026-04-15T09:30:00+00:00",
            "modified_at": "2026-04-15T09:30:00+00:00",
        },
    )


def _receipt(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationTerminalReceipt:
    refused = condition is OperationTerminalCondition.REFUSED
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id=_OPERATION_ID,
            definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=_NOW,
        result_ref=None if refused else "f" * 64,
        refusal_ref=LEDGER_ADD_VALIDATION_REFUSAL_CODE if refused else None,
        refusal_detail_ref="c" * 64 if refused else None,
    )


def test_wire_schema_keeps_governed_tokens_as_bounded_strings_and_roundtrips() -> None:
    request = _request()

    assert LedgerAddRequest.model_validate_json(request.model_dump_json()) == request
    schema = LedgerAddRequest.model_json_schema()
    assert schema["properties"]["iva_category"]["anyOf"][0]["type"] == "string"
    assert schema["properties"]["counterparty_identification_state"]["anyOf"][0]["type"] == "string"
    with pytest.raises(ValidationError):
        LedgerAddRequest(
            profile_id=_PROFILE,
            booked_date="2026-04-15",
            amount="1.000",
            direction="OUTGOING",
            description="ambiguous amount",
        )


def test_registration_requires_commit_and_refuses_another_profile() -> None:
    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected execution for {bucket_id}: {operation!r}")

    def unused_register(*, bucket_id: str) -> ProrrataRegisterServiceRepositoryProtocol:
        raise AssertionError(f"unexpected prorrata lookup for {bucket_id}")

    def unused_own_accounts(*, bucket_id: str) -> OwnAccountRepositoryProtocol:
        raise AssertionError(f"unexpected own-account lookup for {bucket_id}")

    definition = add_operation.build_ledger_add_definition(unused_ports, unused_register, unused_own_accounts)
    registration = add_operation.build_ledger_add_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=_request(),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert AccessAction.COMMIT in resolved.policy.actions
    mismatched_context = OperationAccessContext(
        profile_id=uuid4(),
        destination_id=context.destination_id,
        action=context.action,
        frontend=context.frontend,
        contract=context.contract,
        published_authority=context.published_authority,
    )
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=request,
            context=mismatched_context,
        )


def test_terminal_projector_rejects_effect_mismatch_and_preserves_refusal() -> None:
    projected = LedgerAddOperationResult.created(
        _PROFILE,
        transaction=_transaction(),
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=(_EVENT_ID,),
    )
    execution = LedgerAddExecutionResult(
        outcome="created",
        profile_id=_PROFILE,
        result=projected,
    )

    assert (
        project_ledger_add_result(
            execution,
            _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
        )
        == projected
    )
    with pytest.raises(ValueError, match="incompatible terminal receipt"):
        project_ledger_add_result(
            execution,
            _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        )

    refusal = LedgerAddExecutionResult(
        outcome="validation_error",
        profile_id=_PROFILE,
        validation_code="invalid_command",
        validation_messages=("amount: must be a non-negative magnitude",),
    )
    projected_refusal = project_ledger_add_result(
        refusal,
        _receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE),
    )
    assert isinstance(projected_refusal, LedgerAddOperationResult)
    assert projected_refusal.outcome == "validation_error"
    assert projected_refusal.validation_messages == refusal.validation_messages


def test_prorrata_advisory_facts_are_resolved_from_the_requested_profile_before_commit(
    operation: PinnedAuthorityOperation,
) -> None:
    class EmptyProrrataRepository:
        bucket_id = str(_PROFILE)

        def load(self) -> ProrrataRegister:
            return ProrrataRegister()

    repository = EmptyProrrataRepository()
    requested_buckets: list[str] = []

    def repository_factory(*, bucket_id: str) -> ProrrataRegisterServiceRepositoryProtocol:
        requested_buckets.append(bucket_id)
        return cast(ProrrataRegisterServiceRepositoryProtocol, repository)

    payload = LedgerAddRequest(
        profile_id=_PROFILE,
        booked_date="2026-04-15",
        amount="10.00",
        direction="OUTGOING",
        description="Office materials",
        input_classification="exclusively_deductible",
        prorrata_sector="not-declared",
    )
    input_classification = require_input_classification(
        "exclusively_deductible",
        effective_date=date(2026, 4, 15),
        authority=operation,
    )
    command = ManualLedgerTransactionCommand(
        bucket_id=str(_PROFILE),
        booked_date=date(2026, 4, 15),
        amount=Decimal("10.00"),
        direction=TransactionDirection.OUTGOING,
        description="Office materials",
        business_classification=BusinessClassification.PERSONAL,
        input_classification=input_classification,
        prorrata_sector_id="not-declared",
        actor="operator",
        source_command="aeat app ledger add",
    )

    facts = resolve_ledger_add_prorrata_advisory_facts(payload, command, repository_factory, operation)

    assert requested_buckets == [str(_PROFILE)]
    assert facts == (True, True)
