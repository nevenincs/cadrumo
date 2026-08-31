"""Cross-frontend parity: scripted, line, and full-screen agree by construction.

The substrate's contract is that every frontend is a thin projection over
one pure engine, so the same logical answer sequence must produce the
same :class:`FlowState` answers and the same submit verdict on all three
surfaces. This module drives one shared :class:`FlowDefinition` through
each of the three real frontends and asserts they converge:

* the scripted driver (:func:`run_scripted_flow`) over a canonical token
  queue;
* the line-mode frontend (:class:`LineFlowFrontend`) over real
  ``prompt_toolkit`` pipe keystrokes into an in-memory output;
* the full-screen :class:`FlowScreen` over Textual's headless ``Pilot``.

No frontend is mocked and no engine transition is stubbed: the scripted
and line runs execute synchronously (each managing its own prompt event
loop), and the Textual run is driven under ``asyncio.run`` so the three
event-loop lifetimes never nest. Assertions read structural engine state
(``FlowState.answers``, the review projection's eligibility and answered
count) and validation message *keys*, never localized prose. Page copy
resolves against a real bundled locale key so the render-time assembler
runs for real on every asked page across all three surfaces.
"""

from __future__ import annotations

import asyncio
from io import StringIO

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput
from pydantic import BaseModel
from textual.containers import Vertical

from ....application.flows.copy import assemble_section_titles
from ....application.flows.definition import CopyRef, FlowChoice, FlowCondition, FlowDefinition, FlowPage, FlowSection
from ....application.flows.engine import FlowState, answer, start_flow
from ....application.flows.errors import FlowAnswerError
from ....application.flows.line_frontend import LineFlowFrontend
from ....application.flows.review import ReviewProjection
from ....application.flows.scripted import run_scripted_flow
from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ....core.i18n._render import tr
from ....entrypoints.tui.components.host import ScreenHostApp
from ....entrypoints.tui.flows.app import FlowScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)
"""Wide enough that every question-page zone is on-screen, so a Pilot
click resolves to the button it names rather than to whatever the 80x24
default left visible."""

# The one shared answer sequence, expressed once as the canonical committed
# tokens every frontend must converge on. text, integer, a chosen SELECT
# value that opens the gated dependent, a confirmed flag, then the revealed
# dependent's text.
_EXPECTED_ANSWERS: dict[str, str] = {
    "p_text": "ada",
    "p_int": "42",
    "p_choice": "alpha",
    "p_flag": "true",
    "p_dep": "detail",
}
_ANSWERED_COUNT = len(_EXPECTED_ANSWERS)


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


def _copy(ref: str = "wizard.setup.title") -> CopyRef:
    # A real bundled locale key so the render-time copy assembler resolves
    # identically under every frontend without a locale-root override.
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _choice(value: str) -> FlowChoice:
    return FlowChoice(value=value, label=_copy())


def _definition() -> FlowDefinition:
    """One section carrying the five shared pages, in walk order.

    ``p_choice`` gates ``p_dep``: selecting ``alpha`` reveals the
    dependent, so every frontend walks an identical five-page sequence
    once the gate opens. Checkpointing is UNAVAILABLE in both modes, so
    no store is required and the save-and-exit affordance stays inert.
    """
    return FlowDefinition(
        id="flows.test.parity",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(id="p_text", widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str),
                    FlowPage(id="p_int", widget=FlowWidgetKind.INTEGER, prompt=_copy(), answer_type=int),
                    FlowPage(
                        id="p_choice",
                        widget=FlowWidgetKind.SELECT,
                        prompt=_copy(),
                        choices=(_choice("alpha"), _choice("beta"), _choice("gamma")),
                        answer_type=str,
                    ),
                    FlowPage(id="p_flag", widget=FlowWidgetKind.CONFIRM, prompt=_copy(), answer_type=bool),
                    FlowPage(
                        id="p_dep",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy(),
                        answer_type=str,
                        visible_when=FlowCondition(page_id="p_choice", equals="alpha"),
                    ),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _run_line(
    definition: FlowDefinition,
    keystrokes: str,
) -> tuple[FlowState, ReviewProjection, str]:
    """Drive the real line frontend over piped keystrokes, capturing output."""
    buffer = StringIO()
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)
        frontend = LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(buffer))
        state, projection = frontend.run(mode=FlowMode.MODIFY)
    return state, projection, buffer.getvalue()


