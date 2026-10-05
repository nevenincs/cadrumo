"""CSV classification preserves row semantics behind exact-profile writer authority."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.errors.hierarchy import InternalInvariantError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import Transaction
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...operations.registry_schema_validation import strict_model_json_schema
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import bulk_classify_operation as operation
from ..action_ports import LedgerActionPorts
from ..models import BulkClassifyResult
from ..persistence_ports import LedgerPersistenceConflictError
from ..protocols import InvoiceCatalogueCoCommitWriterProtocol
from .bulk_classify_operation_support import PROFILE_ID, BulkClassifySubject
from .test_classification_rule_plan import _InMemoryTransactionRepository, _transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _request(csv_text: str) -> OperationRequest[operation.LedgerBulkClassifyRequest]:
    return OperationRequest[operation.LedgerBulkClassifyRequest](
        definition_id=operation.LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=operation.LedgerBulkClassifyRequest(profile_id=PROFILE_ID, csv_text=csv_text),
    )


def _receipt(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=operation.LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=datetime(2026, 5, 1, tzinfo=UTC),
        condition=condition,
        effect=effect,
        result_ref="d" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=operation.LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE
        if condition is OperationTerminalCondition.REFUSED
        else None,
        refusal_detail_ref="d" * 64 if condition is OperationTerminalCondition.REFUSED else None,
    )


@pytest.fixture
def transactions() -> tuple[Transaction, Transaction]:
    return (
        _transaction(provider_id="bulk-office", description="Synthetic office purchase"),
        _transaction(provider_id="bulk-personal", description="Synthetic personal purchase"),
    )


@pytest.fixture
def subject(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    transactions: tuple[Transaction, Transaction],
) -> BulkClassifySubject:
    monkeypatch.setattr(
        "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(PROFILE_ID)
    )
    return BulkClassifySubject(operation=authority_operation, transactions=transactions)


def test_request_is_strict_hides_csv_and_round_trips_through_public_schema() -> None:
    source = "transaction_id,classification\nsynthetic,PERSONAL"
    request = _request(source).payload
    assert source not in repr(request)
    assert operation.LedgerBulkClassifyRequest.model_validate_json(request.model_dump_json()) == request
    strict_model_json_schema(operation.LedgerBulkClassifyRequest)
    with pytest.raises(ValidationError):
        operation.LedgerBulkClassifyRequest.model_validate({**request.model_dump(), "file": "private.csv"})


def test_registration_requires_all_periods_commit_and_refuses_mcp() -> None:
    def unused(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError("access resolution must not compose profile storage")

    definition = operation.build_ledger_bulk_classify_definition(unused)
    registration = operation.build_ledger_bulk_classify_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = _request("transaction_id,classification")
    public_request = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )
    access = resolve_operation_access(registry=registry, request=public_request, context=context)
    assert AccessAction.COMMIT in access.policy.actions
    assert access.policy.requires_all_periods and access.request.period_independent
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=public_request,
            context=replace(context, frontend=OperationFrontendProjection.MCP),
        )
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry, request=public_request, context=replace(context, profile_id=uuid4())
        )


def test_complete_result_projector_correlates_effect_profile_and_terminal_condition() -> None:
    result = BulkClassifyResult(total=1, applied=1, skipped=0, bucket_event_ids=("e" * 64,))
    projection = operation.LedgerBulkClassifyProjection(profile_id=PROFILE_ID, outcome="classified", result=result)
    execution = operation.LedgerBulkClassifyExecutionResult(projection=projection)
    receipt = _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)
    assert operation._project_result(execution, receipt) == projection
    for defect in (
        {"effect": OperationEffect.NONE},
        {"condition": OperationTerminalCondition.REFUSED},
        {"identity": receipt.identity.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})},
    ):
        with pytest.raises(ValueError):
            operation._project_result(execution, receipt.model_copy(update=defect))


def test_real_csv_batch_loads_once_co_commits_once_and_preserves_row_failure(
    subject: BulkClassifySubject, transactions: tuple[Transaction, Transaction]
) -> None:
    first, second = transactions
    source = f"transaction_id,classification\n{first.transaction_id[:12]},BUSINESS\ninvalid,PERSONAL\n{second.transaction_id},PERSONAL\n"
    reference = asyncio.run(
        operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context)
    )
    assert reference == "d" * 64
    assert subject.repository.loads == 1 and subject.repository.committed_writes == 1
    assert subject.fence.entries == 1 and not subject.fence.active
    stored = subject.repository.current
    assert stored.transactions[first.transaction_id].business_classification is BusinessClassification.BUSINESS
    assert stored.transactions[second.transaction_id].business_classification is BusinessClassification.PERSONAL
    execution = cast(operation.LedgerBulkClassifyExecutionResult, subject.operands.values[-1])
    result = execution.projection.result
    assert result is not None
    assert (result.total, result.applied, result.skipped) == (3, 2, 0)
    assert len(result.failures) == 1 and result.failures[0].transaction_id == "invalid"
    assert result.bucket_event_ids
    assert subject.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED, OperationEffect.UPDATED]
    assert subject.events.phases == [operation.LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID]
    assert source not in execution.model_dump_json()


@pytest.mark.parametrize("source", ["", "transaction_id,classification\nunknown,BUSINESS\n"])
def test_empty_or_all_failed_csv_is_a_complete_success_with_no_write(subject: BulkClassifySubject, source: str) -> None:
    asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context))
    execution = cast(operation.LedgerBulkClassifyExecutionResult, subject.operands.values[-1])
    assert execution.projection.outcome == "classified"
    result = execution.projection.result
    assert result is not None and result.applied == 0 and not result.bucket_event_ids
    assert subject.repository.committed_writes == 0 and subject.fence.entries == 0
    assert subject.events.effects == [OperationEffect.NONE]
    if source:
        assert result.total == 1 and len(result.failures) == 1


def test_unknown_csv_header_is_an_explicit_prewrite_validation_refusal(subject: BulkClassifySubject) -> None:
    source = "transaction_id,classification,unknown_column\n"
    refused = asyncio.run(
        operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context)
    )
    assert isinstance(refused, OperationRefusalEvidence)
    assert refused.refusal_code == operation.LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE
    assert subject.repository.loads == 0 and subject.repository.write_attempts == 0
    assert subject.events.effects == [OperationEffect.NONE]
    execution = cast(operation.LedgerBulkClassifyExecutionResult, subject.operands.values[-1])
    assert execution.projection.outcome == "validation_error" and execution.projection.result is None
    assert (
        operation._project_result(execution, _receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE))
        == execution.projection
    )


def test_stale_catalogue_is_refused_without_overwriting_any_rows(
    subject: BulkClassifySubject, transactions: tuple[Transaction, Transaction]
) -> None:
    subject.repository.stale = True
    source = f"transaction_id,classification\n{transactions[0].transaction_id},BUSINESS\n"
    with pytest.raises(LedgerPersistenceConflictError):
        asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context))
    assert subject.repository.loads == 1 and subject.repository.committed_writes == 0
    assert subject.repository.current.transactions[transactions[0].transaction_id] == transactions[0]
    assert subject.events.effects[-1] is OperationEffect.NONE
    assert OperationEffect.UPDATED not in subject.events.effects
    assert not subject.operands.values


def test_writer_failure_after_mutation_remains_unknown_and_never_becomes_validation_refusal(
    subject: BulkClassifySubject, transactions: tuple[Transaction, Transaction]
) -> None:
    subject.repository.fail_after_write = True
    source = f"transaction_id,classification\n{transactions[0].transaction_id},BUSINESS\n"
    with pytest.raises(ValueError, match="after committing"):
        asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context))
    assert subject.repository.committed_writes == 1
    assert subject.events.effects[-1] is OperationEffect.UNKNOWN
    assert not subject.operands.values


def test_revocation_before_writer_entry_prevents_catalogue_mutation(
    subject: BulkClassifySubject, transactions: tuple[Transaction, Transaction]
) -> None:
    subject.fence.deny = True
    source = f"transaction_id,classification\n{transactions[0].transaction_id},BUSINESS\n"
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(source), subject.context))
    assert subject.repository.write_attempts == 0 and subject.repository.committed_writes == 0
    assert not subject.operands.values


@pytest.mark.parametrize("defect", ["active_profile", "subject", "authority", "repository"])
def test_exact_profile_and_authority_mismatch_refuses_before_csv_storage(
    subject: BulkClassifySubject, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    request = _request("transaction_id,classification")
    if defect == "active_profile":
        monkeypatch.setattr(
            "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(uuid4())
        )
    elif defect == "subject":
        request = request.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
    elif defect == "authority":
        subject.ports = replace(subject.ports, operation=cast(PinnedAuthorityOperation, object()))
    else:
        subject.ports = replace(
            subject.ports,
            invoice_repository=cast(InvoiceCatalogueCoCommitWriterProtocol, SimpleNamespace(bucket_id=str(uuid4()))),
        )
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(request, subject.context))
    assert subject.repository.loads == 0 and subject.repository.write_attempts == 0


def test_nonrevision_catalogue_port_refuses_before_mutation(subject: BulkClassifySubject) -> None:
    subject.ports = replace(
        subject.ports,
        transaction_repository=_InMemoryTransactionRepository(subject.repository.current),
    )
    with pytest.raises(InternalInvariantError, match="revision-guarded"):
        asyncio.run(operation.LedgerBulkClassifyExecutor(subject.compose).execute(_request(""), subject.context))
    assert subject.repository.loads == 0 and subject.repository.write_attempts == 0
