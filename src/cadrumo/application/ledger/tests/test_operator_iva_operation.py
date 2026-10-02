"""Operator IVA execution retains its profile, reviewed baseline and effect truth."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import BucketTransactionRef
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import classify_operation as subject
from ..action_ports import LedgerActionPortsFactory
from ..llm_classification_ports import OperatorIvaDerivationResult
from ..models import ManualLedgerTransactionResult
from ..persistence_ports import LedgerPersistenceConflictError
from .test_classify_operation import _current_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_CATEGORY = "domestic_general"


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.value: BaseModel | None = None
        self.failure: OSError | None = None

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        if self.failure is not None:
            raise self.failure
        self.value = operand
        return "d" * 64


class _ExecutorPort:
    """Explicit repository, writer and COMMIT ports for the actual executor."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, authority: PinnedAuthorityOperation) -> None:
        self.in_commit = False
        self.current = _current_transaction()
        self.catalogue = SimpleNamespace(transactions={self.current.transaction_id: self.current})
        self.loads = 0
        self.writes: list[dict[str, object]] = []
        self.writer_failure: Exception | None = None
        self.events = _Events()
        self.operands = _Operands()
        owner = self

        class Repository:
            bucket_id = str(_PROFILE)

            def load(self) -> object:
                assert owner.in_commit
                owner.loads += 1
                return owner.catalogue

        class Cancellation:
            @asynccontextmanager
            async def irreversible_section(self):
                assert not owner.in_commit
                owner.in_commit = True
                try:
                    yield
                finally:
                    owner.in_commit = False

        self.ports = SimpleNamespace(
            operation=authority,
            transaction_repository=Repository(),
            invoice_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
            work_unit_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
            calculation_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        )
        self.context = SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=subject.LEDGER_OPERATOR_IVA_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=authority,
            cancellation=Cancellation(),
            events=self.events,
            operands=self.operands,
        )
        self.request = OperationRequest[subject.LedgerOperatorIvaRequest](
            definition_id=subject.LEDGER_OPERATOR_IVA_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=subject.LedgerOperatorIvaRequest(
                profile_id=_PROFILE,
                transaction_id=self.current.transaction_id[:12].upper(),
                iva_category=_CATEGORY,
                actor="operator",
            ),
        )

        def derive(**kwargs: object) -> OperatorIvaDerivationResult:
            assert self.in_commit
            self.writes.append(kwargs)
            if self.writer_failure is not None:
                raise self.writer_failure
            return OperatorIvaDerivationResult(
                transaction_id=self.current.transaction_id,
                iva_category=IvaCategory(_CATEGORY),
                derivable=True,
                iva_rate=Decimal("0.21"),
                taxable_base=Decimal("100"),
                iva_amount=Decimal("21"),
                result=ManualLedgerTransactionResult(
                    ref=BucketTransactionRef(bucket_id=str(_PROFILE), transaction_id=self.current.transaction_id),
                    transaction=self.current,
                    bucket_event_ids=("e" * 64,),
                ),
            )

        monkeypatch.setattr(subject, "require_active_bucket_id", lambda: str(_PROFILE))
        monkeypatch.setattr(subject, "derive_operator_iva_substrate", derive)
        self.executor = subject.LedgerOperatorIvaExecutor(cast(LedgerActionPortsFactory, lambda **_kwargs: self.ports))

    async def execute(self) -> str | OperationRefusalEvidence:
        return await self.executor.execute(self.request, cast(OperationExecutorContext, self.context))


def _registration():
    def unused(**_kwargs: object):
        raise AssertionError("registration must not acquire execution ports")

    definition = subject.build_ledger_operator_iva_definition(cast(LedgerActionPortsFactory, unused))
    return definition, subject.build_ledger_operator_iva_registration(definition)


def test_registration_keeps_private_execution_and_strict_public_exact_profile_contract() -> None:
    definition, registration = _registration()
    assert definition.result_type is subject.LedgerOperatorIvaExecutionResult
    assert {binding.model_type for binding in registration.schema_bindings} == {
        subject.LedgerOperatorIvaRequest,
        subject.LedgerOperatorIvaResult,
    }
    payload = subject.LedgerOperatorIvaRequest(
        profile_id=_PROFILE, transaction_id="ABCDEF123456", iva_category=_CATEGORY
    )
    assert payload.transaction_id == "abcdef123456"
    with pytest.raises(ValidationError):
        subject.LedgerOperatorIvaRequest.model_validate({**payload.model_dump(), "master_key": "unexpected"})
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )
    assert (
        AccessAction.COMMIT
        in resolve_operation_access(registry=registry, request=request, context=context).policy.actions
    )
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=request.model_copy(
                update={
                    "subject_ref": profile_operation_subject(str(_OTHER)),
                    "payload": payload.model_copy(update={"profile_id": _OTHER}),
                }
            ),
            context=context,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["request", "dependent_repository"])
