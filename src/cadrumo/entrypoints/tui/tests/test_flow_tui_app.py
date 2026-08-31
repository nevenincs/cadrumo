"""Pilot-driven behaviour tests for the full-screen flow frontend.

Every test drives the real :class:`FlowScreen` through Textual's headless
Pilot over a real :class:`FlowDefinition` built from the substrate's own
public models, and asserts against widget ids, engine state, and
``PageStatus`` / ``CheckpointAvailability`` members — never rendered
prose, which is locale data and would make the assertion tautological.

Two seams are real, not test doubles. Page copy resolves through the
sanctioned locale-root override against a fixture catalogue, so the copy
assembler runs its production locale-key path; the checkpoint port is
implemented by a JSON-file store whose persisted bytes the save-and-exit
tests read back, so the port is exercised end to end rather than
observed through a recording spy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
import yaml
from pydantic import BaseModel, TypeAdapter
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Input, Label, OptionList, ProgressBar, Static

from ....application.flows.definition import (
    CopyRef,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowLegalRef,
    FlowPage,
    FlowSection,
)
from ....application.flows.engine import answer, page_status, start_flow
from ....application.flows.errors import FlowCheckpointError
from ....core.config import TuiAppearance
from ....core.external_constants import OutputLanguage
from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
    PageStatus,
)
from ....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES, tr
from ....tests.env_scope import activate_output_language, output_language_scope
from ....tests.locales_root_fixture import locales_root_scope
from ..components.host import ScreenHostApp
from ..components.theme import (
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT_THEME_NAME,
    install_cadrumo_themes,
)
from ..components.widgets import ContentScroll
from ..flows.app import FlowScreen, run_flow_tui

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_entrypoint,
]

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from textual.pilot import Pilot

_COPY_REF = "flows.test.copy"
_COPY_CATALOGUE: dict[str, object] = {
    "flows": {
        "test": {
            "copy": "Dato solicitado",
            "desc": "DESC-TEXT",
            "prov": "PROV-TEXT",
            "title": "FLOW-TITLE",
        },
        "tui": {
            "header": "{flow} / {position} / {total} / {section}",
            "header_single_section": "{flow} / {position} / {total}",
        },
        # A candidate frame that interpolates both slots, so the COMPARE_SELECT
        # provenance is observable in the rendered label under the fixture root.
        "compare_select": {"candidate": "{label} :: {provenance}"},
    },
    "wizard": {"section": {"one": "SECTION-ONE", "two": "SECTION-TWO"}},
}

_TERMINAL_SIZE = (140, 60)
"""Wide enough that every zone of the question page is on-screen, so a
Pilot click resolves to the button it names rather than to whatever the
80x24 default left visible."""

_REGISTERED_VALUES: dict[str, str] = {
    "p_name": "ADA LOVELACE (registro)",
    "p_kind": "beta",
}


class _Answers(BaseModel):
    """Trivial answers model; only the type identity is consumed."""


_STR_ANSWERS_ADAPTER: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])


class _JsonFileCheckpointStore:
    """A real :class:`CheckpointStore` persisting answers to one JSON file.

    Not a recording double: the tests assert against the bytes this
    store wrote and read back, so the save-and-exit path is proven to
    have reached persistence rather than merely to have been called.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, flow_id: str) -> Path:
        return self._root / f"{flow_id}.json"

    def save(self, flow_id: str, answers: Mapping[str, str]) -> None:
        self._path(flow_id).write_text(json.dumps(dict(answers), sort_keys=True), encoding="utf-8")

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        path = self._path(flow_id)
        if not path.is_file():
            return None
        return _STR_ANSWERS_ADAPTER.validate_python(json.loads(path.read_text(encoding="utf-8")))

    def discard(self, flow_id: str) -> None:
        self._path(flow_id).unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _flow_copy_catalogue(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point copy resolution at a fixture catalogue carrying the test refs.

    Copy resolution refuses an unresolvable locale key rather than
    rendering a blank, and the shipped catalogues carry copy for the
    real domain flows only. The sanctioned locale-root override supplies
    the refs this module's definition declares, so the assembler runs
    its production locale-key path without a test string entering the
    packaged resources.
    """
    root = tmp_path_factory.mktemp("flow-tui-locales")
    payload = yaml.safe_dump(_COPY_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")
    with locales_root_scope(root):
        yield


def _copy(ref: str = _COPY_REF) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _definition() -> FlowDefinition:
    """One section, three pages: text, closed choice, optional text."""
    return FlowDefinition(
        id="flows.test.tui",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(id="p_name", widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str),
                    FlowPage(
                        id="p_kind",
                        widget=FlowWidgetKind.SELECT,
                        prompt=_copy(),
                        choices=(
                            FlowChoice(value="alpha", label=_copy()),
                            FlowChoice(value="beta", label=_copy()),
                        ),
                        answer_type=str,
                    ),
                    FlowPage(
                        id="p_note",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy(),
                        answer_type=str,
                        required=False,
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


def _app(
    *,
    mode: FlowMode = FlowMode.MODIFY,
    checkpoint_store: _JsonFileCheckpointStore | None = None,
) -> FlowScreen:
    return FlowScreen(
        _definition(),
        mode=mode,
        checkpoint_store=checkpoint_store,
        registered_values=_REGISTERED_VALUES,
    )


def _on_review(host: ScreenHostApp[None]) -> bool:
    """Whether the review screen (its data table) is the active screen."""
    return bool(host.screen.query("#review-table"))


def _review_rows(host: ScreenHostApp[None]) -> dict[str, list[str]]:
    """The review table's rendered cells keyed by page key (section headings skipped)."""
    table = host.screen.query_one("#review-table", DataTable)
    return {
        str(row_key.value): [str(cell) for cell in table.get_row(row_key)]
        for row_key in table.rows
        if row_key.value is not None and not str(row_key.value).startswith("\x00section\x00")
    }


async def _settled_cursor(pilot: Pilot[None], flow: FlowScreen, expected: str) -> str:
    """Pump the message queue until the engine cursor reaches ``expected``.

    Hosting the flow as a screen puts one more layer between a click and the
    state it produces, so an assertion taken on the very next line can read
    the pre-click cursor. This waits on the real postcondition rather than on
    a longer sleep: it returns as soon as the transition lands, and returns
    the actual cursor unchanged when it never does, so the caller's assertion
    still fails with the true value rather than on a timeout message.
    """
    for _ in range(50):
        if flow.state.cursor == expected:
            break
        await pilot.pause()
    cursor = flow.state.cursor
    assert cursor is not None, "a started flow always carries a cursor onto a visible page"
    return cursor


async def _answer_all_required(pilot: Pilot[None], app: FlowScreen) -> None:
    """Walk the flow answering both required pages through the widgets."""
    await pilot.press(*"ada")
    await pilot.click("#btn-next")
    # p_kind is a SELECT: choose the first numbered option (digit key).
    await pilot.press("1")
    await pilot.pause()


# ── click-driven navigation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_question_header_renders_the_flow_title_not_its_internal_id() -> None:
    definition = _definition().model_copy(update={"title": _copy("flows.test.title")})
    app = FlowScreen(definition, mode=FlowMode.MODIFY, registered_values=_REGISTERED_VALUES)
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        header = host.screen.query_one("#flow-header", Static)
        progress = host.screen.query_one("#flow-progress", ProgressBar)
        rendered = str(header.content)

        assert "FLOW-TITLE" in rendered
        assert app.definition.id not in rendered
        assert header.region.bottom <= progress.region.y, "the progress bar must not paint over the title"


@pytest.mark.asyncio
async def test_next_button_commits_the_pending_input_before_advancing() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        # The page under test is an Input page, so 'next' must take the
        # commit-then-advance arm rather than the committed-widget arm.
        assert host.screen.query_one("#widget-area").query_one(Input).value == ""

        await pilot.press(*"ada")
        assert app.state.answers.get("p_name") is None  # uncommitted keystrokes

        await pilot.click("#btn-next")

        assert app.state.answers["p_name"] == "ada"
        assert app.state.cursor == "p_kind"


@pytest.mark.asyncio
async def test_next_button_holds_the_page_when_the_commit_is_invalid() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.click("#btn-next")  # blank on an unconditionally required page

        assert "p_name" not in app.state.answers
        assert app.state.cursor == "p_name"
        assert page_status(app.state, "p_name") is PageStatus.INVALID


@pytest.mark.asyncio
async def test_back_button_returns_the_cursor_to_the_previous_page() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        assert app.state.cursor == "p_kind"

        await pilot.click("#btn-back")

        assert await _settled_cursor(pilot, app, "p_name") == "p_name"


@pytest.mark.asyncio
async def test_review_button_opens_the_review_screen() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        assert not _on_review(host)

        await pilot.click("#btn-review")

        assert _on_review(host)


# ── the review table ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_table_renders_the_registered_value_beside_the_answer() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")

        rows = _review_rows(host)

        assert set(rows) == {"p_name", "p_kind", "p_note"}
        assert rows["p_name"][2] == app.state.answers["p_name"]
        assert rows["p_name"][3] == _REGISTERED_VALUES["p_name"]
        assert rows["p_kind"][3] == tr(_COPY_REF)
        assert _REGISTERED_VALUES["p_kind"] not in rows["p_kind"][3]
        # A page the domain supplied no registered value for renders blank,
        # never a placeholder the operator could read as a record.
        assert rows["p_note"][3] == ""


@pytest.mark.asyncio
async def test_closed_choice_answer_renders_its_label_not_its_storage_token() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")

        answer_cell = _review_rows(host)["p_kind"][2]
        assert answer_cell == tr(_COPY_REF)
        assert app.state.answers["p_kind"] == "alpha", "the positive control must store a distinct token"
        assert "alpha" not in answer_cell


@pytest.mark.asyncio
async def test_review_table_status_glyph_is_a_function_of_page_status() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")

        rows = _review_rows(host)
        glyph_by_key = {key: cells[0] for key, cells in rows.items()}
        status_by_key = {key: page_status(app.state, key) for key in rows}

        assert set(status_by_key.values()) == {PageStatus.ANSWERED, PageStatus.UNANSWERED}
        for left in rows:
            for right in rows:
                assert (glyph_by_key[left] == glyph_by_key[right]) is (status_by_key[left] == status_by_key[right])


@pytest.mark.asyncio
async def test_review_row_selection_jumps_the_cursor_to_that_page() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")
        assert _on_review(host)

        table = host.screen.query_one("#review-table", DataTable)
        table.move_cursor(row=table.get_row_index("p_note"))
        await pilot.press("enter")

        assert app.state.cursor == "p_note"
        assert not _on_review(host)


def _two_section_definition() -> FlowDefinition:
    """Two named sections, one page each -- the shape a heading actually groups."""
    return FlowDefinition(
        id="flows.test.tui.two-sections",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy("wizard.section.one"),
                items=(FlowPage(id="p_first", widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str),),
            ),
            FlowSection(
                id="s2",
                title=_copy("wizard.section.two"),
                items=(
                    FlowPage(
                        id="p_second", widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str, required=False
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


def _heading_rows(host: ScreenHostApp[None]) -> list[str]:
    """The section-heading rows' rendered titles, in table order."""
    table = host.screen.query_one("#review-table", DataTable)
    return [
        str(table.get_row(row_key)[1])
        for row_key in table.rows
        if row_key.value is not None and str(row_key.value).startswith("\x00section\x00")
    ]


@pytest.mark.asyncio
async def test_review_table_omits_the_heading_row_when_the_flow_has_one_section() -> None:
    """A single-section flow's review table opens directly on its first question.

    The heading exists to distinguish one section's rows from another's;
    with exactly one section there is nothing to distinguish, and
    rendering it anyway means the table's very first row is whatever that
    lone section happens to be titled with -- for the live modelo-work and
    amend wizards, their own multi-sentence help copy, landing in the
    table looking exactly like a question row with no status glyph.
    """
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press("f2")

        assert _heading_rows(host) == []
        table = host.screen.query_one("#review-table", DataTable)
        assert table.row_count == 3, "every real page must still be a row; only the heading is omitted"


@pytest.mark.asyncio
async def test_review_table_still_groups_multiple_sections_by_heading() -> None:
    """A genuinely multi-section flow keeps its per-section heading rows."""
    app = FlowScreen(_two_section_definition(), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press("f2")

        assert _heading_rows(host) == [tr("wizard.section.one"), tr("wizard.section.two")]


# ── submit gating ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_is_disabled_and_inert_while_a_required_page_is_unanswered() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press("f2")

        assert host.screen.query_one("#btn-submit", Button).disabled is True

        await pilot.press("s")  # the review screen's submit binding
        await pilot.pause()

        assert app.final_state is None
        assert app.final_projection is None
        assert _on_review(host)


@pytest.mark.asyncio
async def test_submit_enabled_once_eligible_exits_with_the_final_projection() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")

        assert host.screen.query_one("#btn-submit", Button).disabled is False

        await pilot.click("#btn-submit")
        await pilot.pause()

    assert app.final_state is not None
    assert app.final_state.answers["p_name"] == "ada"
    assert app.final_projection is not None
    assert app.final_projection.submit_eligible is True
    assert app.saved_and_exited is False


# ── key bindings ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_escape_routes_to_the_back_intent() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")

        await pilot.press("escape")

        assert app.state.cursor == "p_name"


@pytest.mark.asyncio
async def test_f2_routes_to_the_review_intent_and_escape_leaves_it() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press("f2")
        assert _on_review(host)

        await pilot.press("escape")

        assert not _on_review(host)


@pytest.mark.asyncio
async def test_ctrl_r_resets_the_cursor_page_answer() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        await pilot.press("escape")
        assert app.state.answers["p_name"] == "ada"

        await pilot.press("ctrl+r")

        assert "p_name" not in app.state.answers
        assert page_status(app.state, "p_name") is PageStatus.UNANSWERED


@pytest.mark.asyncio
async def test_ctrl_n_asks_before_restarting_and_leaves_answers_alone_until_confirmed() -> None:
    """A single ``ctrl+n`` must not wipe the flow by itself.

    ``restart_flow`` is unconditional at the engine layer by design — the
    substrate's own docstring states the confirmation is "a frontend
    responsibility". A frontend that called straight through discharged
    none of that: one mis-struck chord on a long walk erased every
    answer with nothing to undo. The dialog is what discharges it.
    """
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        answers_before = dict(app.state.answers)
        assert answers_before

        await pilot.press("ctrl+n")
        await pilot.pause()

        # The engine state is untouched while the dialog is open.
        assert app.state.answers == answers_before
        assert host.screen.query_one("#confirm-title")

        await pilot.click("#btn-confirm-cancel")
        await pilot.pause()

        # Declining leaves every answer exactly where it was.
        assert app.state.answers == answers_before


@pytest.mark.asyncio
async def test_ctrl_n_restarts_the_flow_from_the_first_page_once_confirmed() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        assert app.state.answers

        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.click("#btn-confirm-accept")
        await pilot.pause()

        assert app.state.answers == {}
        assert app.state.cursor == "p_name"
        assert not _on_review(host)


@pytest.mark.asyncio
async def test_ctrl_n_on_the_review_screen_also_asks_before_restarting() -> None:
    """The review page is where every answer is visible at once — and
    exactly where an accidental restart is costliest, since the operator
    may have just reached the end of a long walk. The guard must not be
    only on the question screen."""
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        await pilot.press("f2")
        await pilot.pause()
        assert _on_review(host)
        answers_before = dict(app.state.answers)

        await pilot.press("ctrl+n")
        await pilot.pause()

        assert app.state.answers == answers_before
        assert host.screen.query_one("#confirm-title")

        await pilot.click("#btn-confirm-accept")
        await pilot.pause()

        assert app.state.answers == {}


@pytest.mark.asyncio
async def test_ctrl_s_persists_through_the_checkpoint_store_and_exits(tmp_path: Path) -> None:
    store = _JsonFileCheckpointStore(tmp_path)
    app = _app(mode=FlowMode.CREATE, checkpoint_store=store)
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")

        await pilot.press("ctrl+s")
        await pilot.pause()

    assert store.load("flows.test.tui") == {"p_name": "ada"}
    assert app.saved_and_exited is True
    assert app.final_state is not None
    assert app.final_projection is not None


@pytest.mark.asyncio
async def test_ctrl_s_is_inert_in_a_mode_declaring_checkpointing_unavailable(tmp_path: Path) -> None:
    store = _JsonFileCheckpointStore(tmp_path)
    app = _app(mode=FlowMode.MODIFY, checkpoint_store=store)
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")

        await pilot.press("ctrl+s")
        await pilot.pause()

        assert store.load("flows.test.tui") is None
        assert app.saved_and_exited is False
        assert app.final_state is None
        assert host.is_running


# ── checkpoint honesty and abandoned runs ───────────────────────────────────


def test_declared_checkpointing_without_a_store_refuses_at_construction() -> None:
    definition = _definition()
    with pytest.raises(FlowCheckpointError) as excinfo:
        FlowScreen(_definition(), mode=FlowMode.CREATE)

    assert excinfo.value.context == {
        "flow_id": tr(str(definition.title.ref)),
        "mode": tr("flows.review.mode_create"),
    }
    assert definition.id not in excinfo.value.context.values()
    assert FlowMode.CREATE.value not in excinfo.value.context.values()


def test_declared_checkpointing_without_a_store_refuses_before_the_run_starts() -> None:
    with pytest.raises(FlowCheckpointError):
        run_flow_tui(_definition(), mode=FlowMode.CREATE)


def test_a_mode_declaring_checkpointing_unavailable_constructs_without_a_store() -> None:
    app = FlowScreen(_definition(), mode=FlowMode.MODIFY)

    assert app.state.mode is FlowMode.MODIFY


# ── checkbox, secret, stale-orphan, and select-revisit coverage ──────────────


def _checkbox_definition() -> FlowDefinition:
    """One required CHECKBOX page carrying three choices."""
    return FlowDefinition(
        id="flows.test.checkbox",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(
                        id="p_multi",
                        widget=FlowWidgetKind.CHECKBOX,
                        prompt=_copy(),
                        choices=(
                            FlowChoice(value="c1", label=_copy()),
                            FlowChoice(value="c2", label=_copy()),
                            FlowChoice(value="c3", label=_copy()),
                        ),
                        answer_type=str,
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


def _secret_definition() -> FlowDefinition:
    """A required SECRET page followed by an optional text page."""
    return FlowDefinition(
        id="flows.test.secret",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(id="p_secret", widget=FlowWidgetKind.SECRET, prompt=_copy(), answer_type=str),
                    FlowPage(id="p_after", widget=FlowWidgetKind.TEXT, prompt=_copy(), answer_type=str, required=False),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _gate_definition() -> FlowDefinition:
    """A SELECT gate and a text page visible only while the gate is 'alpha'."""
    return FlowDefinition(
        id="flows.test.gate",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(
                        id="p_gate",
                        widget=FlowWidgetKind.SELECT,
                        prompt=_copy(),
                        choices=(FlowChoice(value="alpha", label=_copy()), FlowChoice(value="beta", label=_copy())),
                        answer_type=str,
                    ),
                    FlowPage(
                        id="p_dep",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy(),
                        answer_type=str,
                        visible_when=FlowCondition(page_id="p_gate", equals="alpha"),
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


@pytest.mark.asyncio
async def test_checkbox_page_stages_two_selections_under_one_key() -> None:
    app = FlowScreen(_checkbox_definition(), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        # Digit keys toggle the numbered rows of the checkbox list.
        await pilot.press("1")  # toggle the first choice
        await pilot.press("2")  # toggle the second choice
        await pilot.pause()

        # Both selections land under the one page key, and the page does not
        # advance on a toggle — staging, not commit-then-move.
        assert set(app.state.answers["p_multi"].split(",")) == {"c1", "c2"}
        assert app.state.cursor == "p_multi"
        assert not _on_review(host)


@pytest.mark.asyncio
async def test_secret_answer_is_masked_in_the_echo_and_the_review_table() -> None:
    # A non-empty registered value for the SECRET page is the positive
    # control the answer-only fixture below cannot provide: the registered
    # column must mask it exactly as the answer column masks the in-flow
    # answer, through the same widget-kind lookup, not a second authority.
    registered_secret = "vault-stored-token"  # noqa: S105 - test fixture value, not a credential
    app = FlowScreen(
        _secret_definition(),
        mode=FlowMode.MODIFY,
        registered_values={"p_secret": registered_secret},
    )
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"hunter2")
        await pilot.click("#btn-next")  # commit the secret, advance to p_after
        await pilot.click("#btn-back")  # back to p_secret so its echo re-renders

        assert app.state.answers["p_secret"] == "hunter2"  # noqa: S105 - test fixture secret, not a credential
        masked = tr("flows.progress.current_answer_secret")
        echo = str(host.screen.query_one("#answer-echo", Static).render())
        # Pair the assertion: first prove the echo zone actually rendered the
        # masked marker (a non-empty, correct surface), THEN prove the raw
        # secret is absent — an absence check is only meaningful against a
        # proven-present surface.
        assert masked
        assert masked in echo
        assert "hunter2" not in echo
        # The re-mounted secret Input is blank, never pre-filled with the secret.
        assert host.screen.query_one("#widget-area").query_one(Input).value == ""

        await pilot.press("f2")
        rows = _review_rows(host)
        # The secret's review row genuinely rendered (present with a status
        # glyph), its answer column carries the masked marker, and only then
        # is the raw secret asserted absent.
        assert "p_secret" in rows
        assert rows["p_secret"][0]  # status glyph column populated
        assert rows["p_secret"][2] == masked
        assert "hunter2" not in rows["p_secret"][2]
        # The registered column is the positive control: a real on-record
        # value for a SECRET page must render the same masked marker, never
        # the raw registered value, in the clear.
        assert rows["p_secret"][3] == masked
        assert registered_secret not in rows["p_secret"][3]


@pytest.mark.asyncio
async def test_stale_orphan_reset_arm_of_edit_from_review_clears_the_answer() -> None:
    definition = _gate_definition()
    # Flip the gate after answering its dependent so the dependent is an
    # invisible stale orphan on resume.
    stale = start_flow(definition, mode=FlowMode.MODIFY)
    stale = answer(definition, stale, "p_gate", "alpha")
    stale = answer(definition, stale, "p_dep", "detail")
    stale = answer(definition, stale, "p_gate", "beta")
    assert "p_dep" in stale.stale

    app = FlowScreen(definition, mode=FlowMode.MODIFY, resume_state=stale, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press("f2")
        assert _on_review(host)

        table = host.screen.query_one("#review-table", DataTable)
        table.move_cursor(row=table.get_row_index("p_dep"))
        await pilot.press("enter")  # select the stale orphan -> confirmed reset arm
        await pilot.pause()

        assert "p_dep" not in app.state.answers
        assert "p_dep" not in app.state.stale
        assert _on_review(host)  # the reset resolves the row in place


def _legal_definition() -> FlowDefinition:
    """A page carrying a two-citation legal-provenance zone."""
    return FlowDefinition(
        id="flows.test.legal",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(
                        id="p_legal",
                        widget=FlowWidgetKind.TEXT,
                        prompt=_copy(),
                        legal_zone=(
                            FlowLegalRef(ref="ley-35-2006:art-27", label=_copy()),
                            FlowLegalRef(ref="ley-35-2006:art-28"),
                        ),
                        answer_type=str,
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


def test_run_flow_tui_hands_the_constructed_app_to_on_app_ready() -> None:
    """The runner passes its one constructed app to ``on_app_ready`` before running it.

    A caller capturing the handle (to drive ``rebuild_for_locale`` from an
    answer hook) must receive the exact instance the runner then runs and
    reads ``final_state`` from — not a second app the caller builds itself,
    which would duplicate the abandoned-run guard. The callback aborts with
    a sentinel so the assertion runs before ``app.run()`` opens a terminal:
    the handle is a fully-constructed :class:`FlowScreen` for the definition,
    whose ``final_state`` is still ``None`` because the run has not started —
    proving the pre-run passthrough of the runner's own single app instance.
    """

    class _AbortRunError(Exception):
        """Sentinel raised from the hook to abort before the interactive run."""

    captured: dict[str, FlowScreen] = {}

    def _capture(app: FlowScreen) -> None:
        captured["ready"] = app
        raise _AbortRunError

    with pytest.raises(_AbortRunError):
        run_flow_tui(
            _definition(),
            mode=FlowMode.MODIFY,
            registered_values=_REGISTERED_VALUES,
            on_screen_ready=_capture,
        )

    ready = captured["ready"]
    assert isinstance(ready, FlowScreen)
    assert ready.definition.id == "flows.test.tui"
    # The hook fires after construction and before the run, so the runner has
    # not yet produced (or read) a final_state on this very instance.
    assert ready.final_state is None


def _date_definition() -> FlowDefinition:
    """One required DATE page mounting a single-line Input."""
    return FlowDefinition(
        id="flows.test.date",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(FlowPage(id="p_date", widget=FlowWidgetKind.DATE, prompt=_copy(), answer_type=str),),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


@pytest.mark.asyncio
async def test_date_page_live_validation_flags_a_bad_date_then_clears_on_a_good_one() -> None:
    app = FlowScreen(_date_definition(), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        # A DATE page mounts a single-line Input (tier-one live validation runs
        # per keystroke through the same widget-shape validator the commit uses).
        field = host.screen.query_one("#widget-area").query_one(Input)

        await pilot.press(*"2026-13-01")  # an impossible month: fails the ISO shape
        await pilot.pause()
        bad_hint = str(host.screen.query_one("#live-validation", Static).render())
        assert bad_hint.startswith("✗")  # the shape error is shown live, non-blocking

        field.value = "2026-01-05"  # replace with a valid ISO date
        await pilot.pause()

        # The live line clears the moment the shape passes; the answer is still
        # uncommitted (live validation never writes engine state).
        assert str(host.screen.query_one("#live-validation", Static).render()) == ""
        assert "p_date" not in app.state.answers


@pytest.mark.asyncio
async def test_progress_bar_tracks_the_visible_position() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        bar = host.screen.query_one("#flow-progress", ProgressBar)
        assert bar.total == 3  # the definition has three visible pages
        assert bar.progress == 1  # cursor on the first page

        await pilot.press(*"ada")
        await pilot.click("#btn-next")

        assert host.screen.query_one("#flow-progress", ProgressBar).progress == 2


@pytest.mark.asyncio
async def test_legal_zone_renders_the_citations_in_the_question_panel() -> None:
    app = FlowScreen(_legal_definition(), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        zone = host.screen.query_one("#page-legal-zone", Static)
        content = str(zone.render())

        # The zone is shown and carries both citation ref tokens (data,
        # rendered verbatim); the labelled one and the bare one both appear.
        assert zone.display is True
        assert "ley-35-2006:art-27" in content
        assert "ley-35-2006:art-28" in content


@pytest.mark.asyncio
async def test_legal_zone_is_hidden_when_the_page_declares_none() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        # The three-page definition declares no legal zone, so the zone is
        # collapsed rather than framing an empty gap.
        assert host.screen.query_one("#page-legal-zone", Static).display is False


def _described_choice(value: str, *, provenance: bool = False) -> FlowChoice:
    return FlowChoice(
        value=value,
        label=_copy(),
        description=_copy("flows.test.desc"),
        provenance=_copy("flows.test.prov") if provenance else None,
    )


def _choice_definition(widget: FlowWidgetKind, *, provenance: bool = False) -> FlowDefinition:
    return FlowDefinition(
        id="flows.test.choices",
        title=_copy(),
        description=_copy(),
        sections=(
            FlowSection(
                id="s1",
                title=_copy(),
                items=(
                    FlowPage(
                        id="p_choice",
                        widget=widget,
                        prompt=_copy(),
                        choices=(
                            _described_choice("a", provenance=provenance),
                            _described_choice("b", provenance=provenance),
                        ),
                        answer_type=str,
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


def _option_prompts(host: ScreenHostApp[None]) -> str:
    """The rendered prompt text of every option in the mounted choice list."""
    option_list = host.screen.query_one("#widget-area").query_one(OptionList)
    return "\n".join(str(option_list.get_option_at_index(index).prompt) for index in range(option_list.option_count))


@pytest.mark.asyncio
async def test_select_renders_a_numbered_list_with_descriptions() -> None:
    app = FlowScreen(_choice_definition(FlowWidgetKind.SELECT), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        text = _option_prompts(host)

        # Numbered single-choice rows (unselected radio glyph) with the
        # domain description on the reserved second line.
        assert "1. ( ) " in text
        assert "2. ( ) " in text
        assert "DESC-TEXT" in text


@pytest.mark.asyncio
async def test_checkbox_renders_a_numbered_list_with_descriptions() -> None:
    app = FlowScreen(_choice_definition(FlowWidgetKind.CHECKBOX), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        text = _option_prompts(host)

        # Numbered multi-select rows carry the checkbox glyph, unticked.
        assert "1. [ ] " in text
        assert "2. [ ] " in text
        assert "DESC-TEXT" in text


@pytest.mark.asyncio
async def test_compare_select_renders_provenance_and_a_final_defer_row() -> None:
    app = FlowScreen(
        _choice_definition(FlowWidgetKind.COMPARE_SELECT, provenance=True),
        mode=FlowMode.MODIFY,
        registered_values={},
    )
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        text = _option_prompts(host)

        # Provenance is the reason COMPARE_SELECT exists; it and the
        # description reach the numbered candidate rows, and the defer arm is
        # the final numbered row (two candidates, then row 3).
        assert "PROV-TEXT" in text
        assert "DESC-TEXT" in text
        assert "3. ( ) " in text


@pytest.mark.asyncio
async def test_rebuild_for_locale_reassembles_copy_under_the_new_language(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("rebuild-locales")
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        payload = yaml.safe_dump({"flows": {"test": {"copy": f"{language}-copy"}}}, allow_unicode=True)
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")

    with output_language_scope(OutputLanguage.EN), locales_root_scope(root):
        app = FlowScreen(_definition(), mode=FlowMode.MODIFY, registered_values={})
        host = ScreenHostApp(app)
        async with host.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert "en-copy" in str(host.screen.query_one("#page-prompt", Label).render())

            activate_output_language(OutputLanguage.ES)
            app.rebuild_for_locale()
            await pilot.pause()

            # The engine state is untouched; every zone re-assembles, so the
            # prompt re-resolves under the newly-activated language.
            assert "es-copy" in str(host.screen.query_one("#page-prompt", Label).render())


@pytest.mark.asyncio
async def test_on_answer_committed_receives_the_page_key_and_committed_value() -> None:
    received: list[tuple[str, str]] = []
    app = FlowScreen(
        _definition(),
        mode=FlowMode.MODIFY,
        registered_values={},
        on_answer_committed=lambda key, value: received.append((key, value)),
    )
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        await pilot.pause()

    assert ("p_name", "ada") in received


@pytest.mark.asyncio
async def test_locale_switch_hook_renders_the_next_page_under_the_new_language(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("hook-locales")
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        payload = yaml.safe_dump({"flows": {"test": {"copy": f"{language}-copy"}}}, allow_unicode=True)
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")

    holder: dict[str, FlowScreen] = {}

    def _switch_to_spanish(page_key: str, _value: str) -> None:
        if page_key == "p_name":
            # This hook runs inside Textual's message-pump Task, a different
            # asyncio Context from the test's own coroutine, so an
            # ``override_settings`` contextvar Token could not be reset from
            # here. ``activate_output_language`` drops plain caches instead
            # and has no such boundary; the enclosing scope owns the restore.
            activate_output_language(OutputLanguage.ES)
            holder["app"].rebuild_for_locale()

    with output_language_scope(OutputLanguage.EN), locales_root_scope(root):
        app = FlowScreen(
            _definition(),
            mode=FlowMode.MODIFY,
            registered_values={},
            on_answer_committed=_switch_to_spanish,
        )
        holder["app"] = app
        host = ScreenHostApp(app)
        async with host.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert "en-copy" in str(host.screen.query_one("#page-prompt", Label).render())

            await pilot.press(*"ada")
            await pilot.click("#btn-next")
            await pilot.pause()

            # The commit fired the hook (activate Spanish + rebuild); the
            # walk advanced, and the page now renders under the newly
            # activated language — the mid-walk language switch the
            # operator's language-first feature needs.
            assert app.state.cursor == "p_kind"
            assert "es-copy" in str(host.screen.query_one("#page-prompt", Label).render())


@pytest.mark.asyncio
async def test_reentering_an_answered_select_from_review_does_not_auto_advance() -> None:
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await _answer_all_required(pilot, app)
        before = app.state.answers["p_kind"]
        await pilot.press("f2")

        table = host.screen.query_one("#review-table", DataTable)
        table.move_cursor(row=table.get_row_index("p_kind"))
        await pilot.press("enter")  # jump back into the answered SELECT page
        await pilot.pause()

        # The OptionList fires no selection on mount, so re-entering an
        # answered SELECT neither re-commits nor auto-advances past it.
        assert not _on_review(host)
        assert app.state.cursor == "p_kind"
        assert app.state.answers["p_kind"] == before


@pytest.mark.asyncio
async def test_checkbox_digit_toggle_updates_the_glyph_in_place() -> None:
    app = FlowScreen(_checkbox_definition(), mode=FlowMode.MODIFY, registered_values={})
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        text = _option_prompts(host)
        assert "1. [ ] " in text  # both unticked to start
        assert "2. [ ] " in text

        await pilot.press("1")  # toggle row 1 on
        await pilot.pause()
        text = _option_prompts(host)
        assert "1. [x] " in text  # row 1 glyph flipped in place
        assert "2. [ ] " in text  # row 2 untouched

        await pilot.press("2")  # toggle row 2 on
        await pilot.pause()
        text = _option_prompts(host)
        assert "1. [x] " in text  # row 1 still ticked
        assert "2. [x] " in text  # row 2 flipped in place
        assert set(app.state.answers["p_multi"].split(",")) == {"c1", "c2"}


_ABANDONED_RUN_SCRIPT = """
import sys
from pathlib import Path

from pydantic import BaseModel

from cadrumo.entrypoints.tui.flows.app import run_flow_tui
from cadrumo.application.flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from cadrumo.application.flows.errors import FlowCheckpointError
from cadrumo.core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from cadrumo.tests.locales_root_fixture import locales_root_scope


class _Answers(BaseModel):
    pass


copy = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="flows.test.copy")
definition = FlowDefinition(
    id="flows.test.abandoned",
    title=copy,
    description=copy,
    sections=(
        FlowSection(
            id="s1",
            title=copy,
            items=(FlowPage(id="p_name", widget=FlowWidgetKind.TEXT, prompt=copy, answer_type=str),),
        ),
    ),
    answers_model=_Answers,
    checkpoint={
        FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
        FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
    },
)

with locales_root_scope(Path(sys.argv[1])):
    try:
        run_flow_tui(definition, mode=FlowMode.MODIFY)
    except FlowCheckpointError:
        print("REFUSED_ABANDONED_RUN")
        sys.exit(0)
print("RETURNED_WITHOUT_REFUSAL")
sys.exit(1)
"""


def test_run_flow_tui_raises_on_a_run_abandoned_without_submit_or_save(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A real headless run that quits without submitting must not return.

    ``run_flow_tui`` drives ``App.run`` itself, so the abandonment is
    reproduced in an owned subprocess: Textual's headless driver plus its
    screenshot timer quit the application exactly as an
    operator abandoning the run would, and the frontend must refuse
    rather than hand back a value that reads as a completed flow.
    """
    locales_root = tmp_path_factory.mktemp("abandoned-locales")
    payload = yaml.safe_dump(_COPY_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (locales_root / f"{language}.yml").write_text(payload, encoding="utf-8")

    completed = subprocess.run(  # noqa: S603 - fixed argv, owned local interpreter
        [sys.executable, "-c", _ABANDONED_RUN_SCRIPT, str(locales_root)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={
            **os.environ,
            "TEXTUAL_DRIVER": "textual.drivers.headless_driver:HeadlessDriver",
            "TEXTUAL_SCREENSHOT": "1",
            "TEXTUAL_SCREENSHOT_LOCATION": str(tmp_path),
        },
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "REFUSED_ABANDONED_RUN" in completed.stdout


# ── appearance ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("appearance", "expected_theme"),
    [
        (TuiAppearance.LIGHT, CADRUMO_LIGHT_THEME_NAME),
        (TuiAppearance.DARK, CADRUMO_DARK_THEME_NAME),
    ],
)
async def test_flow_mounts_and_activates_the_configured_appearance(
    appearance: TuiAppearance,
    expected_theme: str,
) -> None:
    """The configured appearance is the one the mounted app actually runs.

    Mounting is the real assertion: Textual resolves the whole stylesheet
    against the active theme's tokens at mount, so a rule naming a token
    the theme does not define fails here rather than at the operator's
    terminal. Driving both appearances therefore proves both token sets
    satisfy every rule the flow surfaces declare.
    """
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        install_cadrumo_themes(host, appearance=appearance)
        await pilot.pause()
        assert host.theme == expected_theme
        # The body lives on the pushed QuestionScreen, not the default
        # screen. Scrolling and the bordered box are two widgets, not one:
        # the ContentScroll host is what scrolls, and #page-body is the
        # panel inside it. Collapsing them gave the panel `height: auto`,
        # which cannot scroll and pushed the overflow onto the Screen.
        assert host.screen.query_one("#page-scroll", ContentScroll)
        assert host.screen.query_one("#page-body", Vertical)


@pytest.mark.asyncio
async def test_f3_toggles_the_appearance_and_leaves_the_flow_state_untouched() -> None:
    """The appearance switch is presentation-only: no engine transition.

    F2 remains the review intent; the appearance toggle deliberately took
    F3 so it shadows nothing. The operator keeps their cursor and their
    committed answers across the switch.
    """
    app = _app()
    host = ScreenHostApp(app)
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        install_cadrumo_themes(host, appearance=TuiAppearance.DARK)
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        cursor_before = app.state.cursor
        answers_before = dict(app.state.answers)

        await pilot.press("f3")
        await pilot.pause()
        assert host.theme == CADRUMO_LIGHT_THEME_NAME

        await pilot.press("f3")
        await pilot.pause()
        assert host.theme == CADRUMO_DARK_THEME_NAME

        assert app.state.cursor == cursor_before
        assert dict(app.state.answers) == answers_before
        assert not _on_review(host), "F3 must not trigger the F2 review intent"
