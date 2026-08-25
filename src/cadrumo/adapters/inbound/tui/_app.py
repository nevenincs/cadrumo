"""The Textual app driver: engine transitions in, screen renders out.

The app owns exactly two responsibilities: hold the current
:class:`FlowState` (replacing it wholesale on every engine transition)
and route screen intents onto engine calls. It never interprets an
answer, never evaluates visibility, and never decides eligibility —
those are :mod:`cadrumo.application.flows` calls whose results the
screens render. The intent surface mirrors the substrate's closed
:class:`~cadrumo.core.flows.FlowIntentKind` set.

Checkpoint honesty mirrors the line-mode frontend: a mode whose
definition declares checkpointing AVAILABLE demands an injected store at
construction (fail fast, before any answer could be lost), and the
declared no-op arm disables save-and-exit with an explicit line on the
review screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import App
from textual.binding import Binding

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from ....application.flows import (
    FlowCheckpointError as _FlowCheckpointError,
)
from ....application.flows import (
    FlowError as _FlowError,
)
from ....application.flows import (
    FlowPage,
    FlowRepeatingGroup,
    ReviewProjection,
    answer,
    assert_submit_eligible,
    back_page,
    checkpoint_available,
    jump_to,
    next_page,
    page_status,
    reset_page,
    resolve_copy,
    restart_flow,
    review,
    save_checkpoint,
    start_flow,
    visible_sequence,
)
from ....core.flows import REPEATING_INSTANCE_SEPARATOR, FlowMode, FlowWidgetKind, PageStatus
from ....core.i18n import tr
from ....entrypoints.tui.components.theme import BASE_CSS as _BASE_CSS
from ....entrypoints.tui.components.theme import install_cadrumo_themes, toggle_appearance
from ._question_screen import QuestionScreen
from ._review_screen import ReviewScreen

if TYPE_CHECKING:
    from ....application.flows import CheckpointStore, FlowDefinition, FlowState, VisiblePage


def _operator_flow_context(definition: FlowDefinition, mode: FlowMode) -> dict[str, str]:
    """Return error interpolation values containing presentation copy only."""
    return {
        "flow_id": resolve_copy(definition.title),
        "mode": tr("flows.review.mode_create" if mode is FlowMode.CREATE else "flows.review.mode_modify"),
    }


class FlowTuiApp(App[None]):
    """Full-screen projection of one flow run."""

    CSS = (
        _BASE_CSS
        + """
    #flow-top {
        dock: top;
        height: 2;
        width: 100%;
    }
    #flow-header {
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    #flow-progress {
        height: 1;
        width: 100%;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    /* #page-body carries no bespoke box rules: it is a `.cadrumo-panel`
       inside the shared `.cadrumo-scroll` host and `.cadrumo-column`, so
       its border, padding, margin and auto height come from the one panel
       definition every surface shares. */
    #page-prompt { text-style: bold; margin: 0; }
    #page-badge {
        background: $warning 30%;
        color: $warning;
        width: auto;
        padding: 0 1;
        margin: 0;
    }
    #page-help { color: $text-muted; text-style: italic; margin: 0; }
    #page-format-hint { color: $text-muted; margin: 0; }
    #page-failure-modes { color: $text-muted; margin: 0; }
    #page-legal-zone { color: $text-muted; text-style: italic; margin: 0; }
    #widget-area { margin: 0; height: auto; }
    #widget-area Input { border: tall $accent; background: $background; }
    #widget-area RadioSet, #widget-area OptionList {
        border: round $panel;
        background: $background;
        padding: 0 1;
        height: auto;
        width: 100%;
    }
    #widget-area RadioButton { height: auto; }
    #widget-area OptionList > .option-list--option { padding: 0 1; }
    #live-validation { color: $error; margin: 0; }
    #answer-echo { color: $success; text-style: bold; margin: 0; }
    #commit-verdicts { color: $error; margin: 0; }
    #nav-buttons { height: 1; align-horizontal: right; margin: 0; }
    #nav-buttons Button { margin: 0 0 0 1; }
    #review-header {
        dock: top;
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    #review-table {
        border: round $primary;
        background: $surface;
        margin: 0;
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
        border: round $error;
        padding: 0 1;
        margin: 0;
        width: 100%;
    }
    #review-save-note { color: $warning; margin: 0; }
    #btn-submit { dock: bottom; margin: 0; }
    """
    )

    BINDINGS: ClassVar = [
        # F2 is the review intent on the question screen; F3 is free across
        # every surface. Hidden, and description-free: an app-level BINDINGS
        # list resolves at import time, so a ``tr`` call here would freeze the
        # import-time language into the footer the screens deliberately defer.
        Binding("f3", "toggle_appearance", "", show=False),
    ]

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
        super().__init__()
        if checkpoint_available(definition, mode) and checkpoint_store is None:
            raise _FlowCheckpointError(
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

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.push_screen(QuestionScreen())

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance without leaving the flow.

        The engine state is appearance-blind, so nothing re-renders beyond
        the stylesheet: the operator keeps their cursor, answers, and
        scroll position across the switch.
        """
        toggle_appearance(self)

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
        self.state = back_page(self.definition, self.state)
        self._rerender_question()

    def action_next(self) -> None:
        """Advance via the clickable next affordance.

        A page holding an Input commits its current text first (the
        natural click-next expectation); committed-widget pages simply
        advance — their answers already landed on selection.
        """
        screen = self.screen
        if isinstance(screen, QuestionScreen):
            pending = screen.current_input_value()
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
        if not isinstance(self.screen, ReviewScreen):
            self.push_screen(ReviewScreen())

    def action_leave_review(self) -> None:
        if isinstance(self.screen, ReviewScreen):
            self.pop_screen()
            self._rerender_question()

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
        entry = self.cursor_entry()
        if entry is None:
            return
        self.state = reset_page(self.definition, self.state, entry.key)
        self._rerender_question()

    def action_restart(self) -> None:
        self.state = restart_flow(self.definition, self.state)
        if isinstance(self.screen, ReviewScreen):
            self.pop_screen()
        self._rerender_question()

    def action_submit(self) -> None:
        projection = review(self.definition, self.state)
        if not projection.submit_eligible:
            self._rerender_review()
            return
        self.final_projection = assert_submit_eligible(self.definition, self.state)
        self.final_state = self.state
        self.exit()

    def action_save_exit(self) -> None:
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
            raise _FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context=_operator_flow_context(self.definition, self.state.mode),
            )
        save_checkpoint(self.definition, self.state, self._store)
        self.final_state = self.state
        self.final_projection = review(self.definition, self.state)
        self.saved_and_exited = True
        self.exit()

    def rebuild_for_locale(self) -> None:
        """Re-render every screen under the newly-activated output language.

        The engine state is locale-blind, so nothing in it changes; every
        zone and :class:`~cadrumo.application.flows.PageCopy` re-assembles at
        render, and each screen resolves its footer bindings at mount. Popping
        back to a single screen and pushing a fresh :class:`QuestionScreen`
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
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(QuestionScreen())

    # ── rendering plumbing ──────────────────────────────────────────────

    def _at_last_visible_page(self) -> bool:
        sequence = visible_sequence(self.definition, self.state)
        return bool(sequence) and sequence[-1].key == self.state.cursor

    def _rerender_question(self) -> None:
        screen = self.screen
        if isinstance(screen, QuestionScreen):
            screen.render_page()

    def _refresh_answer_zones(self) -> None:
        screen = self.screen
        if isinstance(screen, QuestionScreen):
            screen.refresh_answer_zones()

    def _rerender_review(self) -> None:
        screen = self.screen
        if isinstance(screen, ReviewScreen):
            screen.render_review()


def require_flow_app(app: object) -> FlowTuiApp:
    """Narrow a screen's ``self.app`` to the owning :class:`FlowTuiApp`.

    The runtime object is always the owning app; a typed refusal (rather
    than a bare ``assert`` that ``python -O`` strips) keeps the guard loud
    if a screen is ever mounted under a foreign app.
    """
    if not isinstance(app, FlowTuiApp):
        raise _FlowError(
            translated_message="flows.errors.unexpected_app_type",
            context={"expected": FlowTuiApp.__name__, "actual": type(app).__name__},
        )
    return app


def _collect_page_widgets(definition: FlowDefinition) -> dict[str, FlowWidgetKind]:
    """Map every declared page id to its widget kind (repeating pages included)."""
    widgets: dict[str, FlowWidgetKind] = {}
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage):
                widgets[item.id] = item.widget
            elif isinstance(item, FlowRepeatingGroup):
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
    on_app_ready: Callable[[FlowTuiApp], None] | None = None,
) -> tuple[FlowState, ReviewProjection]:
    """Run the full-screen frontend to completion and return the outcome.

    Returns the final state and projection after a submit or a
    save-and-exit; a run abandoned without either raises so callers
    never mistake an aborted flow for a completed one.

    ``on_app_ready`` is invoked with the constructed :class:`FlowTuiApp`
    after construction and before :func:`~textual.app.App.run`, so a caller can
    capture the app handle to drive a frontend affordance — the locale
    rebuild (:meth:`FlowTuiApp.rebuild_for_locale`) from inside its
    ``on_answer_committed`` hook — without constructing the app itself and
    thereby duplicating this runner's abandoned-run guard. The handle is
    for presentation affordances only: a caller MUST NOT drive the engine
    (commit answers, navigate, submit) through it; the runner retains sole
    ownership of the run lifecycle and the abandonment refusal.
    """
    app = FlowTuiApp(
        definition,
        mode=mode,
        checkpoint_store=checkpoint_store,
        resume_state=resume_state,
        registered_values=registered_values,
        on_answer_committed=on_answer_committed,
    )
    if on_app_ready is not None:
        on_app_ready(app)
    app.run()
    if app.final_state is None or app.final_projection is None:
        raise _FlowCheckpointError(
            translated_message="flows.errors.tui_abandoned",
            context=_operator_flow_context(definition, mode),
        )
    return app.final_state, app.final_projection


__all__ = ["FlowTuiApp", "require_flow_app", "run_flow_tui"]
