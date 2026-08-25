"""Real navigation and transition scenarios through the flow engine.

Every test drives the pure engine through its defining module (enums from
``cadrumo.core.flows``)
and asserts against ``PageStatus`` members and structural state, never
localized prose. The scenarios cover navigation and cursor tracking,
answer commit and canonicalisation, the two load-bearing invariants
(staleness-not-deletion on a gating change, deferral never resolving
silently), repeating-group instance expansion and shrink, section-exit
gating across a boundary, and the review submit gate.

The section-exit scenario needs a registered cross-field validator. The
validator registries are process-global and reject duplicate ids, so the
validator is registered exactly once at module import under a
``test.engine.`` id.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from ....core.flows import (
    DEFER_TOKEN,
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
    PageStatus,
)
from ..definition import CopyRef, FlowChoice, FlowCondition, FlowDefinition, FlowPage, FlowRepeatingGroup, FlowSection
from ..engine import (
    SECTION_VERDICT_PREFIX,
    FlowState,
    answer,
    back_page,
    jump_to,
    next_page,
    page_status,
    reset_page,
    restart_flow,
    set_instance_count,
    start_flow,
    visible_sequence,
)
from ..errors import FlowNavigationError, FlowSubmitError
from ..review import ReviewProjection, assert_submit_eligible, review
from ..validators import ValidationVerdict, register_cross_field_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SECTION_EXIT_VALIDATOR_ID = "test.engine.section_exit"


def _section_exit(answers: Mapping[str, str]) -> tuple[ValidationVerdict, ...]:
    """Pass once page ``p_a`` carries a non-blank answer; fail otherwise."""
    if answers.get("p_a", "").strip():
        return (ValidationVerdict.passed(),)
    return (ValidationVerdict.failed("test.engine.section_incomplete"),)


register_cross_field_validator(_SECTION_EXIT_VALIDATOR_ID, _section_exit)


class _Answers(BaseModel):
    """Trivial answers model; only the type identity is consumed."""


_FULL_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


def _copy(ref: str = "flows.test.copy") -> CopyRef:
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


def _choice(value: str, *, provenance: CopyRef | None = None) -> FlowChoice:
    return FlowChoice(value=value, label=_copy(), provenance=provenance)


def _definition(sections: tuple[FlowSection, ...]) -> FlowDefinition:
    return FlowDefinition(
        id="flows.test.flow",
        title=_copy(),
        description=_copy(),
        sections=sections,
        answers_model=_Answers,
        checkpoint=dict(_FULL_CHECKPOINT),
    )


def _visible_keys(definition: FlowDefinition, state: FlowState) -> list[str]:
    return [entry.key for entry in visible_sequence(definition, state)]  # type: ignore[arg-type]


# ── Navigation flow: gated dependent, canonicalising widgets ─────────────────
def _nav_definition() -> FlowDefinition:
    return _definition(
        (
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    _page("p_name"),
                    _page("p_kind", widget=FlowWidgetKind.SELECT, choices=(_choice("alpha"), _choice("beta"))),
                    _page(
                        "p_detail",
                        visible_when=FlowCondition(page_id="p_kind", equals="alpha"),
                    ),
                    _page("p_confirm", widget=FlowWidgetKind.CONFIRM, answer_type=bool, required=False),
                    _page(
                        "p_tags",
                        widget=FlowWidgetKind.CHECKBOX,
                        choices=(_choice("x"), _choice("y"), _choice("z")),
                        required=False,
                    ),
                    _page("p_num", widget=FlowWidgetKind.INTEGER, answer_type=int, required=False),
                ),
            ),
        ),
    )


def test_start_places_cursor_on_first_visible_page() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    assert state.cursor == "p_name"
    assert state.visited == ("p_name",)
    # The gated dependent is hidden until its parent selects 'alpha'.
    assert "p_detail" not in _visible_keys(definition, state)


def test_next_back_and_boundary_stops_track_the_cursor() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = next_page(definition, state)
    assert state.cursor == "p_kind"
    state = next_page(definition, state)
    assert state.cursor == "p_confirm"  # p_detail hidden, skipped
    assert state.visited[-3:] == ("p_name", "p_kind", "p_confirm")

    back = back_page(definition, state)
    assert back.cursor == "p_kind"

    # Walk to the final page; next_page at the end is a no-op.
    walked = state
    for _ in range(10):
        walked = next_page(definition, walked)
    assert walked.cursor == "p_num"
    assert next_page(definition, walked).cursor == "p_num"

    # back_page at the first page is a no-op.
    first = start_flow(definition, mode=FlowMode.CREATE)
    assert back_page(definition, first).cursor == "p_name"


def test_jump_to_visible_page_and_refusal_on_hidden_target() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    jumped = jump_to(definition, state, "p_num")
    assert jumped.cursor == "p_num"

    # p_detail is not currently visible (p_kind unanswered) -> refusal.
    with pytest.raises(FlowNavigationError):
        jump_to(definition, state, "p_detail")


def test_answer_commit_canonicalises_confirm_checkbox_and_integer() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = answer(definition, state, "p_confirm", "yes")
    assert state.answers["p_confirm"] == "true"
    assert page_status(state, "p_confirm") is PageStatus.ANSWERED

    state = answer(definition, state, "p_tags", "z, x")
    assert state.answers["p_tags"] == "x,z"

    state = answer(definition, state, "p_num", "007")
    assert state.answers["p_num"] == "7"


def test_failing_validation_leaves_prior_answer_and_records_verdicts() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = answer(definition, state, "p_kind", "alpha")
    assert state.answers["p_kind"] == "alpha"

    rejected = answer(definition, state, "p_kind", "zzz")
    assert rejected.answers["p_kind"] == "alpha"  # prior answer retained
    assert "p_kind" in rejected.verdicts
    assert page_status(rejected, "p_kind") is PageStatus.INVALID


def test_changing_a_gating_answer_marks_dependent_stale_and_review_lists_it() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = answer(definition, state, "p_kind", "alpha")
    assert "p_detail" in _visible_keys(definition, state)
    state = answer(definition, state, "p_detail", "some detail")
    assert page_status(state, "p_detail") is PageStatus.ANSWERED

    # Flip the gate: the dependent leaves visibility but is preserved as stale.
    state = answer(definition, state, "p_kind", "beta")
    assert "p_detail" in state.stale
    assert "p_detail" not in _visible_keys(definition, state)

    projection = review(definition, state)
    stale_rows = [row for row in projection.rows if row.key == "p_detail"]
    assert len(stale_rows) == 1
    assert stale_rows[0].status is PageStatus.STALE
    assert stale_rows[0].jumpable is False
    assert not projection.submit_eligible
    assert any(verdict.message_key == "flows.review.page_stale" for verdict in projection.blocking)


def test_reset_clears_one_answer_and_marks_dependents_stale() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p_kind", "alpha")
    state = answer(definition, state, "p_detail", "d")

    state = reset_page(definition, state, "p_kind")
    assert "p_kind" not in state.answers
    assert "p_detail" in state.stale


def test_restart_wipes_state() -> None:
    definition = _nav_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p_kind", "alpha")
    state = answer(definition, state, "p_detail", "d")
    state = next_page(definition, state)

    restarted = restart_flow(definition, state)
    assert restarted.answers == {}
    assert restarted.stale == frozenset()
    assert restarted.cursor == "p_name"
    assert restarted.visited == ("p_name",)


# ── Repeating groups ─────────────────────────────────────────────────────────
def _repeat_definition() -> FlowDefinition:
    return _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(
                    _page("p_count", widget=FlowWidgetKind.INTEGER, answer_type=int),
                    FlowRepeatingGroup(
                        id="grp",
                        title=_copy(),
                        count_from="p_count",
                        pages=(_page("g_a"),),
                    ),
                ),
            ),
        ),
    )


def test_count_answer_expands_instances_keyed_by_group_index_page() -> None:
    definition = _repeat_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = answer(definition, state, "p_count", "2")
    assert state.instance_counts["grp"] == 2
    assert _visible_keys(definition, state) == ["p_count", "grp#0.g_a", "grp#1.g_a"]

    state = answer(definition, state, "grp#0.g_a", "first")
    assert state.answers["grp#0.g_a"] == "first"
    assert page_status(state, "grp#0.g_a") is PageStatus.ANSWERED


def test_shrinking_count_marks_orphaned_instance_answers_stale() -> None:
    definition = _repeat_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p_count", "2")
    state = answer(definition, state, "grp#0.g_a", "a")
    state = answer(definition, state, "grp#1.g_a", "b")

    state = answer(definition, state, "p_count", "1")
    assert state.instance_counts["grp"] == 1
    assert "grp#1.g_a" in state.stale
    assert "grp#0.g_a" not in state.stale


def test_set_instance_count_grows_and_shrinks_from_review() -> None:
    definition = _repeat_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p_count", "1")

    grown = set_instance_count(definition, state, "grp", 3)
    assert grown.instance_counts["grp"] == 3
    assert _visible_keys(definition, grown) == ["p_count", "grp#0.g_a", "grp#1.g_a", "grp#2.g_a"]

    grown = answer(definition, grown, "grp#0.g_a", "a")
    grown = answer(definition, grown, "grp#1.g_a", "b")
    grown = answer(definition, grown, "grp#2.g_a", "c")

    shrunk = set_instance_count(definition, grown, "grp", 1)
    assert shrunk.instance_counts["grp"] == 1
    assert {"grp#1.g_a", "grp#2.g_a"} <= shrunk.stale
    assert "grp#0.g_a" not in shrunk.stale


def test_set_instance_count_refuses_unknown_group() -> None:
    definition = _repeat_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    with pytest.raises(FlowNavigationError):
        set_instance_count(definition, state, "no_such_group", 2)


# ── Compare-select deferral ──────────────────────────────────────────────────
def _compare_definition() -> FlowDefinition:
    return _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(
                    _page(
                        "p_cmp",
                        widget=FlowWidgetKind.COMPARE_SELECT,
                        choices=(
                            _choice("cand_a", provenance=_copy("prov.a")),
                            _choice("cand_b", provenance=_copy("prov.b")),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_compare_select_defer_marks_deferred_and_blocks_submission() -> None:
    definition = _compare_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    state = answer(definition, state, "p_cmp", DEFER_TOKEN)
    assert state.answers["p_cmp"] == DEFER_TOKEN
    assert page_status(state, "p_cmp") is PageStatus.DEFERRED

    projection = review(definition, state)
    assert not projection.submit_eligible
    assert any(verdict.message_key == "flows.review.page_deferred" for verdict in projection.blocking)
    with pytest.raises(FlowSubmitError):
        assert_submit_eligible(definition, state)

    # Resolving the deferral to a real candidate clears the block.
    resolved = answer(definition, state, "p_cmp", "cand_a")
    assert page_status(resolved, "p_cmp") is PageStatus.ANSWERED
    assert review(definition, resolved).submit_eligible


# ── Section-exit gating across a section boundary ────────────────────────────
def _section_exit_definition() -> FlowDefinition:
    return _definition(
        (
            FlowSection(
                id="s_a",
                title=_copy(),
                items=(_page("p_a"),),
                exit_validator_ids=(_SECTION_EXIT_VALIDATOR_ID,),
            ),
            FlowSection(
                id="s_b",
                title=_copy(),
                items=(_page("p_b", required=False),),
            ),
        ),
    )


def test_section_exit_validator_blocks_boundary_then_clears_after_fix() -> None:
    definition = _section_exit_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    assert state.cursor == "p_a"

    # p_a unanswered -> crossing into s_b runs the exit validator, which fails.
    blocked = next_page(definition, state)
    assert blocked.cursor == "p_a"  # cursor held at the boundary
    section_key = f"{SECTION_VERDICT_PREFIX}s_a"
    assert section_key in blocked.verdicts

    # Answer p_a; the boundary now clears and the cursor advances.
    fixed = answer(definition, blocked, "p_a", "present")
    advanced = next_page(definition, fixed)
    assert advanced.cursor == "p_b"
    assert section_key not in advanced.verdicts


# ── Submit gate ──────────────────────────────────────────────────────────────
def _submit_definition() -> FlowDefinition:
    return _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_only"),)),),
    )


def test_submit_gate_refuses_until_required_pages_are_answered() -> None:
    definition = _submit_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)

    with pytest.raises(FlowSubmitError):
        assert_submit_eligible(definition, state)

    answered = answer(definition, state, "p_only", "value")
    projection = assert_submit_eligible(definition, answered)
    assert projection.submit_eligible
    assert projection.required_remaining == 0


def test_review_projection_refuses_contradictory_derived_state() -> None:
    """Direct construction cannot contradict the review rows or their failures."""
    definition = _submit_definition()
    projection = review(definition, start_flow(definition, mode=FlowMode.CREATE))
    document: dict[str, Any] = dict(projection.model_dump())

    with pytest.raises(ValidationError, match="answered_count"):
        ReviewProjection.model_validate({**document, "answered_count": 1})
    with pytest.raises(ValidationError, match="required_remaining"):
        ReviewProjection.model_validate({**document, "required_remaining": 0})
    with pytest.raises(ValidationError, match="blocking verdicts"):
        ReviewProjection.model_validate({**document, "blocking": ()})
    with pytest.raises(ValidationError, match="submit_eligible"):
        ReviewProjection.model_validate({**document, "submit_eligible": True})
    with pytest.raises(ValidationError, match="flow_verdicts"):
        ReviewProjection.model_validate({**document, "flow_verdicts": (ValidationVerdict.passed(),)})


def test_review_projection_preserves_flow_verdict_refusal_precedence() -> None:
    """The first validator stage remains the flow-verdict coherence guard."""
    definition = _submit_definition()
    projection = review(definition, start_flow(definition, mode=FlowMode.CREATE))
    document: dict[str, Any] = dict(projection.model_dump())

    with pytest.raises(ValidationError, match="flow_verdicts"):
        ReviewProjection.model_validate(
            {
                **document,
                "flow_verdicts": (ValidationVerdict.passed(),),
                "answered_count": 1,
                "required_remaining": 0,
                "blocking": (),
                "submit_eligible": True,
            },
        )


def test_derived_review_projection_round_trips() -> None:
    """A production-derived complete review remains valid through JSON round-trip."""
    definition = _submit_definition()
    state = answer(definition, start_flow(definition, mode=FlowMode.CREATE), "p_only", "value")
    projection = review(definition, state)

    assert ReviewProjection.model_validate_json(projection.model_dump_json()) == projection
