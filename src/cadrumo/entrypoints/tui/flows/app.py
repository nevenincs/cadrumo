"""The Textual app driver: engine transitions in, screen renders out.

The app owns exactly two responsibilities: hold the current
:class:`FlowState` (replacing it wholesale on every engine transition)
and route screen intents onto engine calls. It never interprets an
answer, never evaluates visibility, and never decides eligibility —
those are direct :mod:`cadrumo.application.flows` defining-module calls whose results the
screens render. The intent surface mirrors the substrate's closed
:class:`~cadrumo.core.flows.FlowIntentKind` set.

Checkpoint honesty mirrors the line-mode frontend: a mode whose
definition declares checkpointing AVAILABLE demands an injected store at
construction (fail fast, before any answer could be lost), and the
declared no-op arm disables save-and-exit with an explicit line on the
review screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, override

from pydantic import TypeAdapter, ValidationError
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widget import AwaitMount, Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    OptionList,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
)
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from ....application.flows.checkpoint import checkpoint_available, save_checkpoint
from ....application.flows.copy import assemble_page_copy, assemble_section_titles, resolve_copy
from ....application.flows.definition import FlowPage
from ....application.flows.engine import (
    answer,
    back_page,
    jump_to,
    next_page,
    page_status,
    reset_page,
    restart_flow,
    start_flow,
    visible_sequence,
)
from ....application.flows.errors import FlowCheckpointError, FlowUnsupportedConsoleError
from ....application.flows.line_frontend import LineFlowFrontend
from ....application.flows.review import ReviewProjection, ReviewRow, assert_submit_eligible, review
from ....application.flows.validators import validate_widget_shape
from ....core.flows import (
    DEFER_TOKEN,
    REPEATING_INSTANCE_SEPARATOR,
    FlowMode,
    FlowWidgetKind,
    FrontendCapability,
    PageStatus,
)
from ....core.i18n.render import tr
from ....core.parsing import parse_bool
from ..components.app_access import TypedAppAccess
from ..components.dialogs import ConfirmScreen
from ..components.host import ScreenHostApp
from ..components.keyboard import localize_key_descriptions
from ..components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from ..components.widgets import ContentScroll, StageNavigationStrip

if TYPE_CHECKING:
    from collections.abc import Mapping

    from textual.events import Key

    from ....application.flows.checkpoint import CheckpointStore
    from ....application.flows.copy import ChoiceCopy, PageCopy
    from ....application.flows.definition import FlowDefinition
    from ....application.flows.engine import FlowState, VisiblePage
    from ....application.flows.validators import ValidationVerdict


def _operator_flow_context(definition: FlowDefinition, mode: FlowMode) -> dict[str, str]:
    """Return error interpolation values containing presentation copy only."""
    return {
        "flow_id": resolve_copy(definition.title),
        "mode": tr("flows.review.mode_create" if mode is FlowMode.CREATE else "flows.review.mode_modify"),
    }


class FlowPresenter(Protocol):
    """What a flow page needs from whatever is driving the flow.

    The two page screens once took the concrete application as a constructor
    argument and reached back into it fifty-seven times, which pinned them to
    the one host that owned them. This protocol is that reach, written down:
    engine state to render, and the closed intent set to route. Nothing here
    is a Textual concept, so a page can be mounted by any host that can drive
    a flow -- and the protocol failing to grow is the signal that the pages
    have stayed host-agnostic.
    """

    @property
    def definition(self) -> FlowDefinition:
        """The flow being run."""
        ...

    @property
    def state(self) -> FlowState:
        """Current engine state, replaced wholesale on every transition."""
        ...

    @property
    def registered_values(self) -> Mapping[str, str]:
        """Domain-supplied display values already on record, keyed by page key."""
        ...

    def cursor_entry(self) -> VisiblePage | None:
        """The visible-sequence entry the engine cursor addresses, if any."""
        ...

    def is_secret_page(self, page_key: str) -> bool:
        """Whether the page a key addresses collects a secret answer."""
        ...

    def commit_answer(self, raw: str, *, advance: bool = True) -> None:
        """Commit the cursor page's answer, optionally advancing afterwards."""
        ...

    def navigate_back(self) -> None:
        """Move the cursor to the previous visible page."""
        ...

    def action_next(self) -> None:
        """Advance from the current page."""
        ...

    def action_go_review(self) -> None:
        """Open the review surface."""
        ...

    def action_leave_review(self) -> None:
        """Return from the review surface to the question surface."""
        ...

    def action_reset_current(self) -> None:
        """Clear the cursor page's answer."""
        ...

    def action_restart(self) -> None:
        """Restart the flow from its first page."""
        ...

    def action_submit(self) -> None:
        """Submit the flow when it is eligible."""
        ...

    def action_save_exit(self) -> None:
        """Checkpoint the run and leave."""
        ...

    def edit_from_review(self, page_key: str) -> None:
        """Jump back to one page addressed from the review table."""
        ...


_APPEARANCE_BINDING = Binding("f3", "toggle_appearance", "", show=False)
"""Appearance toggle, declared once on the flow surface.

F2 is the review intent on the question page; F3 is free across every
surface. It sits on the FLOW rather than on each page because the pages are
now content the flow owns, so the flow is the active screen and the binding
resolves from it -- it was previously duplicated onto both pages precisely
because the flow was never active. Hidden and description-free: a BINDINGS
list resolves at import time, so a ``tr`` call here would freeze the
import-time language into the footer the pages deliberately defer.
"""


