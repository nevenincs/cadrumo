"""Actual durable one-shot custody, concurrent consumers, expiry and owner loss."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from .....application.operations.financial_operand_contract import (
    OperationFinancialOperandEffectReceiptV1,
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandRequirementV1,
    financial_operand_model_identity,
)
from .....application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpointV1,
    OperationFinancialOperandCustodyState,
)
from .....application.operations.models import OperationIdentity
from .....application.operations.tests.financial_operand_models import FinancialOperandBaseline, FinancialOperandBatch
from .....application.operations.typed_financial_operand_submission import OperationTypedFinancialOperandBroker
from .....core.operations import OperationEffect
from ..typed_financial_operand_custody import OperationTypedFinancialOperandCustodyFilesystemRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _declaration(
    *, lifetime: timedelta = timedelta(minutes=1), committed: bool = False
) -> OperationTransientFinancialOperandDeclarationV1:
    def baseline(operand: BaseModel) -> BaseModel:
        return cast(FinancialOperandBatch, operand).baseline

    def reference(value: BaseModel) -> str:
        return cast(FinancialOperandBaseline, value).baseline_id

    async def receipt(
        requirement: OperationTransientFinancialOperandRequirementV1,
    ) -> OperationFinancialOperandEffectReceiptV1 | None:
        if not committed:
            return None
        return OperationFinancialOperandEffectReceiptV1(
            identity=requirement.identity,
            handoff_id=requirement.handoff_id,
            domain_baseline_ref=requirement.domain_baseline_ref,
            effect=OperationEffect.UPDATED,
        )

    return OperationTransientFinancialOperandDeclarationV1(
        operand_type=FinancialOperandBatch,
        baseline_type=FinancialOperandBaseline,
        operand_schema=financial_operand_model_identity(
            schema_id="test.batch", schema_version=1, model_type=FinancialOperandBatch
        ),
        baseline_schema=financial_operand_model_identity(
            schema_id="test.baseline", schema_version=1, model_type=FinancialOperandBaseline
        ),
        baseline_accessor=baseline,
        baseline_reference=reference,
        lifetime=lifetime,
        effect_receipt_resolver=receipt,
    )


def _batch() -> FinancialOperandBatch:
    return FinancialOperandBatch(
        baseline=FinancialOperandBaseline(baseline_id="d" * 64),
        values=(Decimal("17.23"), Decimal("-4.12"), Decimal("0.125")),
    )


def test_concurrent_consumption_is_once_and_second_consumer_cannot_release_the_first(tmp_path: Path) -> None:
    async def exercise() -> None:
        lock = asyncio.Lock()
        repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")

        async def current(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            assert lock.locked()

        async def expiry(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            pytest.fail("unexpired batch cannot expire")

        broker = OperationTypedFinancialOperandBroker(
            custody=repository,
            clock=lambda: datetime.now(UTC),
            lock_for=lambda _: lock,
            require_current=current,
            settle_expiry=expiry,
        )
        declaration = _declaration()
        submission = await broker.open(
            declaration=declaration,
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="unit"),
            revision=0,
            domain_baseline_ref="d" * 64,
        )
        expected = _batch()
        submission.operand = expected
        requirement = submission.requirement
        await broker.submit(submission)
        assert submission.operand is None and submission.grant == bytearray(32)
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def first() -> None:
            async with broker.consume(requirement, declaration) as operand:
                assert operand is expected
                entered.set()
                await finish.wait()
            del operand

        task = asyncio.create_task(first())
        await entered.wait()
        with pytest.raises(OperationFinancialOperandRefusedError) as refusal:
            async with broker.consume(requirement, declaration):
                pytest.fail("second consumer must not enter")
        assert refusal.value.reason is OperationFinancialOperandRefusalCode.DUPLICATE_CONSUMPTION
        checkpoint = await repository.read(requirement.handoff_id)
        assert (
            checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED
        )
        assert not await broker.cancel(requirement)
        finish.set()
        await task
        checkpoint = await repository.read(requirement.handoff_id)
        assert checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.RELEASED
        # Custody release does not prove a domain commit, even after acknowledgement.
        assert (await broker.reconcile(requirement, declaration)).effect is OperationEffect.UNKNOWN
        assert (await broker.reconcile(requirement, _declaration(committed=True))).effect is OperationEffect.UPDATED
        stored = next((tmp_path / "custody").glob("*.json")).read_text(encoding="utf-8")
        assert "17.23" not in stored and "-4.12" not in stored and "0.125" not in stored
        await broker.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("fault", ("grant", "model", "baseline"))
def test_wrong_binding_refuses_and_clears_submission_without_exposure(tmp_path: Path, fault: str) -> None:
    async def exercise() -> None:
        repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        lock = asyncio.Lock()

        async def current(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            assert lock.locked()

        async def expiry(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            pass

        broker = OperationTypedFinancialOperandBroker(
            custody=repository,
            clock=lambda: datetime.now(UTC),
            lock_for=lambda _: lock,
            require_current=current,
            settle_expiry=expiry,
        )
        declaration = _declaration()
        submission = await broker.open(
            declaration=declaration,
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="unit"),
            revision=0,
            domain_baseline_ref="d" * 64,
        )
        submission.operand = _batch()
        if fault == "grant":
            submission.grant[0] ^= 1
        elif fault == "model":
            submission.operand = FinancialOperandBaseline(baseline_id="d" * 64)
        else:
            submission.operand = FinancialOperandBatch(
                baseline=FinancialOperandBaseline(baseline_id="e" * 64), values=()
            )
        with pytest.raises(OperationFinancialOperandRefusedError) as refused:
            await broker.submit(submission)
        assert (
            refused.value.reason
            is {
                "grant": OperationFinancialOperandRefusalCode.WRONG_GRANT,
                "model": OperationFinancialOperandRefusalCode.WRONG_MODEL,
                "baseline": OperationFinancialOperandRefusalCode.WRONG_BASELINE,
            }[fault]
        )
        assert submission.operand is None and submission.grant == bytearray(32)
        assert (await broker.reconcile(submission.requirement, declaration)).effect is OperationEffect.NONE
        await broker.close()

    asyncio.run(exercise())


def test_unobserved_expiry_settles_outside_the_operation_lock(tmp_path: Path) -> None:
    async def exercise() -> None:
        repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        lock = asyncio.Lock()
        expired = asyncio.Event()

        async def current(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            assert lock.locked()

        async def expiry(requirement: OperationTransientFinancialOperandRequirementV1) -> None:
            async with lock:
                checkpoint = await repository.read(requirement.handoff_id)
                assert checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.EXPIRED
                expired.set()

        broker = OperationTypedFinancialOperandBroker(
            custody=repository,
            clock=lambda: datetime.now(UTC),
            lock_for=lambda _: lock,
            require_current=current,
            settle_expiry=expiry,
        )
        declaration = _declaration(lifetime=timedelta(milliseconds=80))
        submission = await broker.open(
            declaration=declaration,
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="unit"),
            revision=0,
            domain_baseline_ref="d" * 64,
        )
        await asyncio.wait_for(expired.wait(), timeout=5)
        assert (await broker.reconcile(submission.requirement, declaration)).effect is OperationEffect.NONE
        submission.release()
        await broker.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("state", tuple(OperationFinancialOperandCustodyState))
def test_restart_uses_the_exact_durable_position_and_never_infers_a_domain_commit(
    tmp_path: Path, state: OperationFinancialOperandCustodyState
) -> None:
    """Every prefix remains amount-free; a release alone is not evidence of a domain effect."""

    async def exercise() -> None:
        repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        declaration = _declaration()
        lock = asyncio.Lock()

        async def current(requirement) -> None:
            assert lock.locked()

        async def expiry(requirement) -> None:
            raise AssertionError("reconciliation must not reconstruct a live operand wait")

        requirement = OperationTransientFinancialOperandRequirementV1(
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="unit"),
            invocation_revision=1,
            handoff_id="b" * 64,
            grant_fingerprint="c" * 64,
            operand_schema=declaration.operand_schema,
            baseline_schema=declaration.baseline_schema,
            domain_baseline_ref="d" * 64,
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        checkpoint = OperationFinancialOperandCustodyCheckpointV1(
            requirement=requirement,
            sequence=1,
            state=OperationFinancialOperandCustodyState.AWAITING_SUBMISSION,
            recorded_at=datetime.now(UTC),
        )
        await repository.open(checkpoint)
        ordered = (
            OperationFinancialOperandCustodyState.BOUND,
            OperationFinancialOperandCustodyState.DELIVERY_STARTED,
            OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED,
            OperationFinancialOperandCustodyState.RELEASED,
        )
        path = (
            ordered[: ordered.index(state) + 1]
            if state in ordered
            else (() if state is OperationFinancialOperandCustodyState.AWAITING_SUBMISSION else (state,))
        )
        for position in path:
            successor = checkpoint.successor(position, now=datetime.now(UTC))
            await repository.advance(checkpoint, successor)
            checkpoint = successor
        restarted = OperationTypedFinancialOperandBroker(
            custody=repository,
            clock=lambda: datetime.now(UTC),
            lock_for=lambda _: lock,
            require_current=current,
            settle_expiry=expiry,
        )
        receipt = await restarted.reconcile(requirement, declaration)
        uncertain = state in ordered[1:]
        assert receipt.effect is (OperationEffect.UNKNOWN if uncertain else OperationEffect.NONE)
        if uncertain:
            authoritative = await restarted.reconcile(requirement, _declaration(committed=True))
            assert authoritative.effect is OperationEffect.UPDATED
        assert await repository.read(requirement.handoff_id) == checkpoint
        await restarted.close()

    asyncio.run(exercise())


def test_close_cannot_release_an_operand_while_its_executor_scope_is_still_using_it(tmp_path: Path) -> None:
    async def exercise() -> None:
        repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
        lock = asyncio.Lock()

        async def current(requirement) -> None:
            assert lock.locked()

        async def expiry(requirement) -> None:
            raise AssertionError("unexpired delivery cannot expire")

        broker = OperationTypedFinancialOperandBroker(
            custody=repository,
            clock=lambda: datetime.now(UTC),
            lock_for=lambda _: lock,
            require_current=current,
            settle_expiry=expiry,
        )
        declaration = _declaration()
        submission = await broker.open(
            declaration=declaration,
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="unit"),
            revision=1,
            domain_baseline_ref="d" * 64,
        )
        requirement = submission.requirement
        submission.operand = _batch()
        await broker.submit(submission)
        entered, finish = asyncio.Event(), asyncio.Event()

        async def consume() -> None:
            async with broker.consume(requirement, declaration) as operand:
                entered.set()
                await finish.wait()
                assert isinstance(operand, FinancialOperandBatch)
                assert operand.values == _batch().values
                del operand

        consumer = asyncio.create_task(consume())
        await entered.wait()
        closing = asyncio.create_task(broker.close())
        await asyncio.sleep(0)
        assert not closing.done()
        checkpoint = await repository.read(requirement.handoff_id)
        assert (
            checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED
        )
        finish.set()
        await asyncio.gather(consumer, closing)
        checkpoint = await repository.read(requirement.handoff_id)
        assert checkpoint is not None and checkpoint.state is OperationFinancialOperandCustodyState.RELEASED

    asyncio.run(exercise())
