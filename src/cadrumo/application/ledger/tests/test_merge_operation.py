"""Manual merge requests and execution remain profile-bound and revision-pinned."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.transactions.enums import (
    BusinessClassification,
    SplitRole,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.transactions.lineage_models import SplitLineage
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import merge_operation as operation
from ..action_ports import LedgerActionPorts
from ..models import MergeTransactionsResult
from ..persistence_ports import LedgerPersistenceConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_GROUP_ID = "e" * 64


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Build domain transactions under the same governed-fact lease as production."""
    with bundled_indexed_authority().operation():
        yield


def _request(*, profile_id: UUID = _PROFILE) -> operation.LedgerMergeRequest:
    return operation.LedgerMergeRequest(
        profile_id=profile_id,
        child_ids=("A" * 12, "b" * 13),
        reason="revert split",
        actor="operator",
    )


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")

    definition = operation.build_ledger_merge_definition(unused_ports)
    registration = operation.build_ledger_merge_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _transaction(provider_id: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 5, 2),
        value_date=None,
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Vendor SL",
        description=provider_id,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={"source": "test"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.PERSONAL,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def _canonical_result() -> tuple[MergeTransactionsResult, tuple[Transaction, ...], TransactionCatalogue]:
    first = _transaction("merge-child-one")
    second = _transaction("merge-child-two")
    child_ids = tuple(sorted((first.transaction_id, second.transaction_id)))
    parent = _transaction("merge-parent").model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.SPLIT,
            "split_lineage": SplitLineage(
                split_group_id=_GROUP_ID,
                role=SplitRole.PARENT,
                sibling_transaction_ids=child_ids,
            ),
        },
    )
    first = first.model_copy(
        update={
            "split_lineage": SplitLineage(
                split_group_id=_GROUP_ID,
                role=SplitRole.CHILD,
                sibling_transaction_ids=(parent.transaction_id, second.transaction_id),
            ),
        },
    )
    second = second.model_copy(
        update={
            "split_lineage": SplitLineage(
                split_group_id=_GROUP_ID,
                role=SplitRole.CHILD,
                sibling_transaction_ids=(parent.transaction_id, first.transaction_id),
            ),
        },
    )
    merged = _transaction("merge-fresh-row").model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "split_lineage": SplitLineage(
                split_group_id=_GROUP_ID,
                role=SplitRole.MERGED,
                sibling_transaction_ids=child_ids,
            ),
        },
    )
    archived_parent = parent.model_copy(update={"lifecycle_state": TransactionLifecycleState.ARCHIVED})
    archived_children = (first, second)
    catalogue = TransactionCatalogue.model_validate(
        {row.transaction_id: row for row in (parent, *archived_children)},
    )
    result = MergeTransactionsResult(
        bucket_id=str(_PROFILE),
        split_group_id=_GROUP_ID,
        parent_transaction_id=parent.transaction_id,
        merged_transaction_id=merged.transaction_id,
        source_child_ids=child_ids,
        merged_transaction=merged,
        parent_transaction=archived_parent,
        bucket_event_id="d" * 64,
    )
    return result, (first, second), catalogue


def test_request_wire_round_trip_normalizes_prefixes_and_bounds_cohort() -> None:
    request = _request()

    restored = operation.LedgerMergeRequest.model_validate_json(request.model_dump_json())

    assert restored == request
    assert restored.child_ids == ("a" * 12, "b" * 13)
    with pytest.raises(ValidationError):
        operation.LedgerMergeRequest(
            profile_id=_PROFILE,
            child_ids=("a" * 12, "a" * 12),
        )
    with pytest.raises(ValidationError):
        operation.LedgerMergeRequest(
            profile_id=_PROFILE,
            child_ids=tuple(f"{index:064x}" for index in range(129)),
        )


def test_registration_is_secure_and_requires_exact_profile_commit() -> None:
    registry, registration = _registry()

    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=operation.LEDGER_MERGE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=_request(),
        ),
        context=_access_context(registration),
    )

    definition = registry.lookup(operation.LEDGER_MERGE_OPERATION_DEFINITION_ID)
    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert AccessAction.COMMIT in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=OperationRequest[BaseModel](
                definition_id=operation.LEDGER_MERGE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
                payload=_request(profile_id=_OTHER_PROFILE),
            ),
            context=_access_context(registration),
        )


