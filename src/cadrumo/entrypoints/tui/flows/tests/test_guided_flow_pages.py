"""Behavioural proofs for the guided-flow PAGES, not its stage indicator.

The sibling suite proves the stage strip: one stage per section, advancing on
the real engine cursor, and returning on back. That is the indicator. These
prove what an operator does -- the prompt they read, the answer they type, the
answer surviving a step backwards, and the appearance toggle resolving from
whatever surface is actually focused.

WHY THIS MODULE EXISTS SEPARATELY. The flow pages move from SIBLINGS on the
screen stack to DESCENDANTS the entry owns, which touches focus,
binding resolution, DOM ancestry and screen dismissal. Every one of those is
invisible to a stage-strip assertion, so the four tests beside this one would
stay green through a redesign that broke the flow entirely. The row's own
completion signal -- the appearance binding living on the entry, and
``SCOPED_CSS`` returning to default -- is structural and would also survive a
behavioural regression.

Each test below is therefore written to fail if the redesign mishandles the
thing it names, while asserting nothing about WHERE the page lives. They query
through ``app.screen``, the active surface, rather than naming FlowScreen or
QuestionScreen, so they hold across the change instead of pinning the shape the
change exists to remove.

See Also:
    :mod:`cadrumo.entrypoints.tui.flows.tests.test_guided_flows`
        The stage-strip proofs this complements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml
from pydantic import BaseModel
from textual.widgets import Input, Label, Static

from .....application.flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from .....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from .....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES
from .....tests.locales_root_fixture import locales_root_scope
from ...components.dialogs import ConfirmScreen
from ...components.host import ScreenHostApp
from ..app import FlowScreen

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)

_COPY_CATALOGUE: dict[str, object] = {
    "flows": {
        "guided": {
            "flow_title": "GUIDED-FLOW-TITLE",
            "section_one": "First stage",
            "section_two": "Second stage",
            "prompt_one": "PROMPT-ONE",
            "prompt_two": "PROMPT-TWO",
        },
        "tui": {
            "header": "{flow} / {position} / {total} / {section}",
            "header_single_section": "{flow} / {position} / {total}",
        },
        "review": {"header_tui_stage_label": "Review"},
        # Declared so the echo interpolates its value rather than falling back to
        # a humanised key: without these the zone renders "Current answer" and an
        # assertion on the typed text passes or fails for the wrong reason.
        "progress": {
            "current_answer": "Current answer {value}",
            "current_answer_secret": "Current answer hidden",
            "required": "REQUIRED-BADGE",
            "optional": "OPTIONAL-BADGE",
        },
    },
}


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


def _copy(ref: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


@pytest.fixture(autouse=True)
def _flow_copy_catalogue(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Resolve every declared ref against a fixture catalogue.

    Copy resolution refuses an unresolvable key rather than rendering blank, so
    a prompt assertion below proves the definition's own text reached the page
    rather than a fallback.
    """
    root = tmp_path_factory.mktemp("guided-flow-page-locales")
    payload = yaml.safe_dump(_COPY_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")
    with locales_root_scope(root):
        yield


def _two_text_page_definition() -> FlowDefinition:
    """Two sections of one TEXT page each.

    Both pages are TEXT so an answer can be typed, read back, and re-read after
    a step backwards -- a SELECT page cannot show that an entered value
    survived, because its value was never typed.
    """
    return FlowDefinition(
        id="flows.test.pages",
        title=_copy("flows.guided.flow_title"),
        description=_copy("flows.guided.flow_title"),
        sections=(
            FlowSection(
                id="s1",
                title=_copy("flows.guided.section_one"),
                items=(
                    FlowPage(
                        id="p1", widget=FlowWidgetKind.TEXT, prompt=_copy("flows.guided.prompt_one"), answer_type=str
                    ),
                ),
            ),
            FlowSection(
                id="s2",
                title=_copy("flows.guided.section_two"),
                items=(
                    FlowPage(
                        id="p2", widget=FlowWidgetKind.TEXT, prompt=_copy("flows.guided.prompt_two"), answer_type=str
                    ),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _host() -> ScreenHostApp[None]:
    return ScreenHostApp(FlowScreen(_two_text_page_definition(), mode=FlowMode.MODIFY))


def _prompt(host: ScreenHostApp[None]) -> str:
    """The prompt on the ACTIVE surface, whichever surface that is.

    Queried through ``app.screen`` rather than a named class so the assertion
    survives the pages becoming descendants of the entry.
    """
    return str(host.screen.query_one("#page-prompt", Label).render())


def _answer_input(host: ScreenHostApp[None]) -> Input:
    return host.screen.query_one("#widget-area").query_one(Input)


@pytest.mark.asyncio
async def test_the_page_renders_the_prompt_its_definition_declares() -> None:
    """The operator reads the definition's prompt, not a fallback or a blank."""
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE):
        assert "PROMPT-ONE" in _prompt(host)


@pytest.mark.asyncio
async def test_advancing_moves_to_the_next_page_and_renders_its_prompt() -> None:
    """Page-to-page navigation, which a stage-strip assertion cannot see.

    The strip can advance correctly while the page beneath it does not change,
    because the strip reads the engine cursor and the page reads the cursor's
    resolved item.
    """
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"first")
        await pilot.click("#btn-next")
        await pilot.pause()

        assert "PROMPT-TWO" in _prompt(host)


@pytest.mark.asyncio
async def test_an_answer_survives_a_step_backwards() -> None:
    """Going back must restore the answer, not an empty widget.

    This is the state assertion the redesign most endangers: when the pages stop
    being separate screens, whatever currently rebuilds a page on re-entry
    changes, and a page rebuilt from the definition rather than from the stored
    answer looks identical until an operator loses typed input.
    """
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"kept")
        await pilot.click("#btn-next")
        await pilot.pause()
        await pilot.click("#btn-back")
        await pilot.pause()

        assert "PROMPT-ONE" in _prompt(host)
        assert _answer_input(host).value == "kept"


@pytest.mark.asyncio
async def test_the_appearance_toggle_resolves_from_the_active_surface() -> None:
    """F3 must flip the appearance from wherever the operator actually is.

    This is that redesign's completion signal made behavioural. The binding is
    currently duplicated onto both page screens BECAUSE the entry is never the
    active surface; the redesign moves it to the entry alone. Asserting the
    EFFECT rather than the declaration means this test passes before and after,
    and fails if the move leaves the binding somewhere that never resolves.
    """
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        before = host.theme
        await pilot.press("f3")
        await pilot.pause()

        assert host.theme != before, "F3 did not reach an appearance action from the active surface"


def _numeric_definition() -> FlowDefinition:
    """One INTEGER-widget page.

    The widget kind is what matters, not `answer_type`: live validation calls
    `validate_widget_shape`, which judges the widget's own shape. A TEXT page
    annotated `answer_type=int` accepts letters happily and renders no refusal,
    which is how the first draft of this test passed nothing and proved nothing.
    """
    return FlowDefinition(
        id="flows.test.numeric",
        title=_copy("flows.guided.flow_title"),
        description=_copy("flows.guided.flow_title"),
        sections=(
            FlowSection(
                id="s1",
                title=_copy("flows.guided.section_one"),
                items=(
                    FlowPage(
                        id="p1",
                        widget=FlowWidgetKind.INTEGER,
                        prompt=_copy("flows.guided.prompt_one"),
                        answer_type=int,
                    ),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


@pytest.mark.asyncio
async def test_a_refused_answer_reaches_the_operator_as_live_validation() -> None:
    """An invalid entry must SAY so on the page, not fail silently.

    The redesign reroutes input events through a different DOM ancestry, and a
    validation zone that stops updating looks exactly like a page where every
    answer is acceptable -- which is the worse of the two failures, because the
    operator proceeds believing they were understood.
    """
    host = ScreenHostApp(FlowScreen(_numeric_definition(), mode=FlowMode.MODIFY))
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"abc")
        await pilot.pause()

        rendered = str(host.screen.query_one("#live-validation", Static).render())
        assert rendered.startswith("✗"), f"no refusal rendered for a non-numeric answer: {rendered!r}"


@pytest.mark.asyncio
async def test_a_valid_answer_clears_the_live_validation_zone() -> None:
    """The converse, so the assertion above cannot pass on a zone stuck at a refusal."""
    host = ScreenHostApp(FlowScreen(_numeric_definition(), mode=FlowMode.MODIFY))
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"abc")
        await pilot.pause()
        for _ in range(3):
            await pilot.press("backspace")
        await pilot.press("7")
        await pilot.pause()

        assert str(host.screen.query_one("#live-validation", Static).render()) == ""


def _optional_with_help_definition() -> FlowDefinition:
    """One optional page carrying help copy, and one required page carrying none.

    The pair is what makes the zone-visibility contract testable: `_set_zone`
    sets ``display`` from whether the content is non-empty, so an absent help
    ref must HIDE the zone rather than render an empty panel.
    """
    return FlowDefinition(
        id="flows.test.zones",
        title=_copy("flows.guided.flow_title"),
        description=_copy("flows.guided.flow_title"),
        sections=(
            FlowSection(
                id="s1",
                title=_copy("flows.guided.section_one"),
                items=(
                    FlowPage(
                        id="p1",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy("flows.guided.prompt_one"),
                        help=_copy("flows.guided.prompt_two"),
                        required=False,
                        answer_type=str,
                    ),
                    FlowPage(
                        id="p2",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy("flows.guided.prompt_two"),
                        required=True,
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


@pytest.mark.asyncio
async def test_an_absent_help_ref_hides_its_zone_rather_than_rendering_an_empty_panel() -> None:
    """`_set_zone` drives ``display`` from content, and that must survive the move.

    A zone that renders empty instead of hiding leaves the operator reading a
    blank bordered panel, which is why the contract exists. It is invisible to
    any text assertion -- an empty string reads the same whether the node is
    hidden or shown -- so it has to be asserted on ``display``.
    """
    host = ScreenHostApp(FlowScreen(_optional_with_help_definition(), mode=FlowMode.MODIFY))
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert host.screen.query_one("#page-help", Static).display is True

        await pilot.click("#btn-next")
        await pilot.pause()

        assert host.screen.query_one("#page-help", Static).display is False


@pytest.mark.asyncio
async def test_the_badge_states_whether_the_page_is_required() -> None:
    """Required and optional must be distinguishable, and they share one node."""
    host = ScreenHostApp(FlowScreen(_optional_with_help_definition(), mode=FlowMode.MODIFY))
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        optional_badge = str(host.screen.query_one("#page-badge", Static).render())

        await pilot.click("#btn-next")
        await pilot.pause()
        required_badge = str(host.screen.query_one("#page-badge", Static).render())

        assert optional_badge != required_badge, "the badge did not change between an optional and a required page"


@pytest.mark.asyncio
async def test_the_answer_echo_reports_what_was_committed() -> None:
    """The echo is the operator's confirmation their input was taken."""
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"echoed")
        await pilot.click("#btn-next")
        await pilot.pause()
        await pilot.click("#btn-back")
        await pilot.pause()

        assert "echoed" in str(host.screen.query_one("#answer-echo", Static).render())


@pytest.mark.asyncio
async def test_restarting_asks_before_discarding_answers() -> None:
    """Ctrl+N must CONFIRM, never restart silently.

    The dialog is legitimately a pushed screen -- a modal is a host concern and
    stays one after the redesign -- so this proves the page still reaches the
    host to push it. A restart that stopped confirming would discard an
    operator's answers on a keystroke.
    """
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"typed")
        await pilot.press("ctrl+n")
        await pilot.pause()

        assert isinstance(host.screen, ConfirmScreen), f"ctrl+n did not raise a confirmation: {type(host.screen)}"


@pytest.mark.asyncio
async def test_declining_the_restart_leaves_the_answer_intact() -> None:
    """Cancelling must be a no-op, which is the half a confirm dialog exists for."""
    host = _host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"typed")
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert _answer_input(host).value == "typed"
