"""Ledger allocation registration keeps exact-profile authority and fresh writes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ...aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...review.filter import LedgerReviewStatus
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import allocate_operation as operation
from ..action_ports import LedgerActionPorts
from ..transaction_projection import LedgerTransactionProjection
from .unused_repository_ports import ProfileOnlyCatalogueRepository, UnusedAttachmentStore, UnusedBucketEventRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_CURRENT_TRANSACTION_ID = "b" * 64


def _unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = operation.build_ledger_allocate_definition(_unused_ports)
    registration = operation.build_ledger_allocate_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=operation.LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=operation.LedgerAllocateRequest(
            profile_id=profile_id,
            transaction_id="a" * 12,
            business_pct="0.5",
        ),
    )


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


def _transaction_projection(transaction_id: str = _CURRENT_TRANSACTION_ID) -> LedgerTransactionProjection:
    return LedgerTransactionProjection.model_validate(
        {
            "transaction_id": transaction_id,
            "date": "2026-04-15",
            "booked_date": "2026-04-15",
            "value_date": None,
            "amount": "121.00",
            "currency": "EUR",
            "direction": "OUTFLOW",
            "counterparty": "Client SL",
            "description": "Invoice 1",
            "business_classification": "MIXED",
            "business_pct": "0.5",
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "iva_category": None,
            "counterparty_country": None,
            "counterparty_identification_state": None,
            "irpf_category": None,
            "m210_income_classification": None,
            "usage_ratio_id": None,
            "prorrata_reference": None,
            "purchase_invoice_evidence_id": None,
            "invoice_id": None,
            "attachment_ids": (),
            "notes": "",
            "lifecycle_state": "ACTIVE",
            "classified_by": "manual",
            "classified_at": None,
            "classification_reason": "",
            "classification_confidence": None,
            "source_jurisdiction": None,
            "value_in_eur": None,
            "fx_rate": None,
            "created_at": "2026-04-15T09:30:00+00:00",
            "modified_at": "2026-04-15T09:30:00+00:00",
        }
    )


def test_registered_allocate_request_is_secure_and_requires_commit() -> None:
    registry, registration = _registry()
    request = _request()

    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=_access_context(registration),
    )

    definition = registry.lookup(operation.LEDGER_ALLOCATE_OPERATION_DEFINITION_ID)
    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert AccessAction.COMMIT in resolved.policy.actions
    assert operation.LedgerAllocateRequest.model_validate_json(request.payload.model_dump_json()) == request.payload


def test_allocate_access_refuses_a_request_for_another_profile() -> None:
    registry, registration = _registry()

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=_request(profile_id=_OTHER_PROFILE),
            context=_access_context(registration),
        )


def test_allocation_share_and_event_projection_are_bounded() -> None:
    with pytest.raises(ValidationError):
        operation.LedgerAllocateRequest(
            profile_id=_PROFILE,
            transaction_id="a" * 12,
            business_pct="1.5",
        )

    projection = operation.LedgerAllocateOperationResult(
        profile_id=_PROFILE,
        transaction=_transaction_projection(),
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("f" * 64,),
    )
    assert operation.LedgerAllocateOperationResult.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        operation.LedgerAllocateOperationResult(
            profile_id=_PROFILE,
            transaction=_transaction_projection(),
            review_status=LedgerReviewStatus.PENDING,
            bucket_event_ids=("f" * 64,) * 4097,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("operation")
async def test_executor_loads_and_resolves_the_current_catalogue_inside_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_commit = False
    loads: list[object] = []
    mutation: dict[str, object] = {}
    authority = cast(PinnedAuthorityOperation, object())
    transaction = Transaction(
        raw=ledger_raw_transaction("allocate-current", booked_date=date(2026, 4, 15), amount=Decimal("121.00")),
        direction=TransactionDirection.OUTGOING,
        source_jurisdiction="ES",
        group_label=None,
    )
    current_id = transaction.transaction_id
    current_catalogue = TransactionCatalogue.from_transactions((transaction,))

    class TransactionRepository(ProfileOnlyCatalogueRepository[TransactionCatalogue]):
        @override
        def load(self, **_kwargs: object) -> TransactionCatalogue:
            assert in_commit
            loads.append(current_catalogue)
            return current_catalogue

    transaction_repository = TransactionRepository(str(_PROFILE))

    def unused_ratio_loader(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
        raise AssertionError("the allocation update seam does not load usage ratios")

    ports = LedgerActionPorts(
        operation=authority,
        transaction_repository=transaction_repository,
        bucket_event_repository=UnusedBucketEventRepository(),
        invoice_repository=ProfileOnlyCatalogueRepository[InvoiceCatalogue](str(_PROFILE)),
        attachment_store=UnusedAttachmentStore(),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=unused_ratio_loader,
        work_unit_repository=ProfileOnlyCatalogueRepository[WorkUnitCatalogue](str(_PROFILE)),
        calculation_repository=ProfileOnlyCatalogueRepository[CalculationRevisionCatalogue](str(_PROFILE)),
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

    events = Events()
    operands = Operands()
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=operation.LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=authority,
        cancellation=Cancellation(),
        events=events,
        operands=operands,
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "_operation_result", lambda _profile_id, _result: projection)

    def update(**kwargs: object) -> SimpleNamespace:
        assert in_commit
        mutation.update(kwargs)
        return SimpleNamespace(bucket_event_ids=("f" * 64,))

    monkeypatch.setattr(operation, "update_manual_transaction_fields", update)
    projection = operation.LedgerAllocateOperationResult(
        profile_id=_PROFILE,
        transaction=_transaction_projection(),
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("f" * 64,),
    )
    executor = operation.LedgerAllocateExecutor(lambda **_kwargs: ports)
    request = OperationRequest[operation.LedgerAllocateRequest](
        definition_id=operation.LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=operation.LedgerAllocateRequest(
            profile_id=_PROFILE,
            transaction_id=current_id[:12],
            business_pct="0.5",
        ),
    )

    result_ref = await executor.execute(request, cast(OperationExecutorContext, context))

    assert result_ref == "d" * 64
    assert len(loads) == 1
    assert mutation["transaction_id"] == current_id
    assert mutation["catalogue"] is current_catalogue
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert operands.value == projection
