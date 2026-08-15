"""Unit-lane structural cover for two live-scoring properties.

Both properties are exercised by ``test_live_harness.py``, but every test in
that module is ``integration``-marked, so the default ``-m unit`` selection
deselects all of them. Two deliberate mutations were therefore able to survive
a green ``-m unit`` run of this package: making the narration corpus
non-cumulative, and inverting the lifecycle ordering predicate. These tests put
both properties in the lane the mutations survived.

They assert STRUCTURE, never a value the code under test produced: the
lifecycle predicate is a pure function checked against hand-built position
maps, and the corpus property is read off the arguments the scorer passes to
its injected faithfulness port, not off any verdict the scorer computed.

``_ObservedFaithfulnessCheck`` is an implementation of the caller-injected
``FaithfulnessCheckFn`` port, not a double of the code under test. The scorer's
own contract is that the caller supplies this callable
(``dev.agent_eval`` never imports the MCP server layer), so providing one
here is the architecture's intended seam; the assertions read the corpus it was
handed rather than any answer it returned.
"""

from __future__ import annotations

# INTENTIONAL: unit because it exercises `_live_scoring`'s structural
# properties (narration-corpus cumulativity, lifecycle ordering) against a
# caller-injected faithfulness port and hand-built fixtures, never a live
# AEAT surface. "Live" here names the module under test, not external I/O.
import pytest

from .._live_scoring import _score_narration_faithfulness
from .._models import (
    LIFECYCLE_STAGE_ORDER,
    LiveNarrationRecord,
    LiveToolCallRecord,
    LiveTrajectory,
    lifecycle_stages_in_canonical_order,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CREATE, _CALCULATE, _VERIFY, _EXPORT = LIFECYCLE_STAGE_ORDER


class _FaithfulnessVerdict:
    """The three fields the scorer reads off a faithfulness verdict."""

    def __init__(self, *, blocking: bool) -> None:
        self.faithful = True
        self.blocking = blocking
        self.flagged_values: tuple[str, ...] = ()


class _ObservedFaithfulnessCheck:
    """A real implementation of the injected port that records what it was asked."""

    def __init__(self) -> None:
        self.corpora: list[str] = []

    def __call__(self, *, agent_text: str, tool_result_json: str, blocking: bool = False) -> object:
        del agent_text
        self.corpora.append(tool_result_json)
        return _FaithfulnessVerdict(blocking=blocking)


def _call(command_key: str, *, result: str = "") -> LiveToolCallRecord:
    return LiveToolCallRecord(
        tool_name="cadrumo_" + command_key.replace(".", "_"),
        command_key=command_key,
        result_text=result,
    )


def test_canonical_stage_order_holds() -> None:
    """The positive control: stages at increasing positions are in order.

    Without it, the out-of-order assertion below would also pass against a
    predicate that simply returned ``False`` for everything.
    """
    positions = {stage: index for index, stage in enumerate(LIFECYCLE_STAGE_ORDER)}

    assert lifecycle_stages_in_canonical_order(positions) is True


def test_a_stage_out_of_sequence_breaks_the_order() -> None:
    """Export observed before verify violates the canonical order."""
    positions = {_CREATE: 0, _CALCULATE: 1, _EXPORT: 2, _VERIFY: 3}

    assert lifecycle_stages_in_canonical_order(positions) is False


def test_absent_stages_are_unconstrained() -> None:
    """A trajectory that legitimately stops early is ordered, not incomplete.

    The predicate asks only that the stages which DO appear appear in order, so
    a run ending at verify must not be reported as an ordering violation.
    """
    assert lifecycle_stages_in_canonical_order({_CREATE: 0, _CALCULATE: 1, _VERIFY: 2}) is True
    assert lifecycle_stages_in_canonical_order({_CREATE: 0, _EXPORT: 1}) is True
    assert lifecycle_stages_in_canonical_order({}) is True


def test_narration_corpus_is_cumulative_across_the_narration_walk() -> None:
    """Each narration is judged against every tool result the session has seen.

    The second narration consumes only calls whose results are empty, so if the
    corpus were rebuilt per narration it would lose the figure ``calculate``
    returned. Asserting the second corpus EXTENDS the first is a structural
    read of the port's arguments; it does not depend on any verdict.
    """
    trajectory = LiveTrajectory(
        scenario="cumulative-corpus",
        persona="cadrumo-verifier",
        session_id="unit",
        tool_calls=(
            _call(_CREATE),
            _call(_CALCULATE, result='{"casilla_07": "500.00"}'),
            _call(_VERIFY),
            _call(_EXPORT),
        ),
        narrations=(
            LiveNarrationRecord(step=_CALCULATE, text="the calculation is complete"),
            LiveNarrationRecord(step=_EXPORT, text="the quarter result casilla 07 is 500.00"),
        ),
    )
    recorder = _ObservedFaithfulnessCheck()

    _score_narration_faithfulness(
        trajectory,
        faithfulness_check_fn=recorder,
        handoff_leaves=frozenset({"export"}),
    )

    assert len(recorder.corpora) == 2
    first, second = recorder.corpora
    assert "500.00" in first
    assert second.startswith(first)
    assert len(second) > len(first)
    assert "500.00" in second


def test_the_handoff_narration_is_the_blocking_one() -> None:
    """Only a narration on an irreversible handoff leaf is checked as blocking."""
    trajectory = LiveTrajectory(
        scenario="blocking-flag",
        persona="cadrumo-verifier",
        session_id="unit",
        tool_calls=(_call(_CALCULATE), _call(_EXPORT)),
        narrations=(
            LiveNarrationRecord(step=_CALCULATE, text="calculated"),
            LiveNarrationRecord(step=_EXPORT, text="exported"),
        ),
    )
    scoring = _score_narration_faithfulness(
        trajectory,
        faithfulness_check_fn=_ObservedFaithfulnessCheck(),
        handoff_leaves=frozenset({"export"}),
    )

    blocking_by_step = {check.step: check.blocking for check in scoring.checks}
    assert blocking_by_step == {_CALCULATE: False, _EXPORT: True}
