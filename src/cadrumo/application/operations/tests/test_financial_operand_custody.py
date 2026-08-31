"""Real-behavior proofs for transient financial operand custody checkpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ..financial_operand import OperationFinancialOperandRefusalReason
from ..financial_operand_custody import (
    OperationFinancialOperandCrashClassification,
    OperationFinancialOperandCustodyCheckpoint,
    OperationFinancialOperandCustodyError,
    OperationFinancialOperandCustodyState,
    advance_custody,
    classify_interrupted_custody,
    reconcile_on_restart,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)
_STATE = OperationFinancialOperandCustodyState


def _checkpoint(
    state: OperationFinancialOperandCustodyState = _STATE.AWAITING_SUBMISSION,
    *,
    sequence: int = 1,
    at: datetime = _T0,
) -> OperationFinancialOperandCustodyCheckpoint:
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id="interaction-1",
        sequence=sequence,
        state=state,
        recorded_at=at,
    )


def test_custody_walks_its_declared_order_to_release() -> None:
    """The happy path advances one step at a time and ends released."""
    checkpoint = _checkpoint()
    for offset, state in enumerate(
        (_STATE.BOUND, _STATE.DELIVERY_STARTED, _STATE.DELIVERY_ACKNOWLEDGED, _STATE.RELEASED),
        start=1,
    ):
        checkpoint = advance_custody(checkpoint, state, now=_T0 + timedelta(seconds=offset))
        assert checkpoint.state is state
        assert checkpoint.sequence == offset + 1

    assert checkpoint.is_terminal


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (_STATE.AWAITING_SUBMISSION, _STATE.DELIVERY_STARTED),
        (_STATE.AWAITING_SUBMISSION, _STATE.RELEASED),
        (_STATE.BOUND, _STATE.DELIVERY_ACKNOWLEDGED),
        (_STATE.DELIVERY_STARTED, _STATE.RELEASED),
        (_STATE.DELIVERY_STARTED, _STATE.CANCELLED),
        (_STATE.DELIVERY_ACKNOWLEDGED, _STATE.EXPIRED),
    ],
)
def test_a_skipped_or_illegal_custody_step_is_refused(
    current: OperationFinancialOperandCustodyState,
    target: OperationFinancialOperandCustodyState,
) -> None:
    """No path may skip delivery, or abandon a wait the executor already holds."""
    with pytest.raises(OperationFinancialOperandCustodyError):
        advance_custody(_checkpoint(current), target, now=_T0 + timedelta(seconds=1))


def test_release_happens_exactly_once_across_racing_paths() -> None:
    """The second supervisor path to reach a released wait is refused, not obeyed."""
    acknowledged = _checkpoint(_STATE.DELIVERY_ACKNOWLEDGED, sequence=4)
    released = advance_custody(acknowledged, _STATE.RELEASED, now=_T0 + timedelta(seconds=1))

    assert released.state is _STATE.RELEASED
    with pytest.raises(OperationFinancialOperandCustodyError):
        advance_custody(released, _STATE.RELEASED, now=_T0 + timedelta(seconds=2))


def test_an_unwatched_wait_still_settles_as_expired() -> None:
    """A lapsed wait settles on its own terms and records why."""
    expired = advance_custody(
        _checkpoint(),
        _STATE.EXPIRED,
        now=_T0 + timedelta(minutes=6),
        refusal_reason=OperationFinancialOperandRefusalReason.EXPIRED,
    )

    assert expired.is_terminal
    assert expired.refusal_reason is OperationFinancialOperandRefusalReason.EXPIRED


def test_a_checkpoint_cannot_move_backwards_in_time() -> None:
    """A journal that accepted a reversed clock could not be replayed in order."""
    with pytest.raises(OperationFinancialOperandCustodyError):
        advance_custody(_checkpoint(at=_T0), _STATE.BOUND, now=_T0 - timedelta(seconds=1))


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (_STATE.AWAITING_SUBMISSION, OperationFinancialOperandCrashClassification.NOT_DELIVERED),
        (_STATE.BOUND, OperationFinancialOperandCrashClassification.NOT_DELIVERED),
        (_STATE.DELIVERY_STARTED, OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN),
        (_STATE.DELIVERY_ACKNOWLEDGED, OperationFinancialOperandCrashClassification.DELIVERED),
    ],
)
def test_an_interrupted_wait_is_classified_by_how_far_it_got(
    state: OperationFinancialOperandCustodyState,
    expected: OperationFinancialOperandCrashClassification,
) -> None:
    """Only the position reached decides what a restart may conclude."""
    assert classify_interrupted_custody(_checkpoint(state)) is expected


def test_a_settled_wait_needs_no_crash_conclusion() -> None:
    """A terminal checkpoint is already an answer and is not reclassified."""
    for state in (_STATE.RELEASED, _STATE.EXPIRED, _STATE.CANCELLED):
        assert classify_interrupted_custody(_checkpoint(state)) is None


def test_restart_never_invents_an_acknowledgement_it_did_not_witness() -> None:
    """An interrupted delivery settles released but stays recorded as uncertain."""
    reconciled = reconcile_on_restart(_checkpoint(_STATE.DELIVERY_STARTED, sequence=3), now=_T0 + timedelta(hours=1))

    assert reconciled.state is _STATE.RELEASED
    assert reconciled.crash_classification is OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN
    assert reconciled.state is not _STATE.DELIVERY_ACKNOWLEDGED


def test_restart_cancels_a_wait_nothing_was_delivered_to() -> None:
    """A wait that never reached delivery is closed as cancelled, not released."""
    reconciled = reconcile_on_restart(_checkpoint(_STATE.BOUND, sequence=2), now=_T0 + timedelta(hours=1))

    assert reconciled.state is _STATE.CANCELLED
    assert reconciled.refusal_reason is OperationFinancialOperandRefusalReason.CANCELLED
    assert reconciled.crash_classification is OperationFinancialOperandCrashClassification.NOT_DELIVERED


def test_restart_leaves_an_already_settled_wait_untouched() -> None:
    """Reconciliation is idempotent over a journal that already terminated."""
    settled = _checkpoint(_STATE.RELEASED, sequence=5)

    assert reconcile_on_restart(settled, now=_T0 + timedelta(hours=1)) is settled


def test_no_custody_checkpoint_can_carry_operand_material() -> None:
    """The durable record names the wait, never the amount that answered it."""
    forbidden = ("amount", "value", "digest", "hash", "fingerprint", "operand_value")
    for name in OperationFinancialOperandCustodyCheckpoint.model_fields:
        assert not any(token in name.lower() for token in forbidden), name


def test_a_delivered_checkpoint_cannot_claim_a_refusal_reason() -> None:
    """Only a wait that ended without delivery explains itself with a reason."""
    with pytest.raises(ValidationError):
        OperationFinancialOperandCustodyCheckpoint(
            operand_kind="pago.fraccionado",
            interaction_id="interaction-1",
            sequence=2,
            state=_STATE.DELIVERY_ACKNOWLEDGED,
            recorded_at=_T0,
            refusal_reason=OperationFinancialOperandRefusalReason.CANCELLED,
        )
