"""A confirmed Ledger flow cannot skip confirmation or abandon a write in flight.

``LedgerClassificationScreen`` and ``LedgerImportScreen`` both drive their
command through this machine, and until now nothing pinned it: the transition
table was a dict rebuilt inside the method, so it could not be read or asserted
against, and neither screen's states were covered.

Two absences in the table carry the safety, and both are asserted below rather
than left implicit. ``EDITING`` cannot reach ``SUBMITTING``, so no ledger write
happens without passing the confirmation step. ``SUBMITTING`` cannot reach
``CANCELLED``, so a write already dispatched cannot be walked away from — the
guarantee ``action_back`` refuses out loud when an operator presses Escape
mid-submit.

Every ordered pair of states is exercised, not a sample: a spot check would
pass while some other pair had quietly become legal.
"""

from __future__ import annotations

import pytest

from ..ledger.models import LedgerFlowState
from ..ledger.workspace_presentation import ALLOWED_FLOW_TRANSITIONS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The complete machine, restated independently of the production mapping.
_EXPECTED: dict[LedgerFlowState, set[LedgerFlowState]] = {
    LedgerFlowState.EDITING: {LedgerFlowState.CONFIRMING, LedgerFlowState.CANCELLED},
    LedgerFlowState.CONFIRMING: {LedgerFlowState.SUBMITTING, LedgerFlowState.CANCELLED},
    LedgerFlowState.SUBMITTING: {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED},
    LedgerFlowState.SUCCEEDED: set(),
    LedgerFlowState.FAILED: set(),
    LedgerFlowState.CANCELLED: set(),
}

_PAIRS = [(source, target) for source in LedgerFlowState for target in LedgerFlowState]


@pytest.mark.parametrize(("source", "target"), _PAIRS, ids=lambda state: state.value)
def test_every_ordered_pair_of_states_matches_the_specification(
    source: LedgerFlowState,
    target: LedgerFlowState,
) -> None:
    """All 36 pairs, so a newly-legal move cannot hide between spot checks."""
    permitted = target in ALLOWED_FLOW_TRANSITIONS.get(source, frozenset())

    assert permitted is (target in _EXPECTED[source])


def test_a_write_cannot_start_without_confirmation() -> None:
    """The first safety absence, stated on its own so it cannot be lost in a table."""
    assert LedgerFlowState.SUBMITTING not in ALLOWED_FLOW_TRANSITIONS[LedgerFlowState.EDITING]


def test_a_write_in_flight_cannot_be_abandoned() -> None:
    """The second: Escape during submit must have nowhere to go.

    ``action_back`` renders a refusal for this state; if the machine permitted
    the move, that refusal would be the only thing standing between an operator
    and a half-observed write.
    """
    assert LedgerFlowState.CANCELLED not in ALLOWED_FLOW_TRANSITIONS[LedgerFlowState.SUBMITTING]


@pytest.mark.parametrize(
    "terminal",
    [LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED, LedgerFlowState.CANCELLED],
    ids=lambda state: state.value,
)
def test_a_settled_flow_admits_no_further_move(terminal: LedgerFlowState) -> None:
    """Terminal states are absorbing, so a screen cannot be re-edited after it settles."""
    assert ALLOWED_FLOW_TRANSITIONS.get(terminal, frozenset()) == frozenset()


def test_every_state_is_either_reachable_or_a_start() -> None:
    """No orphan state: one nothing can enter would be dead or a missing edge."""
    reachable = {target for targets in ALLOWED_FLOW_TRANSITIONS.values() for target in targets}

    assert set(LedgerFlowState) - reachable == {LedgerFlowState.EDITING}


def test_every_non_terminal_state_can_be_left() -> None:
    """A state with no exit that is not terminal would strand the operator."""
    stuck = [state for state, targets in ALLOWED_FLOW_TRANSITIONS.items() if not targets]

    assert stuck == []
