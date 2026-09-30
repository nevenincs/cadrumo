"""Manual split requests and execution stay exact-profile and revision-pinned."""

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
from .. import split_operation as operation
from ..action_ports import LedgerActionPorts
from ..models import SplitChildCommand, SplitTransactionResult
from ..persistence_ports import LedgerPersistenceConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Build domain transactions under the same governed-fact lease as production."""
    with bundled_indexed_authority().operation():
        yield


def _request(*, profile_id: UUID = _PROFILE) -> operation.LedgerSplitRequest:
    return operation.LedgerSplitRequest(
        profile_id=profile_id,
        transaction_id="A" * 12,
        children=(
            operation.LedgerSplitChildRequest(amount="60", description="business portion"),
            operation.LedgerSplitChildRequest(amount="40", description="personal portion"),
        ),
        reason="separate use",
        actor="operator",
    )


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")

    definition = operation.build_ledger_split_definition(unused_ports)
    registration = operation.build_ledger_split_registration(definition)
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


def _parent_transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="split-operation-parent",
        booked_date=date(2026, 5, 2),
        value_date=None,
        amount=Decimal("100.00"),
        currency="EUR",
        counterparty="Vendor SL",
        description="materials",
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


def _child_transaction(parent: Transaction, child: SplitChildCommand, *, index: int) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=f"split:{parent.transaction_id}:{index:04d}",
        booked_date=parent.raw.booked_date,
        value_date=parent.raw.value_date,
        amount=child.amount,
        currency=parent.raw.currency,
        counterparty=parent.raw.counterparty,
        description=child.description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=index + 1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
            provider_name="ledger-split",
        ),
        raw_fields={"parent_transaction_id": parent.transaction_id, "split_index": str(index)},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": parent.direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": parent.source_jurisdiction,
            "group_label": parent.group_label,
        },
    )


def test_request_wire_round_trip_and_bounded_child_list() -> None:
    request = _request()

    restored = operation.LedgerSplitRequest.model_validate_json(request.model_dump_json())

    assert restored == request
    assert restored.transaction_id == "a" * 12
    assert [child.amount for child in restored.children] == ["60", "40"]
    with pytest.raises(ValidationError):
        operation.LedgerSplitChildRequest(amount="60.0", description="business portion")
    with pytest.raises(ValidationError):
        operation.LedgerSplitRequest(
            profile_id=_PROFILE,
            transaction_id="a" * 12,
            children=tuple(
                operation.LedgerSplitChildRequest(amount="1", description=f"child-{index}") for index in range(129)
            ),
        )


def test_registration_is_secure_and_requires_exact_profile_commit() -> None:
    registry, registration = _registry()
    request = operation.LedgerSplitRequest.model_validate(_request().model_dump(mode="python"))

    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=request,
        ),
        context=_access_context(registration),
    )

    definition = registry.lookup(operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID)
    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert AccessAction.COMMIT in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=OperationRequest[BaseModel](
                definition_id=operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
                payload=operation.LedgerSplitRequest.model_validate(
                    _request(profile_id=_OTHER_PROFILE).model_dump(mode="python"),
                ),
            ),
            context=_access_context(registration),
        )


def test_split_result_round_trip_and_bounded_child_ids() -> None:
    result = operation.LedgerSplitOperationResult(
        profile_id=_PROFILE,
        parent_transaction_id="a" * 64,
        split_group_id="b" * 64,
        child_transaction_ids=("c" * 64, "d" * 64),
        bucket_event_id="e" * 64,
        parent_business_classification=BusinessClassification.PERSONAL,
    )

    assert operation.LedgerSplitOperationResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        operation.LedgerSplitOperationResult(
            profile_id=_PROFILE,
            parent_transaction_id="a" * 64,
            split_group_id="b" * 64,
            child_transaction_ids=("c" * 64, "c" * 64),
            bucket_event_id="e" * 64,
            parent_business_classification=BusinessClassification.PERSONAL,
        )


@pytest.mark.asyncio
async def test_executor_resolves_and_writes_against_the_same_fresh_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_commit = False
    parent = _parent_transaction()
    catalogue = TransactionCatalogue.model_validate({parent.transaction_id: parent})
    revision_calls: list[object] = []
    guarded_writes: list[str] = []
    split_calls: list[dict[str, object]] = []
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
            raise AssertionError("split should use the full revisioned catalogue")

        def save(self, _catalogue: TransactionCatalogue) -> None:
            raise AssertionError("split must use its full-catalogue revision guard")

        def save_with_secure_object_writes(
            self,
            _catalogue: TransactionCatalogue,
            _extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("split must use its full-catalogue revision guard")

        def replace_if_current_with_secure_object_writes(
            self,
            _current: Transaction,
            _replacement: Transaction,
            _extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("split must use its full-catalogue revision guard")

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
            return "d" * 64

    action_results: list[SplitTransactionResult] = []
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))

    def canonical_split(**kwargs: object) -> SplitTransactionResult:
        assert in_commit
        split_ports = cast(LedgerActionPorts, kwargs["ports"])
        pinned = cast(
            operation.RevisionGuardedTransactionCatalogueCoCommitWriterProtocol,
            split_ports.transaction_repository,
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
        split_calls.append(kwargs)
        commands = cast(tuple[SplitChildCommand, ...], kwargs["children"])
        child_transactions = tuple(
            _child_transaction(parent, command, index=index) for index, command in enumerate(commands)
        )
        child_ids = tuple(child.transaction_id for child in child_transactions)
        group_id = "b" * 64
        parent_after = parent.model_copy(
            update={
                "lifecycle_state": TransactionLifecycleState.SPLIT,
                "split_lineage": SplitLineage(
                    split_group_id=group_id,
                    role=SplitRole.PARENT,
                    sibling_transaction_ids=tuple(sorted(child_ids)),
                ),
            },
        )
        final_children = tuple(
            child.model_copy(
                update={
                    "split_lineage": SplitLineage(
                        split_group_id=group_id,
                        role=SplitRole.CHILD,
                        sibling_transaction_ids=tuple(
                            sorted(
                                (
                                    parent.transaction_id,
                                    *(other for other in child_ids if other != child.transaction_id),
                                )
                            )
                        ),
                    ),
                },
            )
            for child in child_transactions
        )
        result = SplitTransactionResult(
            bucket_id=str(_PROFILE),
            parent_transaction_id=parent.transaction_id,
            split_group_id=group_id,
            child_transaction_ids=child_ids,
            parent_transaction=parent_after,
            child_transactions=final_children,
            bucket_event_id="f" * 64,
        )
        action_results.append(result)
        return result

    monkeypatch.setattr(operation, "split_transaction", canonical_split)

    events = Events()
    operands = Operands()
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=authority,
        cancellation=Cancellation(),
        events=events,
        operands=operands,
    )
    executor = operation.LedgerSplitExecutor(lambda *, bucket_id, operation: ports)
    payload = operation.LedgerSplitRequest(
        profile_id=_PROFILE,
        transaction_id=parent.transaction_id[:12],
        children=(
            operation.LedgerSplitChildRequest(amount="60", description="business portion"),
            operation.LedgerSplitChildRequest(amount="40", description="personal portion"),
        ),
    )
    request = OperationRequest[operation.LedgerSplitRequest](
        definition_id=operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )

    result_ref = await executor.execute(request, cast(OperationExecutorContext, context))

    assert result_ref == "d" * 64
    assert revision_calls == [catalogue]
    assert guarded_writes == ["revision-one"]
    assert len(split_calls) == 1
    assert split_calls[0]["transaction_id"] == parent.transaction_id
    assert split_calls[0]["actor"] == str(_PROFILE)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(operands.value, operation.LedgerSplitExecutionResult)
    assert len(action_results) == 1
    assert operands.value.result.parent_transaction_id == parent.transaction_id
    assert operands.value.result.child_transaction_ids == action_results[0].child_transaction_ids
    assert operands.value.result.split_group_id == action_results[0].split_group_id
    assert operands.value.result.bucket_event_id == action_results[0].bucket_event_id


def test_result_projector_requires_matching_success_receipt() -> None:
    result = operation.LedgerSplitExecutionResult(
        profile_id=_PROFILE,
        result=operation.LedgerSplitOperationResult(
            profile_id=_PROFILE,
            parent_transaction_id="a" * 64,
            split_group_id="b" * 64,
            child_transaction_ids=("c" * 64, "d" * 64),
            bucket_event_id="e" * 64,
            parent_business_classification=BusinessClassification.PERSONAL,
        ),
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="f" * 64,
            definition_id=operation.LEDGER_SPLIT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 5, 4, tzinfo=UTC),
        result_ref="a" * 64,
    )

    assert operation._project_operation_result(result, receipt) == result.result
    with pytest.raises(ValueError):
        operation._project_operation_result(
            result,
            receipt.model_copy(update={"effect": OperationEffect.NONE}),
        )
