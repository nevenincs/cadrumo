"""Headless drive of the line-mode frontend over the real engine.

Every scenario drives ``LineFlowFrontend.run`` through its canonical defining
module, feeding real keystrokes over
``prompt_toolkit.input.create_pipe_input`` and capturing output in an
in-memory ``PlainTextOutput`` — the same headless pipe-input contract the
retired one-shot prompter's smoke test used. No prompt is mocked: the
frontend runs its real questionary primitives against the piped bytes.

The cases cover a full run to submit across two sections; in-place
re-prompt on a failing verdict; the review edit-by-number path re-asking a
page; confirmed restart wiping answers; save-and-exit persisting through a
real in-memory ``CheckpointStore`` implementation and returning an
un-submitted state; the fail-fast refusal when a mode declares
checkpointing available but no store was injected; the stale-orphan
recovery that resets an orphaned answer from review to unblock submission;
and the non-TTY console refusal.

Assertions read structural state (``FlowState.answers``, ``stale``,
submit-eligibility) and error message *keys*, never localized prose. The
page copy references resolve against a real bundled locale key so the
render-time assembler runs for real on every asked page.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput
from pydantic import BaseModel

from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ....core.i18n import tr
from .. import (
    CopyRef,
    FlowCheckpointError,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowLegalRef,
    FlowPage,
    FlowRunAbandonedError,
    FlowSection,
    FlowState,
    FlowUnsupportedConsoleError,
    ReviewProjection,
    answer,
    assemble_section_titles,
    start_flow,
)
from ..line_frontend import LineFlowFrontend

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Down-arrow escape sequence: moves the questionary select highlight down
# one row. ``\r`` selects the highlighted row.
_DOWN = "\x1b[B"

_FULL_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


class _MemoryCheckpointStore:
    """A real in-memory :class:`CheckpointStore` — it genuinely persists.

    This is a true port implementation, not a test double: ``save``
    stores the answer map, ``load`` returns it, ``discard`` erases it.
    It satisfies the runtime-checkable ``CheckpointStore`` Protocol.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

    def save(self, flow_id: str, answers: Mapping[str, str]) -> None:
        self._data[flow_id] = dict(answers)

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        return self._data.get(flow_id)

    def discard(self, flow_id: str) -> None:
        self._data.pop(flow_id, None)


def _copy(ref: str = "wizard.setup.title") -> CopyRef:
    # A real bundled locale key so the render-time copy assembler resolves.
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
        id="flows.test.line",
        title=_copy(),
        description=_copy(),
        sections=sections,
        answers_model=_Answers,
        checkpoint=dict(_FULL_CHECKPOINT),
    )


def _memory_output() -> PlainTextOutput:
    return PlainTextOutput(StringIO())


def _run(
    definition: FlowDefinition,
    keystrokes: str,
    *,
    mode: FlowMode,
    resume_state: FlowState | None = None,
    store: _MemoryCheckpointStore | None = None,
) -> tuple[FlowState, ReviewProjection]:
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)
        frontend = LineFlowFrontend(
            definition,
            input=pipe,
            output=_memory_output(),
            checkpoint_store=store,
        )
        return frontend.run(mode=mode, resume_state=resume_state)


def _two_section_flow() -> FlowDefinition:
    return _definition(
        (
            FlowSection(id="s1", title=_copy(), items=(_page("p_a"),)),
            FlowSection(id="s2", title=_copy(), items=(_page("p_b"),)),
        ),
    )


def test_full_run_submits_across_two_sections() -> None:
    definition = _two_section_flow()
    # Two text answers, then the highlighted 'submit' action.
    state, projection = _run(definition, "alpha\rbeta\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_a": "alpha", "p_b": "beta"}
    assert projection.submit_eligible
    assert projection.required_remaining == 0


def test_failing_verdict_reprompts_in_place_then_accepts_valid() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_num", widget=FlowWidgetKind.INTEGER, answer_type=int),)),),
    )
    # 'abc' fails the integer shape and re-prompts in place; '42' commits.
    state, projection = _run(definition, "abc\r42\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_num": "42"}
    assert projection.submit_eligible


def test_date_failing_verdict_reprompts_in_place_then_accepts_valid() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_date", widget=FlowWidgetKind.DATE),)),),
    )
    # A non-ISO date fails the shape and re-prompts in place; the ISO form commits.
    state, projection = _run(definition, "2026-13-01\r2026-01-05\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_date": "2026-01-05"}
    assert projection.submit_eligible


