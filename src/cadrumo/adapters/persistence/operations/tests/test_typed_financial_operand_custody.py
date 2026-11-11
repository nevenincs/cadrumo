"""Actual hardened typed financial custody refuses stale and redirected writes."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....application.operations.financial_operand_contract import (
    OperationTransientFinancialOperandRequirementV1,
    financial_operand_model_identity,
)
from .....application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpointV1,
    OperationFinancialOperandCustodyState,
)
from .....application.operations.models import OperationIdentity
from .....application.operations.persistence.financial_operand_custody import (
    OperationFinancialOperandCustodyConflictError,
)
from .....application.operations.tests.financial_operand_models import FinancialOperandBaseline, FinancialOperandBatch
from .....tests.thread_file_io_probe import recording_file_io
from ...storage.errors import RepositoryError
from ..typed_financial_operand_custody import OperationTypedFinancialOperandCustodyFilesystemRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_NOW = datetime(2026, 10, 5, tzinfo=UTC)


def _checkpoint() -> OperationFinancialOperandCustodyCheckpointV1:
    return OperationFinancialOperandCustodyCheckpointV1(
        requirement=OperationTransientFinancialOperandRequirementV1(
            identity=OperationIdentity(operation_id="a" * 64, definition_id="modelo.edit.apply", subject_ref="subject"),
            invocation_revision=1,
            handoff_id="b" * 64,
            grant_fingerprint="c" * 64,
            operand_schema=financial_operand_model_identity(
                schema_id="test.batch", schema_version=1, model_type=FinancialOperandBatch
            ),
            baseline_schema=financial_operand_model_identity(
                schema_id="test.baseline", schema_version=1, model_type=FinancialOperandBaseline
            ),
            domain_baseline_ref="d" * 64,
            expires_at=_NOW + timedelta(minutes=5),
        ),
        sequence=1,
        state=OperationFinancialOperandCustodyState.AWAITING_SUBMISSION,
        recorded_at=_NOW,
    )


def test_real_store_preserves_the_exact_requirement_and_refuses_stale_cas(tmp_path: Path) -> None:
    """Every custody position retains its invocation, baseline, grant and model coordinates."""
    repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
    original = _checkpoint()

    async def exercise() -> None:
        await repository.open(original)
        bound = original.successor(OperationFinancialOperandCustodyState.BOUND, now=_NOW)
        await repository.advance(original, bound)
        assert await repository.read(original.requirement.handoff_id) == bound
        with pytest.raises(OperationFinancialOperandCustodyConflictError):
            await repository.advance(original, bound)
        with pytest.raises(OperationFinancialOperandCustodyConflictError):
            await repository.open(original)

    asyncio.run(exercise())


def test_a_changed_baseline_cannot_ride_a_legal_custody_transition(tmp_path: Path) -> None:
    """State progression never launders a forged requirement."""
    repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
    original = _checkpoint()
    asyncio.run(repository.open(original))
    successor = original.successor(OperationFinancialOperandCustodyState.BOUND, now=_NOW)
    forged = successor.model_copy(
        update={"requirement": successor.requirement.model_copy(update={"domain_baseline_ref": "e" * 64})}
    )
    with pytest.raises(OperationFinancialOperandCustodyConflictError):
        asyncio.run(repository.advance(original, forged))
    assert asyncio.run(repository.read(original.requirement.handoff_id)) == original


@pytest.mark.parametrize("identifier", ("../escape", "short", "A" * 64))
def test_invalid_handoff_is_refused_before_creating_any_directory(tmp_path: Path, identifier: str) -> None:
    """Coordinates are validated even when no current custody root exists."""
    root = tmp_path / "custody"
    repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=root)
    with pytest.raises(RepositoryError):
        asyncio.run(repository.read(identifier))
    assert not root.exists()


def test_typed_custody_does_not_read_or_write_files_on_the_awaiting_thread(tmp_path: Path) -> None:
    """A native operation loop stays responsive throughout durable custody changes."""
    repository = OperationTypedFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")
    original = _checkpoint()

    async def exercise() -> None:
        with recording_file_io(threading.get_ident()) as observations:
            await repository.open(original)
            await repository.read(original.requirement.handoff_id)
            await repository.advance(
                original, original.successor(OperationFinancialOperandCustodyState.BOUND, now=_NOW)
            )
        assert not observations

    asyncio.run(exercise())