async def test_executor_refuses_profile_escape_before_repository_or_writer(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, mismatch: str
) -> None:
    port = _ExecutorPort(monkeypatch, operation)
    if mismatch == "request":
        port.request = port.request.model_copy(
            update={"payload": port.request.payload.model_copy(update={"profile_id": _OTHER})}
        )
    else:
        port.ports.invoice_repository.bucket_id = str(_OTHER)
    with pytest.raises(ProfileAccessRefusedError):
        await port.execute()
    assert port.loads == 0
    assert port.writes == []
    assert port.operands.value is None
    assert port.events.effects == []


@pytest.mark.asyncio
async def test_executor_lends_original_baseline_to_existing_deriver_inside_commit(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
) -> None:
    port = _ExecutorPort(monkeypatch, operation)
    assert await port.execute() == "d" * 64
    assert port.loads == 1
    assert len(port.writes) == 1
    assert port.writes[0]["expected_current"] is port.current
    assert port.writes[0]["transaction_id"] == port.current.transaction_id
    assert port.writes[0]["ports"] is port.ports
    assert port.writes[0]["bucket_id"] == str(_PROFILE)
    assert port.writes[0]["actor"] == "operator"
    assert port.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert not port.in_commit
    assert isinstance(port.operands.value, subject.LedgerOperatorIvaExecutionResult)
    assert port.operands.value.request == port.request.payload
    assert port.operands.value.result.transaction_id == port.current.transaction_id


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["prepare", "writer"])
async def test_validation_refusal_keeps_none_effect_and_typed_bounded_detail(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, where: str
) -> None:
    port = _ExecutorPort(monkeypatch, operation)
    if where == "prepare":
        port.request = port.request.model_copy(
            update={"payload": port.request.payload.model_copy(update={"iva_category": "not-a-declared-category"})}
        )
    else:
        port.writer_failure = TransactionValidationError("pre-write validation refused")
    evidence = await port.execute()
    assert isinstance(evidence, OperationRefusalEvidence)
    assert evidence.refusal_code == subject.LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
    assert evidence.detail_ref == "d" * 64
    assert port.events.effects == ([] if where == "prepare" else [OperationEffect.UNKNOWN, OperationEffect.NONE])
    assert len(port.writes) == (0 if where == "prepare" else 1)
    assert isinstance(port.operands.value, subject.LedgerOperatorIvaExecutionResult)
    assert port.operands.value.result.outcome == "validation_error"
    assert port.operands.value.result.classification is None
    assert port.operands.value.result.validation_messages


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", [True, False])
async def test_writer_failure_distinguishes_stale_none_from_unexpected_unknown(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, stale: bool
) -> None:
    port = _ExecutorPort(monkeypatch, operation)
    failure = LedgerPersistenceConflictError("newer row won") if stale else OSError("writer outcome unavailable")
    port.writer_failure = failure
    with pytest.raises(type(failure)) as raised:
        await port.execute()
    assert raised.value is failure
    assert port.events.effects == (
        [OperationEffect.UNKNOWN, OperationEffect.NONE] if stale else [OperationEffect.UNKNOWN]
    )
    assert port.operands.value is None
    assert len(port.writes) == 1
    assert port.writes[0]["expected_current"] is port.current


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["projection", "put"])
async def test_post_write_failure_retains_updated_effect(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, where: str
) -> None:
    port = _ExecutorPort(monkeypatch, operation)
    failure = OSError("post-write result unavailable")
    if where == "put":
        port.operands.failure = failure
    else:

        def project(*_args: object) -> BaseModel:
            raise failure

        monkeypatch.setattr(subject, "_operation_result", project)
    with pytest.raises(OSError) as raised:
        await port.execute()
    assert raised.value is failure
    assert port.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert len(port.writes) == 1
    assert port.operands.value is None


def test_refusal_projection_correlates_normalized_request_profile_category_and_receipt() -> None:
    definition, registration = _registration()
    assert registration.result_projector is not None
    request = subject.LedgerOperatorIvaRequest(
        profile_id=_PROFILE, transaction_id="ABCDEF123456", iva_category=_CATEGORY
    )
    result = subject.LedgerOperatorIvaResult(
        profile_id=_PROFILE,
        outcome="validation_error",
        transaction_id="abcdef123456" + "b" * 52,
        iva_category=_CATEGORY,
        derivable=False,
        validation_messages=("Category unavailable for this row",),
    )
    execution = subject.LedgerOperatorIvaExecutionResult(request=request, result=result)
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 4, 15, tzinfo=UTC),
        refusal_ref=subject.LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
        refusal_detail_ref="e" * 64,
    )
    assert registration.result_projector(execution, receipt) == result
    for update in ({"profile_id": _OTHER}, {"iva_category": "another-category"}, {"transaction_id": "c" * 64}):
        with pytest.raises(ValueError):
            registration.result_projector(
                execution.model_copy(update={"result": result.model_copy(update=update)}), receipt
            )
    with pytest.raises(ValueError):
        registration.result_projector(execution, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))
    with pytest.raises(ValueError):
        registration.result_projector(execution, receipt.model_copy(update={"refusal_ref": "unrelated_refusal"}))