def test_decimal_failing_verdict_reprompts_in_place_then_accepts_valid() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_amount", widget=FlowWidgetKind.DECIMAL),)),),
    )
    # A comma-separated amount fails the shape and re-prompts; the dot form commits.
    state, projection = _run(definition, "1,5\r1.50\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_amount": "1.50"}
    assert projection.submit_eligible


def test_review_edit_by_number_reasks_a_page() -> None:
    definition = _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(_page("p_a", widget=FlowWidgetKind.SELECT, choices=(_choice("alpha"), _choice("beta"))),),
            ),
        ),
    )
    # walk selects 'alpha'; review -> edit (down+enter) -> '1' -> re-select
    # 'beta' (down+enter) -> submit.
    state, _ = _run(definition, f"\r{_DOWN}\r1\r{_DOWN}\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_a": "beta"}


def test_confirmed_restart_wipes_answers_and_reasks() -> None:
    definition = _definition((FlowSection(id="s", title=_copy(), items=(_page("p_a"),)),))
    # answer 'first'; review -> restart (down x2 + enter) -> confirm 'y';
    # re-answer 'second'; review -> submit.
    state, projection = _run(definition, f"first\r{_DOWN}{_DOWN}\ry\rsecond\r\r", mode=FlowMode.MODIFY)

    assert dict(state.answers) == {"p_a": "second"}
    assert projection.submit_eligible


def test_save_and_exit_persists_through_the_store_and_returns_unsubmitted() -> None:
    definition = _definition((FlowSection(id="s", title=_copy(), items=(_page("p_a"),)),))
    store = _MemoryCheckpointStore()
    # answer 'saved'; review -> save-and-exit (down x2 + enter). CREATE mode
    # declares checkpointing available, so the store-backed save runs.
    state, _ = _run(
        definition,
        f"saved\r{_DOWN}{_DOWN}\r",
        mode=FlowMode.CREATE,
        store=store,
    )

    assert store.load("flows.test.line") == {"p_a": "saved"}
    assert dict(state.answers) == {"p_a": "saved"}


def test_available_checkpoint_mode_without_store_fails_fast_at_run_start() -> None:
    definition = _definition((FlowSection(id="s", title=_copy(), items=(_page("p_a"),)),))
    # CREATE declares checkpointing available; no store injected -> refuse
    # before any progress, so a mis-wired frontend never offers a save it
    # cannot perform.
    with pytest.raises(FlowCheckpointError) as excinfo:
        _run(definition, "", mode=FlowMode.CREATE)

    assert excinfo.value.translated_message == "flows.errors.checkpoint_store_missing"


def test_stale_orphan_reset_from_review_unblocks_submission() -> None:
    definition = _definition(
        (
            FlowSection(
                id="s",
                title=_copy(),
                items=(
                    _page("p_gate", widget=FlowWidgetKind.SELECT, choices=(_choice("alpha"), _choice("beta"))),
                    _page("p_dep", visible_when=FlowCondition(page_id="p_gate", equals="alpha")),
                ),
            ),
        ),
    )
    # Build a state where flipping the gate orphaned an answered dependent:
    # p_dep is stale and no longer visible.
    stale = start_flow(definition, mode=FlowMode.MODIFY)
    stale = answer(definition, stale, "p_gate", "alpha")
    stale = answer(definition, stale, "p_dep", "detail")
    stale = answer(definition, stale, "p_gate", "beta")
    assert "p_dep" in stale.stale

    # Resume into review: not submit-eligible, so 'edit' is highlighted.
    # Edit row 2 (the non-jumpable stale orphan), confirm the reset, submit.
    state, projection = _run(
        definition,
        "\r2\ry\r\r",
        mode=FlowMode.MODIFY,
        resume_state=stale,
    )

    assert "p_dep" not in state.stale
    assert "p_dep" not in state.answers
    assert state.answers["p_gate"] == "beta"
    assert projection.submit_eligible


def test_secret_answer_is_masked_in_the_reprompt_header_and_never_captured() -> None:
    # One required SECRET page. Answer it, then from review edit it (submit is
    # highlighted first, so one down selects 'edit'), pick row 1, and re-enter
    # it: the re-ask renders the page header, whose current-answer line is the
    # only place a committed value could reach the terminal. Masking must emit
    # a fixed marker there, so the raw secret never appears in captured output
    # even though it lives in the engine state.
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_secret", widget=FlowWidgetKind.SECRET),)),),
    )
    buffer = StringIO()
    with create_pipe_input() as pipe:
        pipe.send_text(f"hunter2\r{_DOWN}\r1\rhunter2\r\r")
        frontend = LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(buffer))
        state, _ = frontend.run(mode=FlowMode.MODIFY)

    captured = buffer.getvalue()
    assert state.answers["p_secret"] == "hunter2"  # noqa: S105 - test fixture secret, not a credential
    # Pair the assertion: prove the header actually re-rendered the answered
    # page (its position marker present) AND that the current-answer line
    # rendered the masked marker, THEN assert the raw secret is absent — an
    # absence check against an empty or wrong capture would pass vacuously.
    # The header carries the section's RESOLVED title, never its internal
    # slug ("s"), so this control is written against the same resolution the
    # frontend performs.
    assert (
        tr(
            "flows.progress.page_header",
            position=1,
            total=1,
            section=assemble_section_titles(definition)["s"],
        )
        in captured
    )
    assert tr("flows.progress.current_answer_secret") in captured
    assert "hunter2" not in captured


