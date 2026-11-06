"""Single-classification requests and receipts stay bounded and profile-bound."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationRegistry
from ...review.filter import LedgerReviewStatus
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import classify_operation as operation
from .. import classify_requests, classify_result_contracts
from ..action_ports import LedgerActionPorts, LedgerActionPortsFactory
from ..classify_result_projection import project_classify_operation_result
from ..transaction_projection import LedgerTransactionProjection
from .ledger_input_rule_support import current_transaction
from .recording_executor_context_support import RecordingEvents, RecordingOperands
from .transaction_projection_support import ledger_transaction_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_TRANSACTION_ID = "b" * 64


def _request(*, profile_id: UUID = _PROFILE) -> classify_requests.LedgerClassifyRequest:
    return classify_requests.LedgerClassifyRequest(
        profile_id=profile_id,
        transaction_id=_TRANSACTION_ID[:12],
        patch=classify_requests.LedgerClassifyPatch(business_classification="PERSONAL"),
        patch_fields=("business_classification",),
    )


def _transaction_projection() -> LedgerTransactionProjection:
    return ledger_transaction_projection(
        transaction_id=_TRANSACTION_ID,
        business_classification="PERSONAL",
        business_pct=None,
    )


def _receipt(
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> OperationTerminalReceipt:
    refused = condition is OperationTerminalCondition.REFUSED
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=classify_requests.LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=datetime(2026, 4, 15, tzinfo=UTC),
        result_ref=None if refused else "f" * 64,
        refusal_ref=classify_result_contracts.LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE if refused else None,
        refusal_detail_ref="e" * 64 if refused else None,
    )


def test_request_round_trip_keeps_explicit_null_and_exact_omission_mask() -> None:
    request = classify_requests.LedgerClassifyRequest(
        profile_id=_PROFILE,
        transaction_id=_TRANSACTION_ID[:12],
        patch=classify_requests.LedgerClassifyPatch(business_classification="PERSONAL", notes=None),
        patch_fields=("business_classification", "notes"),
    )

    assert classify_requests.LedgerClassifyRequest.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        classify_requests.LedgerClassifyRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            patch=classify_requests.LedgerClassifyPatch(business_classification="PERSONAL", notes="unselected"),
            patch_fields=("business_classification",),
        )


def test_mixed_share_and_m210_orphan_identity_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        classify_requests.LedgerClassifyRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            patch=classify_requests.LedgerClassifyPatch(business_classification="MIXED"),
            patch_fields=("business_classification",),
        )

    with pytest.raises(ValidationError):
        classify_requests.LedgerClassifyRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            patch=classify_requests.LedgerClassifyPatch(business_classification="BUSINESS"),
            patch_fields=("business_classification", "m210_income_classification"),
            m210=classify_requests.LedgerClassifyM210Options(payer_id="payer-1"),
        )


def test_registration_requires_commit_and_refuses_another_profile() -> None:
    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected execution for {bucket_id}: {operation!r}")

    definition = operation.build_ledger_classify_definition(unused_ports)
    registration = operation.build_ledger_classify_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=classify_requests.LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
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

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=OperationRequest[BaseModel](
                definition_id=classify_requests.LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
                payload=_request(profile_id=_OTHER_PROFILE),
            ),
            context=context,
        )


def test_terminal_projector_checks_effect_and_preserves_bounded_m210_refusal_kind() -> None:
    projection = classify_result_contracts.LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=_PROFILE,
        transaction=_transaction_projection(),
        investment_asset_id=None,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("d" * 64,),
    )
    execution = classify_result_contracts.LedgerClassifyExecutionResult(
        outcome="classified",
        profile_id=_PROFILE,
        result=projection,
    )
    receipt = _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)

    assert project_classify_operation_result(execution, receipt) == projection
    with pytest.raises(ValueError):
        project_classify_operation_result(execution, receipt.model_copy(update={"effect": OperationEffect.NONE}))

    refusal_execution = classify_result_contracts.LedgerClassifyExecutionResult(
        outcome="validation_error",
        profile_id=_PROFILE,
        validation_kind="m210_required_options",
        validation_messages=("M210 declaration is incomplete",),
    )
    refused = cast(
        classify_result_contracts.LedgerClassifyOperationResult,
        project_classify_operation_result(
            refusal_execution,
            _receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        ),
    )
    assert refused.outcome == "validation_error"
    assert refused.validation_kind == "m210_required_options"
    assert refused.bucket_event_ids == ()


@pytest.mark.asyncio
@pytest.mark.usefixtures("operation")
async def test_executor_loads_in_commit_and_passes_the_same_row_as_expected_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_commit = False
    loaded: list[object] = []
    mutations: list[dict[str, object]] = []
    authority = cast(PinnedAuthorityOperation, object())
    current = current_transaction("classify-executor-row")
    transaction_id = current.transaction_id
    catalogue = SimpleNamespace(transactions={transaction_id: current})

    class TransactionRepository:
        bucket_id = str(_PROFILE)

        def load(self) -> object:
            assert in_commit
            loaded.append(catalogue)
            return catalogue

    ports = SimpleNamespace(
        operation=authority,
        transaction_repository=TransactionRepository(),
        invoice_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        work_unit_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        calculation_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
    )

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self):
            nonlocal in_commit
            in_commit = True
            try:
                yield
            finally:
                in_commit = False

    events = RecordingEvents()
    operands = RecordingOperands()
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=classify_requests.LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=authority,
        cancellation=Cancellation(),
        events=events,
        operands=operands,
    )
    transaction_projection = _transaction_projection()
    public_result = classify_result_contracts.LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=_PROFILE,
        transaction=transaction_projection,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
    )
    projection_calls: list[object] = []

    def project(_profile_id: UUID, result: object) -> classify_result_contracts.LedgerClassifyOperationResult:
        projection_calls.append(result)
        return public_result

    def update(**kwargs: object) -> SimpleNamespace:
        assert in_commit
        mutations.append(kwargs)
        return SimpleNamespace(bucket_event_ids=("e" * 64,))

    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "classification_result_from_action", project)
    monkeypatch.setattr(operation, "update_manual_transaction_fields", update)
    factory = cast(LedgerActionPortsFactory, lambda **_kwargs: ports)
    executor = operation.LedgerClassifyExecutor(factory)
    request = OperationRequest[classify_requests.LedgerClassifyRequest](
        definition_id=classify_requests.LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=classify_requests.LedgerClassifyRequest(
            profile_id=_PROFILE,
            transaction_id=transaction_id[:12],
            patch=classify_requests.LedgerClassifyPatch(business_classification="BUSINESS", notes="reason"),
            patch_fields=("business_classification", "notes"),
        ),
    )

    result_ref = await executor.execute(request, cast(OperationExecutorContext, context))

    assert result_ref == "d" * 64
    assert loaded == [catalogue]
    assert len(projection_calls) == 2
    assert mutations[0]["transaction_id"] == transaction_id
    assert mutations[0]["catalogue"] is catalogue
    assert mutations[0]["expected_current"] is current
    assert mutations[0]["ports"] is ports
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(operands.value, classify_result_contracts.LedgerClassifyExecutionResult)