class FlowScreen(TypedAppAccess, Screen[None]):
    """Full-screen projection of one flow run, mountable by any host.

    ``DEFAULT_CSS`` rather than ``CSS``: Textual applies a screen
    subclass's ``DEFAULT_CSS`` and ignores ``CSS`` entirely, so declaring
    the stylesheet under the wrong name drops it silently while almost
    every test still passes and only a geometry assertion notices.
    The pages are content this surface owns, mounted into ``#flow-content``,
    so its document tree and bindings participate: ``SCOPED_CSS`` keeps its
    default because the styled nodes are genuine descendants, and the
    appearance binding is declared once HERE rather than duplicated onto each
    page because this surface is the one that is actually active.
    """

    BINDINGS: ClassVar = [_APPEARANCE_BINDING]

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance without leaving the flow."""
        toggle_appearance(self.app)

    DEFAULT_CSS = tokenised(
        BASE_CSS
        + """
    #flow-top {
        dock: top;
        height: auto;
        width: 100%;
    }
    #flow-stage-strip { height: $cadrumo-band-height; width: 100%; }
    #flow-header {
        height: $cadrumo-band-height;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: $cadrumo-space-0 $cadrumo-space-1;
    }
    #flow-progress {
        height: $cadrumo-band-height;
        width: 100%;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        background: $surface;
        color: $text-muted;
    }
    /* #page-body carries no bespoke box rules: it is a `.cadrumo-panel`
       inside the shared `.cadrumo-scroll` host and `.cadrumo-column`, so
       its border, padding, margin and auto height come from the one panel
       definition every surface shares. */
    #page-prompt { text-style: bold; margin: $cadrumo-space-0; }
    #page-badge {
        background: $warning 30%;
        color: $warning;
        width: auto;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        margin: $cadrumo-space-0;
    }
    #page-help { color: $text-muted; text-style: italic; margin: $cadrumo-space-0; }
    #page-format-hint { color: $text-muted; margin: $cadrumo-space-0; }
    #page-failure-modes { color: $text-muted; margin: $cadrumo-space-0; }
    #page-legal-zone { color: $text-muted; text-style: italic; margin: $cadrumo-space-0; }
    #widget-area { margin: $cadrumo-space-0; height: auto; }
    #widget-area Input { border: $cadrumo-radius $accent; background: $background; }
    #widget-area RadioSet, #widget-area OptionList {
        border: $cadrumo-radius $panel;
        background: $background;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        height: auto;
        width: 100%;
    }
    #widget-area RadioButton { height: auto; }
    #widget-area OptionList > .option-list--option { padding: $cadrumo-space-0 $cadrumo-space-1; }
    #live-validation { color: $error; margin: $cadrumo-space-0; }
    #answer-echo { color: $success; text-style: bold; margin: $cadrumo-space-0; }
    #commit-verdicts { color: $error; margin: $cadrumo-space-0; }
    /* `auto`, never a pinned row: a button is three rows tall, so a
       one-row container clipped every label away and left three bare
       slabs on screen. Every sibling action row already sizes itself. */
    #nav-buttons {
        height: auto;
        align-horizontal: right;
        margin: $cadrumo-section $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0;
    }
    #nav-buttons Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
    #review-header {
        dock: top;
        height: $cadrumo-band-height;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: $cadrumo-space-0 $cadrumo-space-1;
    }
    #review-table {
        border: $cadrumo-radius $primary;
        background: $surface;
        margin: $cadrumo-space-0;
        /* 1fr, not auto. A DataTable is its own scroll container and is a
           real control the operator drives with the arrow keys, so it must
           be the one thing that scrolls here. At `height: auto` it grew to
           its full row count instead, so the Screen scrolled as well and
           the operator saw two vertical scrollbars for one list. */
        height: 1fr;
        width: 100%;
    }
    #review-blocking {
        color: $error;
        border: $cadrumo-radius $error;
        padding: $cadrumo-space-0 $cadrumo-space-1;
        margin: $cadrumo-space-0;
        width: 100%;
    }
    #review-save-note { color: $warning; margin: $cadrumo-space-0; }
    #btn-submit { margin: $cadrumo-space-0; }
    """
    )

    def __init__(
        self,
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        checkpoint_store: CheckpointStore | None = None,
        resume_state: FlowState | None = None,
        registered_values: Mapping[str, str] | None = None,
        on_answer_committed: Callable[[str, str], None] | None = None,
    ) -> None:
        """Build a flow projection, requiring a store when checkpointing is available."""
        super().__init__()
        if checkpoint_available(definition, mode) and checkpoint_store is None:
            raise FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context=_operator_flow_context(definition, mode),
            )
        self.definition = definition
        self.state: FlowState = resume_state if resume_state is not None else start_flow(definition, mode=mode)
        self._store = checkpoint_store
        self._widget_by_page_id: dict[str, FlowWidgetKind] = _collect_page_widgets(definition)
        """Widget kind per declared page id, so an answer's echo can be
        masked when the page collects a secret regardless of which zone
        renders it (question body, page header, review answer column)."""
        self.registered_values: dict[str, str] = dict(registered_values or {})
        """Domain-supplied display values currently on record, keyed by page
        key — rendered verbatim in the review table's registered column so
        the operator sees the in-flow answer beside the persisted fact."""
        self._on_answer_committed = on_answer_committed
        """Generic post-commit notification, fired after each successful engine
        answer commit with ``(page_key, canonical_committed_value)`` and before
        the frontend advances or re-renders. A locale-switch hook can
        re-activate the language and call :meth:`rebuild_for_locale` so the
        next page renders in the new language. Domain-blind by construction —
        never a language hook itself. The value may be a SECRET page's raw
        answer, so a consumer MUST NOT log it."""
        self.final_state: FlowState | None = None
        self.final_projection: ReviewProjection | None = None
        self.saved_and_exited = False

    @override
    def compose(self) -> ComposeResult:
        """Yield the region the flow's pages are mounted into.

        The entry renders its own document rather than delegating to a pushed
        sibling, which is what lets its bindings resolve and its CSS scope.
        """
        yield Vertical(id="flow-content")

    async def on_mount(self) -> None:
        """Install shared appearance support and show the current question page.

        The initial mount is AWAITED: `mount` is asynchronous, and a caller that
        interacts before it settles finds an empty page. That reads as a page
        whose widget simply holds no value -- a blank required answer commits
        nothing and the flow silently declines to advance -- rather than as a
        missing widget, so it must be awaited rather than left to a later
        refresh.
        """
        install_cadrumo_themes(self.app)
        await self._show(QuestionPane(self))

    def _show(self, pane: Vertical) -> AwaitMount:
        """Replace the mounted page with `pane`, returning its pending mount."""
        region = self.query_one("#flow-content", Vertical)
        region.remove_children()
        return region.mount(pane)

    def _pane[PaneT: Widget](self, kind: type[PaneT]) -> PaneT | None:
        """The mounted page when it is of `kind`, else None."""
        found = self.query(kind)
        return found.first() if found else None

    # ── engine access for screens ───────────────────────────────────────

    def cursor_entry(self) -> VisiblePage | None:
        """The visible-sequence entry the engine cursor addresses, if any."""
        for entry in visible_sequence(self.definition, self.state):
            if entry.key == self.state.cursor:
                return entry
        return None

    def _notify_answer_committed(self, page_key: str) -> None:
        if self._on_answer_committed is not None:
            self._on_answer_committed(page_key, self.state.answers.get(page_key, ""))

    def is_secret_page(self, page_key: str) -> bool:
        """Whether the page a key addresses collects a secret answer.

        Repeating-instance keys (``<group>#<index>.<page-id>``) resolve to
        their declared page id; a plain key is the page id itself.
        """
        base = page_key.rsplit(".", 1)[-1] if REPEATING_INSTANCE_SEPARATOR in page_key else page_key
        return self._widget_by_page_id.get(base) is FlowWidgetKind.SECRET

    # ── intents ─────────────────────────────────────────────────────────

    def commit_answer(self, raw: str, *, advance: bool = True) -> None:
        """Commit the answer for the cursor page.

        ``advance`` distinguishes the two commit shapes: an Input page
        commits-then-advances (``advance=True``), while a multi-select
        CHECKBOX stages every toggle in place (``advance=False``) so a
        second selection is not cut off by an immediate page exit — the
        page advances only on an explicit Next / escape / review intent.
        A staging commit still refreshes the echo and verdict zones so
        the operator sees the toggle land, but never re-mounts the widget
        area (which would discard the in-progress selection and focus).
        """
        entry = self.cursor_entry()
        if entry is None:
            return
        self.state = answer(self.definition, self.state, entry.key, raw)
        if entry.key not in self.state.verdicts:
            # Successful commit (no failing verdict for this page): notify
            # before advancing/re-rendering, so a locale-switch hook's
            # rebuild lands on the NEXT page. Fires for a staged CHECKBOX
            # toggle too (once per toggle).
            self._notify_answer_committed(entry.key)
        if not advance:
            self._refresh_answer_zones()
            return
        if entry.key in self.state.verdicts:
            self._rerender_question()
            return
        advanced = next_page(self.definition, self.state)
        if advanced.cursor == self.state.cursor and self._at_last_visible_page():
            self.state = advanced
            self.action_go_review()
            return
        self.state = advanced
        self._rerender_question()

    def navigate_back(self) -> None:
        """Move the engine cursor backwards and repaint the question projection."""
        self.state = back_page(self.definition, self.state)
        self._rerender_question()

    def action_next(self) -> None:
        """Advance via the clickable next affordance.

        A page holding an Input commits its current text first (the
        natural click-next expectation); committed-widget pages simply
        advance — their answers already landed on selection.
        """
        pane = self._pane(QuestionPane)
        if pane is not None:
            pending = pane.current_input_value()
            if pending is not None:
                self.commit_answer(pending)
                return
        advanced = next_page(self.definition, self.state)
        if advanced.cursor == self.state.cursor and self._at_last_visible_page():
            self.state = advanced
            self.action_go_review()
            return
        self.state = advanced
        self._rerender_question()

    def action_go_review(self) -> None:
        """Show the summary projection unless it is already mounted."""
        if self._pane(ReviewPane) is None:
            self._show(ReviewPane(self))

    def action_leave_review(self) -> None:
        """Return from the summary projection to the current question."""
        if self._pane(ReviewPane) is not None:
            self._show(QuestionPane(self))

    def edit_from_review(self, page_key: str) -> None:
        """Jump to a visible row, or offer the stale-orphan confirmed reset."""
        visible_keys = {entry.key for entry in visible_sequence(self.definition, self.state)}
        if page_key in visible_keys:
            self.state = jump_to(self.definition, self.state, page_key)
            self.action_leave_review()
            return
        if page_status(self.state, page_key) is PageStatus.STALE:
            # The recovery affordance: clearing the orphaned answer is the
            # only way an invisible stale row can resolve; it is explicit
            # here (a selected action on the marked row), never automatic.
            self.state = reset_page(self.definition, self.state, page_key)
            self._rerender_review()

    def action_reset_current(self) -> None:
        """Clear the current page answer through the engine and repaint it."""
        entry = self.cursor_entry()
        if entry is None:
            return
        self.state = reset_page(self.definition, self.state, entry.key)
        self._rerender_question()

    def action_restart(self) -> None:
        """Restart the engine flow after the screen has confirmed that intent."""
        self.state = restart_flow(self.definition, self.state)
        if self._pane(ReviewPane) is not None:
            self._show(QuestionPane(self))
            return
        self._rerender_question()

    def action_submit(self) -> None:
        """Finish the run only when the engine marks its review as eligible."""
        projection = review(self.definition, self.state)
        if not projection.submit_eligible:
            self._rerender_review()
            return
        self.final_projection = assert_submit_eligible(self.definition, self.state)
        self.final_state = self.state
        self.dismiss(None)

    def action_save_exit(self) -> None:
        """Persist the current checkpoint when the definition makes it available."""
        if not checkpoint_available(self.definition, self.state.mode):
            self._rerender_review()
            return
        if self._store is None:
            # The constructor fail-fast makes this unreachable when
            # checkpointing is available; the typed refusal is the
            # defence-in-depth backstop (mirroring the line frontend),
            # never a silent no-save exit — and it survives ``python -O``,
            # where a bare assert would vanish and reach ``save_checkpoint``
            # with ``None``.
            raise FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context=_operator_flow_context(self.definition, self.state.mode),
            )
        save_checkpoint(self.definition, self.state, self._store)
        self.final_state = self.state
        self.final_projection = review(self.definition, self.state)
        self.saved_and_exited = True
        self.dismiss(None)

    def rebuild_for_locale(self) -> None:
        """Re-render every screen under the newly-activated output language.

        The engine state is locale-blind, so nothing in it changes; every
        zone and :class:`~cadrumo.application.flows.copy.PageCopy` re-assembles at
        render, and each screen resolves its footer bindings at mount. Popping
        the mounted page with a fresh :class:`QuestionPane`
        therefore re-resolves all operator-facing copy — prompts, choices,
        buttons, and footer bindings — under the active locale, with no
        substrate cache to purge.

        The swap is deferred to after the current refresh so a caller invoking
        this from inside :meth:`commit_answer` (the post-commit locale-switch
        hook) does not tear the mounted screen out from under the commit's own
        advance/re-render; the fresh screen then mounts on the already-advanced
        cursor, so the NEXT page renders in the new language.
        """
        self.call_after_refresh(self._rebuild_screens_for_locale)

    def _rebuild_screens_for_locale(self) -> None:
        self._show(QuestionPane(self))

    # ── rendering plumbing ──────────────────────────────────────────────

    def _at_last_visible_page(self) -> bool:
        sequence = visible_sequence(self.definition, self.state)
        return bool(sequence) and sequence[-1].key == self.state.cursor

    def _rerender_question(self) -> None:
        pane = self._pane(QuestionPane)
        if pane is not None:
            pane.render_page()

    def _refresh_answer_zones(self) -> None:
        pane = self._pane(QuestionPane)
        if pane is not None:
            pane.refresh_answer_zones()

    def _rerender_review(self) -> None:
        pane = self._pane(ReviewPane)
        if pane is not None:
            pane.render_review()


def _collect_page_widgets(definition: FlowDefinition) -> dict[str, FlowWidgetKind]:
    """Map every declared page id to its widget kind (repeating pages included)."""
    widgets: dict[str, FlowWidgetKind] = {}
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage):
                widgets[item.id] = item.widget
            else:
                for page in item.pages:
                    widgets[page.id] = page.widget
    return widgets


def run_flow_tui(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    checkpoint_store: CheckpointStore | None = None,
    resume_state: FlowState | None = None,
    registered_values: Mapping[str, str] | None = None,
    on_answer_committed: Callable[[str, str], None] | None = None,
    on_screen_ready: Callable[[FlowScreen], None] | None = None,
) -> tuple[FlowState, ReviewProjection]:
    """Run the full-screen frontend to completion and return the outcome.

    Returns the final state and projection after a submit or a
    save-and-exit; a run abandoned without either raises so callers
    never mistake an aborted flow for a completed one.

    ``on_screen_ready`` is invoked with the constructed :class:`FlowScreen`
    after construction and before the host runs, so a caller can capture the
    screen handle to drive a frontend affordance — the locale rebuild
    (:meth:`FlowScreen.rebuild_for_locale`) from inside its
    ``on_answer_committed`` hook — without constructing the surface itself and
    thereby duplicating this runner's abandoned-run guard. The handle is
    for presentation affordances only: a caller MUST NOT drive the engine
    (commit answers, navigate, submit) through it; the runner retains sole
    ownership of the run lifecycle and the abandonment refusal.

    The surface is a screen, so a standalone run mounts it in the shared
    host rather than being an application itself. A root shell navigating to
    the flow pushes the same screen and never reaches this runner.
    """
    screen = FlowScreen(
        definition,
        mode=mode,
        checkpoint_store=checkpoint_store,
        resume_state=resume_state,
        registered_values=registered_values,
        on_answer_committed=on_answer_committed,
    )
    if on_screen_ready is not None:
        on_screen_ready(screen)
    ScreenHostApp(screen).run()
    if screen.final_state is None or screen.final_projection is None:
        raise FlowCheckpointError(
            translated_message="flows.errors.tui_abandoned",
            context=_operator_flow_context(definition, mode),
        )
    return screen.final_state, screen.final_projection


_TEXTUAL_INPUT_WIDGETS = frozenset(
    {
        FlowWidgetKind.TEXT,
        FlowWidgetKind.SECRET,
        FlowWidgetKind.INTEGER,
        FlowWidgetKind.PATH,
        FlowWidgetKind.DATE,
        FlowWidgetKind.DECIMAL,
    },
)


def _operator_confirm_answer(page: FlowPage, raw: str) -> str | None:
    if page.widget is not FlowWidgetKind.CONFIRM:
        return None
    parsed = parse_bool(raw)
    if parsed is None:
        return None
    return tr("flows.confirm.yes" if parsed else "flows.confirm.no")


def _operator_choice_answer(page: FlowPage, raw: str) -> str | None:
    if page.widget in {FlowWidgetKind.SELECT, FlowWidgetKind.COMPARE_SELECT, FlowWidgetKind.CHECKBOX}:
        labels = {choice.value: choice.label for choice in assemble_page_copy(page).choices}
        tokens = raw.split(",") if page.widget is FlowWidgetKind.CHECKBOX else [raw]
        if any(token not in labels for token in tokens):
            return tr("flows.tui.choice_unavailable")
        return ", ".join(labels[token] for token in tokens)
    return None


def _operator_answer(page: FlowPage, raw: str) -> str:
    """Render a committed answer without exposing a closed-choice token."""
    if not raw:
        return ""
    confirm_answer = _operator_confirm_answer(page, raw)
    if confirm_answer is not None:
        return confirm_answer
    if page.widget is FlowWidgetKind.COMPARE_SELECT and raw == DEFER_TOKEN:
        return tr("flows.compare_select.defer_label")
    choice_answer = _operator_choice_answer(page, raw)
    if choice_answer is not None:
        return choice_answer
    return raw


def _operator_verdict(
    verdict: ValidationVerdict,
    *,
    prompts: Mapping[str, str],
    current_prompt: str,
    choices: Mapping[str, str],
) -> str:
    """Resolve one verdict after replacing machine identifiers with copy."""
    context = dict(verdict.context)
    for key in ("page_id", "page_key", "page"):
        if key in context:
            context[key] = prompts.get(str(context[key]), current_prompt)
    fields = _string_list(context.get("fields"))
    if fields is not None:
        context["fields"] = [prompts.get(value, tr("flows.review.question_unavailable")) for value in fields]
    choice_values = _string_list(context.get("choices"))
    if choice_values is not None:
        context["choices"] = [choices.get(value, tr("flows.tui.choice_unavailable")) for value in choice_values]
    return tr(verdict.message_key or "", **context)


_OBJECT_LIST_ADAPTER = TypeAdapter(list[object])


def _string_list(value: object | None) -> list[str] | None:
    """Validate and stringify an optional verdict-context list."""
    if value is None:
        return None
    try:
        items = _OBJECT_LIST_ADAPTER.validate_python(value, strict=True)
    except ValidationError:
        return None
    return [str(item) for item in items]


def _confirm_restart_dialog() -> ConfirmScreen:
    """Build the single flow-specific restart confirmation."""
    return ConfirmScreen(
        title=tr("flows.tui.confirm_restart.title"),
        message=tr("flows.tui.confirm_restart.message"),
        confirm_label=tr("flows.tui.confirm_restart.confirm"),
        cancel_label=tr("flows.tui.confirm_restart.cancel"),
    )


class _FlowPane(TypedAppAccess, Vertical):
    """What both flow pages share: their owner, and the intents that leave them.

    The question and review pages are two projections of one flow run, so the
    handle back to the presenter and the three intents that are not about the
    page's own content -- restart, its confirmation, and save-and-exit -- are
    identical on both. They were byte-identical duplicates before this base
    existed; one concept written twice is one concept that can drift once.

    Everything that DOES differ stays on the pages: `compose`, `on_mount`,
    `on_button_pressed` and `_localize_bindings` are each genuinely per-page.
    """

    def __init__(self, presenter: FlowPresenter) -> None:
        super().__init__()
        self._presenter = presenter

    @property
    def presenter(self) -> FlowPresenter:
        """Return the typed flow application that owns this projection."""
        return self._presenter

    def action_restart_flow(self) -> None:
        self.app.push_screen(_confirm_restart_dialog(), self._apply_restart_decision)

    def _apply_restart_decision(self, confirmed: bool | None) -> None:
        if confirmed:
            self.presenter.action_restart()

    def action_save_exit(self) -> None:
        self.presenter.action_save_exit()


class QuestionPane(_FlowPane):
    """Render the cursor page and forward answer intents to the flow app."""

    BINDINGS: ClassVar = [
        Binding("escape", "go_back", ""),
        Binding("f2", "go_review", ""),
        Binding("ctrl+r", "reset_page", ""),
        Binding("ctrl+n", "restart_flow", ""),
        Binding("ctrl+s", "save_exit", ""),
    ]

    def _build_stage_strip(self, *, current_index: int = 0) -> StageNavigationStrip:
        """Build the section-level stage strip from the flow's own titles.

        One stage per declared `FlowSection`, in the definition's own
        order -- the strip renders what the application already decided
        the sections are; it introduces no section ordering or grouping
        of its own.
        """
        titles = assemble_section_titles(self._presenter.definition)
        stages = [titles.get(section.id, section.id) for section in self._presenter.definition.sections]
        return StageNavigationStrip(stages, current_index=current_index, id="flow-stage-strip")

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="flow-top"):
            yield Static(id="flow-header")
            yield self._build_stage_strip()
            yield ProgressBar(id="flow-progress", show_eta=False)
        with (
            ContentScroll(id="page-scroll", classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="page-body", classes="cadrumo-panel"),
        ):
            yield Label("", id="page-prompt")
            yield Static("", id="page-badge")
            yield Static("", id="page-help")
            yield Static("", id="page-format-hint")
            yield Static("", id="page-failure-modes")
            yield Static("", id="page-legal-zone")
            yield Vertical(id="widget-area")
            yield Static("", id="live-validation")
            yield Static("", id="answer-echo")
            yield Static("", id="commit-verdicts")
            with Horizontal(id="nav-buttons"):
                yield Button(tr("flows.tui.button_back"), id="btn-back")
                yield Button(tr("flows.tui.button_next"), id="btn-next", variant="primary")
                yield Button(f"{tr('flows.tui.button_review')} (F2)", id="btn-review", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        """Resolve runtime binding copy and render the engine cursor's page."""
        self._localize_bindings()
        self.render_page()

    def _localize_bindings(self) -> None:
        localize_key_descriptions(
            self,
            {
                "go_back": tr("flows.tui.binding_back"),
                "go_review": tr("flows.tui.binding_review"),
                "reset_page": tr("flows.tui.binding_reset"),
                "restart_flow": tr("flows.tui.binding_restart"),
                "save_exit": tr("flows.tui.binding_save_exit"),
            },
        )

    def render_page(self) -> None:
        """Render every zone for the page the engine cursor addresses."""
        presenter = self.presenter
        entry = presenter.cursor_entry()
        if entry is None:
            presenter.action_go_review()
            return
        copy = assemble_page_copy(entry.page)
        self._render_header(presenter, entry)
        self._render_body(presenter, entry, copy)
        self._mount_widget(presenter, entry, copy)

    def _render_header(self, presenter: FlowPresenter, entry: VisiblePage) -> None:
        sequence = visible_sequence(presenter.definition, presenter.state)
        position = next((index for index, item in enumerate(sequence) if item.key == entry.key), 0)
        section_title = assemble_section_titles(presenter.definition).get(entry.section_id)
        if section_title is None:
            section_title = tr("flows.tui.section_unavailable")
        flow_title = resolve_copy(presenter.definition.title)
        if section_title == flow_title:
            header = tr(
                "flows.tui.header_single_section",
                flow=flow_title,
                position=position + 1,
                total=len(sequence),
            )
        else:
            header = tr(
                "flows.tui.header",
                flow=flow_title,
                position=position + 1,
                total=len(sequence),
                section=section_title,
            )
        self.query_one("#flow-header", Static).update(header)
        self.query_one("#flow-progress", ProgressBar).update(total=len(sequence), progress=position + 1)
        self.query_one("#page-body", Vertical).border_title = section_title
        section_index = next(
            (index for index, section in enumerate(presenter.definition.sections) if section.id == entry.section_id),
            0,
        )
        self.query_one("#flow-stage-strip", StageNavigationStrip).set_current_index(section_index)

    def _render_body(self, presenter: FlowPresenter, entry: VisiblePage, copy: PageCopy) -> None:
        self.query_one("#page-prompt", Label).update(copy.prompt)
        badge_key = "flows.progress.required" if entry.page.required else "flows.progress.optional"
        self.query_one("#page-badge", Static).update(tr(badge_key))
        self._set_zone("#page-help", copy.help or "")
        self._set_zone(
            "#page-format-hint",
            f"▸ {tr('flows.progress.format_hint', hint=copy.format_hint)}" if copy.format_hint else "",
        )
        self._set_zone(
            "#page-failure-modes",
            "\n".join(tr("flows.progress.failure_mode", text=text) for text in copy.failure_modes),
        )
        self._set_zone(
            "#page-legal-zone",
            "\n".join(f"{ref.ref} — {ref.label}" if ref.label else ref.ref for ref in copy.legal_zone),
        )
        self.query_one("#answer-echo", Static).update(self._answer_echo_text(presenter, entry))
        self.query_one("#commit-verdicts", Static).update(self._commit_verdicts_text(presenter, entry))
        self.query_one("#live-validation", Static).update("")

    def _set_zone(self, selector: str, content: str) -> None:
        zone = self.query_one(selector, Static)
        zone.update(content)
        zone.display = bool(content)

    @staticmethod
    def _answer_echo_text(presenter: FlowPresenter, entry: VisiblePage) -> str:
        current = presenter.state.answers.get(entry.key)
        if not current:
            return ""
        marker = (
            tr("flows.progress.current_answer_secret")
            if entry.page.widget is FlowWidgetKind.SECRET
            else tr("flows.progress.current_answer", value=_operator_answer(entry.page, current))
        )
        return f"✓ {marker}"

    @staticmethod
    def _commit_verdicts_text(presenter: FlowPresenter, entry: VisiblePage) -> str:
        verdicts = presenter.state.verdicts.get(entry.key, ())
        copy = assemble_page_copy(entry.page)
        prompts = {
            visible.key: assemble_page_copy(visible.page).prompt
            for visible in visible_sequence(presenter.definition, presenter.state)
        }
        choices = {choice.value: choice.label for choice in copy.choices}
        return "\n".join(
            _operator_verdict(
                verdict,
                prompts=prompts,
                current_prompt=copy.prompt,
                choices=choices,
            )
            for verdict in verdicts
            if verdict.message_key
        )

    def refresh_answer_zones(self) -> None:
        """Refresh derived answer zones without remounting the input widget."""
        presenter = self.presenter
        entry = presenter.cursor_entry()
        if entry is None:
            return
        self.query_one("#answer-echo", Static).update(self._answer_echo_text(presenter, entry))
        self.query_one("#commit-verdicts", Static).update(self._commit_verdicts_text(presenter, entry))
        self.query_one("#live-validation", Static).update("")

    def _mount_widget(self, presenter: FlowPresenter, entry: VisiblePage, copy: PageCopy) -> None:
        area = self.query_one("#widget-area", Vertical)
        area.remove_children()
        widget_kind = entry.page.widget
        current = presenter.state.answers.get(entry.key) or entry.page.default or ""
        if widget_kind in _TEXTUAL_INPUT_WIDGETS:
            field = Input(
                value="" if widget_kind is FlowWidgetKind.SECRET else current,
                password=widget_kind is FlowWidgetKind.SECRET,
            )
            area.mount(field)
            field.focus()
            return
        if widget_kind is FlowWidgetKind.CONFIRM:
            radio = RadioSet(
                RadioButton(tr("flows.confirm.yes"), value=parse_bool(current) is True, name="true"),
                RadioButton(tr("flows.confirm.no"), value=parse_bool(current) is False, name="false"),
            )
            area.mount(radio)
            radio.focus()
            return
        option_list = OptionList(*self._choice_options(copy, widget_kind, current))
        area.mount(option_list)
        option_list.focus()

    def _choice_options(self, copy: PageCopy, widget_kind: FlowWidgetKind, current: str) -> list[Option]:
        selected = {token for token in current.split(",") if token} if widget_kind is FlowWidgetKind.CHECKBOX else None
        options: list[Option] = []
        for index, choice in enumerate(copy.choices, start=1):
            is_selected = choice.value in selected if selected is not None else choice.value == current
            options.append(Option(self._option_prompt(index, choice, widget_kind, chosen=is_selected), id=choice.value))
        if widget_kind is FlowWidgetKind.COMPARE_SELECT:
            options.append(
                Option(
                    self._defer_prompt(len(copy.choices) + 1, chosen=current == DEFER_TOKEN),
                    id=DEFER_TOKEN,
                ),
            )
        return options

    @staticmethod
    def _glyph(widget_kind: FlowWidgetKind, *, chosen: bool) -> str:
        if widget_kind is FlowWidgetKind.CHECKBOX:
            return "[x]" if chosen else "[ ]"
        return "(•)" if chosen else "( )"

    def _option_prompt(self, number: int, choice: ChoiceCopy, widget_kind: FlowWidgetKind, *, chosen: bool) -> Text:
        text = Text(f"{number}. {self._glyph(widget_kind, chosen=chosen)} {choice.label}")
        details = [detail for detail in (choice.provenance, choice.description) if detail]
        text.append("\n   ")
        text.append(" · ".join(details) if details else " ", style="dim")
        return text

    def _defer_prompt(self, number: int, *, chosen: bool) -> Text:
        glyph = "(•)" if chosen else "( )"
        text = Text(f"{number}. {glyph} {tr('flows.compare_select.defer_label')}")
        text.append("\n   ")
        text.append(" ", style="dim")
        return text

    def on_input_changed(self, event: Input.Changed) -> None:
        presenter = self.presenter
        entry = presenter.cursor_entry()
        if entry is None:
            return
        _canonical, verdict = validate_widget_shape(entry.page, event.value)
        copy = assemble_page_copy(entry.page)
        hint = (
            ""
            if verdict.ok
            else "✗ "
            + _operator_verdict(
                verdict,
                prompts={entry.key: copy.prompt},
                current_prompt=copy.prompt,
                choices={},
            )
        )
        self.query_one("#live-validation", Static).update(hint)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.presenter.commit_answer(event.value)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.name:
            self.presenter.commit_answer(event.pressed.name)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self._activate_choice(event.option.id)

    def on_key(self, event: Key) -> None:
        if not event.key.isdigit() or event.key == "0":
            return
        option_lists = self.query_one("#widget-area", Vertical).query(OptionList)
        if not option_lists:
            return
        option_list = option_lists.first()
        index = int(event.key) - 1
        if 0 <= index < option_list.option_count:
            event.stop()
            option_id = option_list.get_option_at_index(index).id
            if option_id is not None:
                self._activate_choice(option_id)

    def _activate_choice(self, value: str) -> None:
        entry = self.presenter.cursor_entry()
        if entry is None:
            return
        if entry.page.widget is FlowWidgetKind.CHECKBOX:
            copy = assemble_page_copy(entry.page)
            selected = {token for token in self.presenter.state.answers.get(entry.key, "").split(",") if token}
            selected.symmetric_difference_update({value})
            ordered = ",".join(choice.value for choice in copy.choices if choice.value in selected)
            self.presenter.commit_answer(ordered, advance=False)
            self._refresh_checkbox_glyphs(entry, copy)
            return
        self.presenter.commit_answer(value)

    def _refresh_checkbox_glyphs(self, entry: VisiblePage, copy: PageCopy) -> None:
        option_list = self.query_one("#widget-area", Vertical).query_one(OptionList)
        selected = {token for token in self.presenter.state.answers.get(entry.key, "").split(",") if token}
        for index, choice in enumerate(copy.choices, start=1):
            option_list.replace_option_prompt_at_index(
                index - 1,
                self._option_prompt(index, choice, FlowWidgetKind.CHECKBOX, chosen=choice.value in selected),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.presenter.navigate_back()
        elif event.button.id == "btn-next":
            self.presenter.action_next()
        elif event.button.id == "btn-review":
            self.presenter.action_go_review()

    def current_input_value(self) -> str | None:
        inputs = self.query_one("#widget-area", Vertical).query(Input)
        return inputs.first().value if inputs else None

    def action_go_back(self) -> None:
        self.presenter.navigate_back()

    def action_go_review(self) -> None:
        self.presenter.action_go_review()

    def action_reset_page(self) -> None:
        self.presenter.action_reset_current()


_STATUS_GLYPHS: dict[PageStatus, str] = {
    PageStatus.ANSWERED: "✔",
    PageStatus.UNANSWERED: "○",
    PageStatus.INVALID: "✗",
    PageStatus.STALE: "⚠",
    PageStatus.DEFERRED: "…",
}

_SECTION_HEADING_PREFIX = "\x00section\x00"


class _ReviewTable(DataTable[str]):
    """Typed flow-review table with string cell values."""


class ReviewPane(_FlowPane):
    """Render a clickable summary of every question in the flow."""

    BINDINGS: ClassVar = [
        Binding("escape", "back_to_question", ""),
        Binding("s", "submit_flow", ""),
        Binding("ctrl+s", "save_exit", ""),
        Binding("ctrl+n", "restart_flow", ""),
    ]

    @override
    def compose(self) -> ComposeResult:
        titles = assemble_section_titles(self._presenter.definition)
        stages = [titles.get(section.id, section.id) for section in self._presenter.definition.sections]
        stages.append(tr("flows.review.header_tui_stage_label"))
        yield StageNavigationStrip(stages, current_index=len(stages) - 1, id="flow-stage-strip")
        yield Static(id="review-header")
        yield _ReviewTable(id="review-table", cursor_type="row")
        yield Static(id="review-blocking")
        yield Static(id="review-save-note")
        yield Button(tr("flows.review.action_submit"), id="btn-submit", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        """Configure localized table columns and render the current review."""
        self._localize_bindings()
        table = self.query_one("#review-table", _ReviewTable)
        table.zebra_stripes = True
        table.add_columns(
            tr("flows.review.column_status"),
            tr("flows.review.column_question"),
            tr("flows.review.column_answer"),
            tr("flows.review.column_registered"),
        )
        self.render_review()

    def _localize_bindings(self) -> None:
        localize_key_descriptions(
            self,
            {
                "back_to_question": tr("flows.tui.binding_return"),
                "submit_flow": tr("flows.tui.binding_submit"),
                "save_exit": tr("flows.tui.binding_save_exit"),
                "restart_flow": tr("flows.tui.binding_restart"),
            },
        )

    def render_review(self) -> None:
        """Project the engine review into the table, notices, and submit control."""
        presenter = self.presenter
        projection = review(presenter.definition, presenter.state)
        prompts = self._prompts_by_key(presenter)
        self.query_one("#review-header", Static).update(
            tr(
                "flows.review.header_tui",
                answered=projection.answered_count,
                remaining=projection.required_remaining,
                eligible=tr("flows.confirm.yes" if projection.submit_eligible else "flows.confirm.no"),
            ),
        )
        table = self.query_one("#review-table", _ReviewTable)
        table.clear()
        self._fill_table(table, presenter, projection, prompts)
        choice_labels = {
            choice.value: choice.label
            for entry in visible_sequence(presenter.definition, presenter.state)
            for choice in assemble_page_copy(entry.page).choices
        }
        blocking_text = "\n".join(
            _operator_verdict(
                verdict,
                prompts=prompts,
                current_prompt=tr("flows.review.question_unavailable"),
                choices=choice_labels,
            )
            for verdict in projection.blocking
            if verdict.message_key
        )
        blocking = self.query_one("#review-blocking", Static)
        blocking.update(blocking_text)
        blocking.display = bool(blocking_text)
        if checkpoint_available(presenter.definition, presenter.state.mode):
            save_note = ""
        else:
            mode_label = tr(
                "flows.review.mode_create" if presenter.state.mode is FlowMode.CREATE else "flows.review.mode_modify",
            )
            save_note = tr("flows.review.save_unavailable", mode=mode_label)
        self.query_one("#review-save-note", Static).update(save_note)
        self.query_one("#btn-submit", Button).disabled = not projection.submit_eligible
        table.focus()

    def _fill_table(
        self,
        table: _ReviewTable,
        presenter: FlowPresenter,
        projection: ReviewProjection,
        prompts: dict[str, str],
    ) -> None:
        """Add each reviewed page under a section heading when useful."""
        section_titles = self._section_titles(presenter)
        multi_section = len({row.section_id for row in projection.rows}) > 1
        current_section: str | None = None
        for row in projection.rows:
            if multi_section and row.section_id != current_section:
                current_section = row.section_id
                table.add_row(
                    "",
                    section_titles.get(row.section_id, tr("flows.review.section_unavailable")),
                    "",
                    "",
                    key=f"{_SECTION_HEADING_PREFIX}{row.section_id}",
                )
            table.add_row(
                _STATUS_GLYPHS.get(row.status, "?"),
                self._prompt_cell(row, prompts),
                self._answer_cell(presenter, row.key),
                self._registered_cell(presenter, row.key),
                key=row.key,
            )

    @staticmethod
    def _prompt_cell(row: ReviewRow, prompts: dict[str, str]) -> str:
        prompt = prompts.get(row.key)
        if prompt is None:
            return tr("flows.review.question_unavailable")
        if not row.jumpable:
            return f"{prompt} {tr('flows.review.orphan_marker')}".strip()
        return prompt

    @staticmethod
    def _answer_cell(presenter: FlowPresenter, page_key: str) -> str:
        answer_value = presenter.state.answers.get(page_key, "")
        if answer_value and presenter.is_secret_page(page_key):
            return tr("flows.progress.current_answer_secret")
        entry = next(
            (item for item in visible_sequence(presenter.definition, presenter.state) if item.key == page_key), None
        )
        return answer_value if entry is None else _operator_answer(entry.page, answer_value)

    @staticmethod
    def _registered_cell(presenter: FlowPresenter, page_key: str) -> str:
        registered = presenter.registered_values.get(page_key, "")
        if registered and presenter.is_secret_page(page_key):
            return tr("flows.progress.current_answer_secret")
        entry = next(
            (item for item in visible_sequence(presenter.definition, presenter.state) if item.key == page_key), None
        )
        return registered if entry is None else _operator_answer(entry.page, registered)

    def _prompts_by_key(self, presenter: FlowPresenter) -> dict[str, str]:
        return {
            entry.key: assemble_page_copy(entry.page).prompt
            for entry in visible_sequence(presenter.definition, presenter.state)
        }

    @staticmethod
    def _section_titles(presenter: FlowPresenter) -> dict[str, str]:
        return assemble_section_titles(presenter.definition)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        page_key = event.row_key.value
        if page_key is None or page_key.startswith(_SECTION_HEADING_PREFIX):
            return
        self.presenter.edit_from_review(page_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self.presenter.action_submit()

    def action_back_to_question(self) -> None:
        self.presenter.action_leave_review()

    def action_submit_flow(self) -> None:
        self.presenter.action_submit()


def select_flow_frontend(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    capability: FrontendCapability,
    checkpoint_store: CheckpointStore | None = None,
    resume_state: FlowState | None = None,
    registered_values: Mapping[str, str] | None = None,
) -> FlowScreen | LineFlowFrontend:
    """Construct the one frontend supported by the classified host."""
    if capability is FrontendCapability.NON_INTERACTIVE:
        raise FlowUnsupportedConsoleError(
            translated_message="flows.errors.unsupported_console",
        )
    if capability is FrontendCapability.FULL_SCREEN:
        return FlowScreen(
            definition,
            mode=mode,
            checkpoint_store=checkpoint_store,
            resume_state=resume_state,
            registered_values=registered_values,
        )
    return LineFlowFrontend(definition, checkpoint_store=checkpoint_store)


__all__ = ["FlowPresenter", "FlowScreen", "run_flow_tui", "select_flow_frontend"]