async def _drive_tui_full_run(definition: FlowDefinition) -> tuple[FlowState | None, ReviewProjection | None]:
    """Answer every page through the full-screen widgets, then submit."""
    app = FlowScreen(definition, mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.press("enter")  # commit p_text, advance to p_int
        await pilot.pause()
        await pilot.press(*"42")
        await pilot.press("enter")  # commit p_int, advance to p_choice
        await pilot.pause()
        await pilot.press("1")  # choose the first numbered SELECT row (alpha), advance
        await pilot.pause()
        await pilot.press("enter")  # press the highlighted CONFIRM radio (true), advance
        await pilot.pause()
        await pilot.press(*"detail")
        await pilot.press("enter")  # commit p_dep (last page) -> auto review
        await pilot.pause()
        await pilot.click("#btn-submit")
        await pilot.pause()
    return app.final_state, app.final_projection


async def _drive_tui_invalid_integer(definition: FlowDefinition) -> str | None:
    """Feed a bad integer and return the verdict key the page holds in state."""
    app = FlowScreen(definition, mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.press("enter")  # commit p_text, advance to p_int
        await pilot.pause()
        await pilot.press(*"abc")
        await pilot.press("enter")  # invalid integer: the page holds and records the verdict
        await pilot.pause()
        verdicts = app.state.verdicts.get("p_int", ())
        assert verdicts, "the invalid integer must leave a blocking verdict on the page"
        assert app.state.cursor == "p_int", "an invalid commit must not advance the cursor"
        return verdicts[0].message_key


def test_three_frontends_converge_on_the_same_answers_and_submit_verdict() -> None:
    definition = _definition()

    scripted_state, scripted_projection = run_scripted_flow(
        definition,
        tuple(_EXPECTED_ANSWERS.values()),
        mode=FlowMode.MODIFY,
    )
    # CONFIRM auto-submits on the 'y' keypress (no trailing enter), so the
    # confirm token carries no '\r' of its own.
    line_state, line_projection, _captured = _run_line(definition, "ada\r42\r\rydetail\r\r")
    tui_state, tui_projection = asyncio.run(_drive_tui_full_run(definition))

    # (1) The three final answer maps are identical.
    assert dict(scripted_state.answers) == _EXPECTED_ANSWERS
    assert dict(line_state.answers) == _EXPECTED_ANSWERS
    assert tui_state is not None
    assert dict(tui_state.answers) == _EXPECTED_ANSWERS

    # (2) All three review projections report an eligible submit with the same
    # answered count, so the completeness gate agrees across surfaces.
    assert tui_projection is not None
    for projection in (scripted_projection, line_projection, tui_projection):
        assert projection.submit_eligible is True
        assert projection.answered_count == _ANSWERED_COUNT
        assert projection.required_remaining == 0


def test_three_frontends_report_the_same_invalid_token_verdict_key() -> None:
    definition = _definition()

    # The pure engine is the single validation authority every frontend calls;
    # derive the canonical invalid-integer verdict from it once.
    probe = answer(definition, start_flow(definition, mode=FlowMode.MODIFY), "p_int", "abc")
    invalid_verdict = probe.verdicts["p_int"][0]
    invalid_key = invalid_verdict.message_key
    assert invalid_key is not None

    # Scripted: an invalid token halts the walk and carries the rejecting
    # key(s) in the error context (never the raw answer).
    with pytest.raises(FlowAnswerError) as excinfo:
        run_scripted_flow(definition, ("ada", "abc"), mode=FlowMode.MODIFY)
    assert excinfo.value.context is not None
    scripted_keys = excinfo.value.context["message_keys"]

    # Full-screen: the page holds and records the verdict in engine state.
    tui_key = asyncio.run(_drive_tui_invalid_integer(definition))

    # Line: records the verdict then re-prompts in place; the bad-then-good
    # drive completes the flow, and the shared-engine verdict renders on the
    # captured surface (rendered-key resolution, not a hardcoded prose match).
    _state, _projection, captured = _run_line(definition, "ada\rabc\r42\r\rydetail\r\r")
    line_rendered_verdict = tr(invalid_key, **invalid_verdict.context)

    assert scripted_keys == (invalid_key,)
    assert tui_key == invalid_key
    assert line_rendered_verdict in captured


async def _tui_section_group_box_title(definition: FlowDefinition) -> str:
    """Read the question panel's group-box title on the first page."""
    app = FlowScreen(definition, mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        return str(host.screen.query_one("#page-body", Vertical).border_title)


def test_no_frontend_renders_a_section_slug_as_operator_facing_copy() -> None:
    """A section's group-box title and header are resolved copy, never its id.

    ``FlowSection.id`` is an internal slug and ``FlowSection.title`` is the
    reference carrying the operator-facing, locale-resolved title. Rendering
    the slug leaks an untranslated identifier into the interface — it stays
    fixed while the rest of the surface follows the profile language. This
    pins both surfaces that show a section outside review: the full-screen
    question panel's group-box border title, and the line-mode page header.
    """
    definition = _definition()
    resolved = assemble_section_titles(definition)["s1"]

    # Precondition: the fixture can actually distinguish the two. A section
    # whose resolved title happened to equal its slug would make every
    # assertion below pass vacuously.
    assert resolved != "s1", "fixture cannot detect the defect: resolved title equals the slug"

    group_box_title = asyncio.run(_tui_section_group_box_title(definition))
    assert group_box_title == resolved
    assert group_box_title != "s1"

    # On the opening page the gated ``p_dep`` is not yet visible, so the
    # sequence the header counts against is four pages, not five.
    _state, _projection, captured = _run_line(definition, "ada\r42\r1\r\rdetail\r\r")
    assert tr("flows.progress.page_header", position=1, total=4, section=resolved) in captured
    assert tr("flows.progress.page_header", position=1, total=4, section="s1") not in captured