def test_ctrl_c_on_a_required_prompt_raises_a_typed_abandonment() -> None:
    # A required page with no cancel path would re-prompt forever on a blank;
    # unsafe_ask surfaces the Ctrl-C as a KeyboardInterrupt that the frontend
    # boundary maps to a typed, translated abandonment instead of swallowing
    # it into a silent re-prompt.
    definition = _definition((FlowSection(id="s", title=_copy(), items=(_page("p_a"),)),))
    with create_pipe_input() as pipe:
        pipe.send_text("\x03")  # Ctrl-C
        frontend = LineFlowFrontend(definition, input=pipe, output=_memory_output())
        with pytest.raises(FlowRunAbandonedError) as excinfo:
            frontend.run(mode=FlowMode.MODIFY)

    assert excinfo.value.translated_message == "errors.refused.refused_flow_run_abandoned"


def test_legal_zone_renders_one_line_per_citation() -> None:
    # A labelled citation renders through the tr frame; a citation with no
    # label passes its ref token through verbatim.
    page = FlowPage(
        id="p_a",
        widget=FlowWidgetKind.TEXT,
        prompt=_copy(),
        legal_zone=(
            FlowLegalRef(ref="ley-35-2006:art-27", label=_copy()),
            FlowLegalRef(ref="ley-35-2006:art-28"),
        ),
        answer_type=str,
        required=False,
    )
    definition = _definition((FlowSection(id="s", title=_copy(), items=(page,)),))
    buffer = StringIO()
    with create_pipe_input() as pipe:
        pipe.send_text("value\r\r")  # answer the page, then submit from review
        frontend = LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(buffer))
        frontend.run(mode=FlowMode.MODIFY)

    captured = buffer.getvalue()
    resolved_label = tr("wizard.setup.title")
    assert tr("flows.progress.legal_ref", ref="ley-35-2006:art-27", label=resolved_label) in captured
    assert "ley-35-2006:art-28" in captured


def test_on_answer_committed_fires_per_successful_commit_with_key_and_value() -> None:
    definition = _two_section_flow()
    received: list[tuple[str, str]] = []
    with create_pipe_input() as pipe:
        pipe.send_text("alpha\rbeta\r\r")
        frontend = LineFlowFrontend(
            definition,
            input=pipe,
            output=_memory_output(),
            on_answer_committed=lambda key, value: received.append((key, value)),
        )
        frontend.run(mode=FlowMode.MODIFY)

    # One notification per successful commit, carrying the page key and the
    # canonical committed value, in walk order.
    assert received == [("p_a", "alpha"), ("p_b", "beta")]


def test_on_answer_committed_does_not_fire_on_a_failing_verdict() -> None:
    definition = _definition(
        (FlowSection(id="s", title=_copy(), items=(_page("p_num", widget=FlowWidgetKind.INTEGER, answer_type=int),)),),
    )
    received: list[tuple[str, str]] = []
    with create_pipe_input() as pipe:
        # 'abc' fails the integer shape (no notification); '42' commits (one).
        pipe.send_text("abc\r42\r\r")
        frontend = LineFlowFrontend(
            definition,
            input=pipe,
            output=_memory_output(),
            on_answer_committed=lambda key, value: received.append((key, value)),
        )
        frontend.run(mode=FlowMode.MODIFY)

    assert received == [("p_num", "42")]


def test_uninjected_frontend_refuses_non_tty_console() -> None:
    # pytest captures stdio, so the test process is non-TTY. A frontend with
    # no injected IO must refuse from the environment probe directly.
    assert not sys.stdin.isatty()
    definition = _definition((FlowSection(id="s", title=_copy(), items=(_page("p_a"),)),))

    with pytest.raises(FlowUnsupportedConsoleError) as excinfo:
        LineFlowFrontend(definition).ensure_interactive_environment()

    assert excinfo.value.translated_message == "flows.errors.unsupported_console"