@pytest.mark.asyncio
async def test_executor_resolves_and_writes_against_the_same_fresh_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_commit = False
    result, children, catalogue = _canonical_result()
    revision_calls: list[TransactionCatalogue] = []
    guarded_writes: list[str] = []
    merge_calls: list[dict[str, object]] = []
    authority = cast(PinnedAuthorityOperation, object())

    class TransactionRepository:
        bucket_id = str(_PROFILE)

        def exists(self) -> bool:
            return True

        def load(self) -> TransactionCatalogue:
            return catalogue

        def load_for_date_range(self, _start: date, _end: date) -> TransactionCatalogue:
            return catalogue

        def load_by_ids(self, _transaction_ids: object) -> TransactionCatalogue:
            return catalogue

        def partition_by_date_range(self, _start: date, _end: date) -> object:
            raise AssertionError("merge should use the full revisioned catalogue")

        def save(self, _catalogue: TransactionCatalogue) -> None:
            raise AssertionError("merge must use its full-catalogue revision guard")

        def save_with_secure_object_writes(
            self,
            _catalogue: TransactionCatalogue,
            _extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("merge must use its full-catalogue revision guard")

        def replace_if_current_with_secure_object_writes(
            self,
            _current: Transaction,
            _replacement: Transaction,
            _extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("merge must use its full-catalogue revision guard")

        def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
            assert in_commit
            revision_calls.append(catalogue)
            return catalogue, "revision-one"

        def save_if_revision_with_secure_object_writes(
            self,
            _new_catalogue: TransactionCatalogue,
            *,
            expected_revision_id: str,
            extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            assert in_commit
            assert extra_writes == ()
            guarded_writes.append(expected_revision_id)

    repository = TransactionRepository()
    ports = LedgerActionPorts(
        operation=authority,
        transaction_repository=cast(Any, repository),
        bucket_event_repository=cast(Any, object()),
        invoice_repository=cast(Any, SimpleNamespace(bucket_id=str(_PROFILE))),
        attachment_store=cast(Any, object()),
        usage_ratio_profile=cast(Any, object()),
        usage_ratio_profile_loader=cast(Any, object()),
        work_unit_repository=cast(Any, SimpleNamespace(bucket_id=str(_PROFILE))),
        calculation_repository=cast(Any, SimpleNamespace(bucket_id=str(_PROFILE))),
        purchase_invoice_evidence_records=(),
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

    class Events:
        def __init__(self) -> None:
            self.effects: list[OperationEffect] = []

        async def phase(self, _phase: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            self.effects.append(effect)

    class Operands:
        value: BaseModel | None = None

        async def put(self, operand: BaseModel, *, written_at: object) -> str:
            self.value = operand
            return "f" * 64

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))

    def canonical_merge(**kwargs: object) -> MergeTransactionsResult:
        assert in_commit
        merge_ports = cast(LedgerActionPorts, kwargs["ports"])
        pinned = cast(
            operation.RevisionGuardedTransactionCatalogueCoCommitWriterProtocol, merge_ports.transaction_repository
        )
        assert pinned is not repository
        pinned_catalogue, pinned_revision = pinned.load_revisioned()
        assert pinned_catalogue is catalogue
        assert pinned_revision == "revision-one"
        with pytest.raises(LedgerPersistenceConflictError):
            pinned.save(catalogue)
        pinned.save_if_revision_with_secure_object_writes(
            catalogue,
            expected_revision_id=pinned_revision,
            extra_writes=(),
        )
        merge_calls.append(kwargs)
        action_child_ids = cast(tuple[str, ...], kwargs["child_transaction_ids"])
        assert set(action_child_ids) == set(result.source_child_ids)
        return result

    monkeypatch.setattr(operation, "merge_transactions", canonical_merge)
    events = Events()
    operands = Operands()
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=operation.LEDGER_MERGE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=authority,
        cancellation=Cancellation(),
        events=events,
        operands=operands,
    )
    executor = operation.LedgerMergeExecutor(lambda *, bucket_id, operation: ports)
    payload = operation.LedgerMergeRequest(
        profile_id=_PROFILE,
        child_ids=(children[0].transaction_id[:12], children[1].transaction_id[:12]),
        actor="operator",
    )
    request = OperationRequest[operation.LedgerMergeRequest](
        definition_id=operation.LEDGER_MERGE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )

    result_ref = await executor.execute(request, cast(OperationExecutorContext, context))

    assert result_ref == "f" * 64
    assert revision_calls == [catalogue]
    assert guarded_writes == ["revision-one"]
    assert len(merge_calls) == 1
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(operands.value, operation.LedgerMergeExecutionResult)
    assert operands.value.result.source_child_ids == result.source_child_ids
    assert operands.value.result.parent_transaction_id == result.parent_transaction_id
    assert operands.value.result.merged_transaction_id == result.merged_transaction_id


def test_result_projector_requires_matching_success_receipt() -> None:
    result, _children, _catalogue = _canonical_result()
    execution = operation.LedgerMergeExecutionResult(
        profile_id=_PROFILE,
        result=operation.LedgerMergeOperationResult(
            profile_id=_PROFILE,
            split_group_id=result.split_group_id,
            parent_transaction_id=result.parent_transaction_id,
            merged_transaction_id=result.merged_transaction_id,
            source_child_ids=result.source_child_ids,
            bucket_event_id=result.bucket_event_id,
        ),
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=operation.LEDGER_MERGE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 5, 4, tzinfo=UTC),
        result_ref="b" * 64,
    )

    assert operation._project_operation_result(execution, receipt) == execution.result

    with pytest.raises(ValueError):
        operation._project_operation_result(
            execution,
            receipt.model_copy(update={"effect": OperationEffect.NONE}),
        )
