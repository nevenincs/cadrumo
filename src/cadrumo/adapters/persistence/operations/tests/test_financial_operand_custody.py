"""Real-filesystem proofs for durable financial operand custody checkpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from .....application.operations.financial_operand import OperationFinancialOperandRefusalReason
from .....application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpoint,
    OperationFinancialOperandCustodyState,
    advance_custody,
)
from .....application.operations.persistence.financial_operand_custody import (
    OperationFinancialOperandCustodyConflictError,
)
from ...storage import RepositoryError
from ..financial_operand_custody import OperationFinancialOperandCustodyFilesystemRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_T0 = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)
_STATE = OperationFinancialOperandCustodyState


def _repository(tmp_path: Path) -> OperationFinancialOperandCustodyFilesystemRepository:
    return OperationFinancialOperandCustodyFilesystemRepository(root=tmp_path / "custody")


def _opened(interaction_id: str = "interaction-1") -> OperationFinancialOperandCustodyCheckpoint:
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id=interaction_id,
        sequence=1,
        state=_STATE.AWAITING_SUBMISSION,
        recorded_at=_T0,
    )


def test_a_checkpoint_survives_a_strict_roundtrip(tmp_path: Path) -> None:
    """What is written is exactly what is read back, field for field."""
    repository = _repository(tmp_path)
    checkpoint = advance_custody(
        _opened(),
        _STATE.CANCELLED,
        now=_T0 + timedelta(seconds=1),
        refusal_reason=OperationFinancialOperandRefusalReason.CANCELLED,
    )

    asyncio.run(repository.open(checkpoint))
    loaded = asyncio.run(repository.read(checkpoint.interaction_id))

    assert loaded == checkpoint
    assert loaded is not checkpoint


def test_an_unopened_wait_reads_as_absent_not_as_empty(tmp_path: Path) -> None:
    """A wait that was never opened is distinguishable from one that settled."""
    assert asyncio.run(_repository(tmp_path).read("never-opened")) is None


def test_a_wait_cannot_be_opened_twice(tmp_path: Path) -> None:
    """Re-opening would discard the custody position already recorded."""
    repository = _repository(tmp_path)
    asyncio.run(repository.open(_opened()))

    with pytest.raises(OperationFinancialOperandCustodyConflictError):
        asyncio.run(repository.open(_opened()))


def test_release_is_exactly_once_when_two_paths_present_the_same_predecessor(tmp_path: Path) -> None:
    """The first swap wins; the loser is refused rather than clearing the buffer twice."""
    repository = _repository(tmp_path)
    acknowledged = OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id="interaction-1",
        sequence=4,
        state=_STATE.DELIVERY_ACKNOWLEDGED,
        recorded_at=_T0,
    )
    asyncio.run(repository.open(acknowledged))

    winner = advance_custody(acknowledged, _STATE.RELEASED, now=_T0 + timedelta(seconds=1))
    loser = advance_custody(acknowledged, _STATE.RELEASED, now=_T0 + timedelta(seconds=2))

    asyncio.run(repository.advance(acknowledged, winner))
    with pytest.raises(OperationFinancialOperandCustodyConflictError):
        asyncio.run(repository.advance(acknowledged, loser))

    assert asyncio.run(repository.read("interaction-1")) == winner


def test_advancing_a_wait_that_is_not_open_is_refused(tmp_path: Path) -> None:
    """A swap cannot create a custody position that was never opened."""
    repository = _repository(tmp_path)
    opened = _opened()
    successor = advance_custody(opened, _STATE.BOUND, now=_T0 + timedelta(seconds=1))

    with pytest.raises(OperationFinancialOperandCustodyConflictError):
        asyncio.run(repository.advance(opened, successor))


def test_a_swap_cannot_move_a_checkpoint_to_another_interaction(tmp_path: Path) -> None:
    """One wait's settlement can never be written over another wait's record."""
    repository = _repository(tmp_path)
    opened = _opened()
    asyncio.run(repository.open(opened))
    foreign = OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id="interaction-2",
        sequence=2,
        state=_STATE.BOUND,
        recorded_at=_T0 + timedelta(seconds=1),
    )

    with pytest.raises(RepositoryError):
        asyncio.run(repository.advance(opened, foreign))


def test_restart_reconciliation_sees_only_unsettled_waits(tmp_path: Path) -> None:
    """A settled wait needs no conclusion, so it is not offered to reconciliation."""
    repository = _repository(tmp_path)
    unsettled = _opened("interaction-open")
    settled = advance_custody(
        _opened("interaction-settled"),
        _STATE.EXPIRED,
        now=_T0 + timedelta(minutes=6),
        refusal_reason=OperationFinancialOperandRefusalReason.EXPIRED,
    )
    asyncio.run(repository.open(unsettled))
    asyncio.run(repository.open(settled))

    remaining = asyncio.run(repository.unsettled())

    assert remaining == (unsettled,)


@pytest.mark.parametrize("interaction_id", ["", "../escape", "nested/id", ".hidden"])
def test_a_traversing_identifier_never_reaches_the_filesystem(tmp_path: Path, interaction_id: str) -> None:
    """An identifier that could leave the custody directory is refused outright."""
    with pytest.raises(RepositoryError):
        asyncio.run(_repository(tmp_path).read(interaction_id))
