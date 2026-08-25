"""Checkpoint save/refuse and resume-projection over the real engine.

Every scenario drives the checkpoint port and the resume projection
through the defining checkpoint and resume modules against a real
in-memory ``CheckpointStore`` implementation — a genuine port that stores
and returns the answer map, never a mock.

The cases cover a save round-trip; the declared no-op arm refusing to save
(carrying counts only, never answer values); the ``checkpoint_available``
truth table; and the resume projection: valid persisted answers commit and
gates reveal their dependents to a fixed point, an answer the current
definition rejects lands stale rather than committed, an orphaned key for a
page the definition no longer declares lands stale, a repeating-group count
answer reseeds ``instance_counts``, the cursor lands on the first
unanswered visible page, and no diagnostic ever carries an answer value.

Assertions read structural state and ``PageStatus`` members, never
localized prose.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import BaseModel

from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
    PageStatus,
)
from ..checkpoint import checkpoint_available, save_checkpoint
from ..definition import CopyRef, FlowChoice, FlowCondition, FlowDefinition, FlowPage, FlowRepeatingGroup, FlowSection
from ..engine import answer, page_status, start_flow
from ..errors import FlowCheckpointError
from ..resume import resume_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FULL_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


class _MemoryCheckpointStore:
    """A real in-memory :class:`CheckpointStore`; it genuinely persists."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    def save(self, flow_id: str, answers: Mapping[str, str]) -> None:
        self._data[flow_id] = dict(answers)

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        return self._data.get(flow_id)

    def discard(self, flow_id: str) -> None:
        self._data.pop(flow_id, None)


def _copy(ref: str = "wizard.setup.title") -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _page(
    page_id: str,
    *,
    widget: FlowWidgetKind = FlowWidgetKind.TEXT,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
    choices: tuple[FlowChoice, ...] = (),
    visible_when: FlowCondition | None = None,
    required: bool = True,
) -> FlowPage:
    return FlowPage(
        id=page_id,
        widget=widget,
        prompt=_copy(),
        choices=choices,
        visible_when=visible_when,
        required=required,
        answer_type=answer_type,
    )


def _choice(value: str) -> FlowChoice:
    return FlowChoice(value=value, label=_copy())


def _definition(sections: tuple[FlowSection, ...]) -> FlowDefinition:
    return FlowDefinition(
        id="flows.test.checkpoint",
        title=_copy(),
        description=_copy(),
        sections=sections,
        answers_model=_Answers,
        checkpoint=dict(_FULL_CHECKPOINT),
    )


def _gated_flow() -> FlowDefinition:
    return _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(
                    _page("p_gate", widget=FlowWidgetKind.SELECT, choices=(_choice("alpha"), _choice("beta"))),
                    _page("p_dep", visible_when=FlowCondition(page_id="p_gate", equals="alpha")),
                    _page("p_last", required=False),
                ),
            ),
        ),
    )


def test_save_checkpoint_round_trips_through_the_store() -> None:
    definition = _gated_flow()
    store = _MemoryCheckpointStore()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p_gate", "alpha")
    state = answer(definition, state, "p_dep", "detail")

    save_checkpoint(definition, state, store)

    assert store.load("flows.test.checkpoint") == {"p_gate": "alpha", "p_dep": "detail"}


def test_no_op_mode_refuses_save_with_counts_only() -> None:
    definition = _gated_flow()
    store = _MemoryCheckpointStore()
    # MODIFY declares checkpointing UNAVAILABLE: save must refuse.
    state = start_flow(definition, mode=FlowMode.MODIFY)
    state = answer(definition, state, "p_gate", "alpha")
    state = answer(definition, state, "p_dep", "SENSITIVE-ANSWER-VALUE")

    with pytest.raises(FlowCheckpointError) as excinfo:
        save_checkpoint(definition, state, store)

    error = excinfo.value
    assert error.translated_message == "application.flows.errors.checkpoint_unavailable_mode"
    # Counts only; no answer value anywhere in the diagnostic context.
    context = error.context
    assert context is not None
    assert context["answered_count"] == 2
    assert not any("SENSITIVE-ANSWER-VALUE" in str(value) for value in context.values())
    # And nothing was persisted through the refusal.
    assert store.load("flows.test.checkpoint") is None


def test_checkpoint_available_truth_table() -> None:
    definition = _gated_flow()
    assert checkpoint_available(definition, FlowMode.CREATE) is True
    assert checkpoint_available(definition, FlowMode.MODIFY) is False


def test_resume_commits_valid_answers_and_reveals_dependents_to_fixed_point() -> None:
    definition = _gated_flow()
    # The persisted gate answer must reveal p_dep so its persisted answer
    # commits in the same fixed-point walk.
    state = resume_flow(definition, {"p_gate": "alpha", "p_dep": "detail"}, mode=FlowMode.CREATE)

    assert state.answers == {"p_gate": "alpha", "p_dep": "detail"}
    assert page_status(state, "p_dep") is PageStatus.ANSWERED
    assert state.stale == frozenset()


def test_resume_answer_rejected_by_definition_lands_stale_not_committed() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_num", widget=FlowWidgetKind.INTEGER, answer_type=int),)),),
    )
    state = resume_flow(definition, {"p_num": "not-an-integer"}, mode=FlowMode.CREATE)

    assert "p_num" not in state.answers
    assert "p_num" in state.stale


def test_resume_orphaned_key_lands_stale() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_num", widget=FlowWidgetKind.INTEGER, answer_type=int),)),),
    )
    # 'ghost' names no page the current definition declares.
    state = resume_flow(definition, {"p_num": "5", "ghost": "orphan-value"}, mode=FlowMode.CREATE)

    assert state.answers == {"p_num": "5"}
    assert "ghost" in state.stale


def test_resume_repeating_group_count_reseeds_instance_counts() -> None:
    definition = _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(
                    _page("p_count", widget=FlowWidgetKind.INTEGER, answer_type=int),
                    FlowRepeatingGroup(id="grp", title=_copy(), count_from="p_count", pages=(_page("g_a"),)),
                ),
            ),
        ),
    )
    state = resume_flow(
        definition,
        {"p_count": "2", "grp#0.g_a": "a", "grp#1.g_a": "b"},
        mode=FlowMode.CREATE,
    )

    assert state.instance_counts["grp"] == 2
    assert state.answers == {"p_count": "2", "grp#0.g_a": "a", "grp#1.g_a": "b"}


def test_resume_cursor_lands_on_first_unanswered_visible_page() -> None:
    definition = _gated_flow()
    # Only the gate is persisted; p_dep becomes visible and unanswered.
    state = resume_flow(definition, {"p_gate": "alpha"}, mode=FlowMode.CREATE)

    assert state.cursor == "p_dep"
