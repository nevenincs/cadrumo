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

from typing import TYPE_CHECKING

from textual.app import App

from cadrumo.application.flows import (
    FlowCheckpointError as _FlowCheckpointError,
)
from cadrumo.application.flows import (
    ReviewProjection,
    answer,
    assert_submit_eligible,
    back_page,
    checkpoint_available,
    jump_to,
    next_page,
    page_status,
    reset_page,
    restart_flow,
    review,
    save_checkpoint,
    start_flow,
    visible_sequence,
)
from cadrumo.core.flows import FlowMode, PageStatus

from ._question_screen import QuestionScreen
from ._review_screen import ReviewScreen

if TYPE_CHECKING:
    from cadrumo.application.flows import CheckpointStore, FlowDefinition, FlowState, VisiblePage


class FlowTuiApp(App[None]):
    """Full-screen projection of one flow run."""

    CSS = """
    #flow-header { dock: top; height: 1; background: $primary-darken-2; }
    #page-prompt { text-style: bold; margin: 1 2 0 2; }
    #page-badge { color: $warning; margin: 0 2; }
    #page-help { margin: 1 2 0 2; }
    #page-format-hint { color: $text-muted; margin: 0 2; }
    #page-failure-modes { color: $text-muted; margin: 0 2; }
    #widget-area { margin: 1 2; height: auto; }
    #live-validation { color: $error; margin: 0 2; }
    #answer-echo { color: $success; margin: 0 2; }
    #commit-verdicts { color: $error; margin: 0 2; }
    #review-header { dock: top; height: 1; background: $primary-darken-2; }
    #review-blocking { color: $error; margin: 0 2; }
    #review-save-note { color: $warning; margin: 0 2; }
    """

    def __init__(
        self,
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        checkpoint_store: CheckpointStore | None = None,
        resume_state: FlowState | None = None,
    ) -> None:
        super().__init__()
        if checkpoint_available(definition, mode) and checkpoint_store is None:
            raise _FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context={"flow_id": definition.id, "mode": mode.value},
            )
        self.definition = definition
        self.state: FlowState = resume_state if resume_state is not None else start_flow(definition, mode=mode)
        self._store = checkpoint_store
        self.final_state: FlowState | None = None
        self.final_projection: ReviewProjection | None = None
        self.saved_and_exited = False

    def on_mount(self) -> None:
        self.push_screen(QuestionScreen())

    # ── engine access for screens ───────────────────────────────────────

    def cursor_entry(self) -> VisiblePage | None:
        """The visible-sequence entry the engine cursor addresses, if any."""
        for entry in visible_sequence(self.definition, self.state):
            if entry.key == self.state.cursor:
                return entry
        return None

    # ── intents ─────────────────────────────────────────────────────────

    def commit_answer(self, raw: str) -> None:
        """Commit the answer for the cursor page, then advance or re-render."""
        entry = self.cursor_entry()
        if entry is None:
            return
        self.state = answer(self.definition, self.state, entry.key, raw)
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

    def action_back(self) -> None:
        self.state = back_page(self.definition, self.state)
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
        assert self._store is not None  # guaranteed by the constructor fail-fast
        save_checkpoint(self.definition, self.state, self._store)
        self.final_state = self.state
        self.final_projection = review(self.definition, self.state)
        self.saved_and_exited = True
        self.exit()

    # ── rendering plumbing ──────────────────────────────────────────────

    def _at_last_visible_page(self) -> bool:
        sequence = visible_sequence(self.definition, self.state)
        return bool(sequence) and sequence[-1].key == self.state.cursor

    def _rerender_question(self) -> None:
        screen = self.screen
        if isinstance(screen, QuestionScreen):
            screen.render_page()

    def _rerender_review(self) -> None:
        screen = self.screen
        if isinstance(screen, ReviewScreen):
            screen.render_review()


def run_flow_tui(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    checkpoint_store: CheckpointStore | None = None,
    resume_state: FlowState | None = None,
) -> tuple[FlowState, ReviewProjection]:
    """Run the full-screen frontend to completion and return the outcome.

    Returns the final state and projection after a submit or a
    save-and-exit; a run abandoned without either raises so callers
    never mistake an aborted flow for a completed one.
    """
    app = FlowTuiApp(definition, mode=mode, checkpoint_store=checkpoint_store, resume_state=resume_state)
    app.run()
    if app.final_state is None or app.final_projection is None:
        raise _FlowCheckpointError(
            translated_message="flows.errors.tui_abandoned",
            context={"flow_id": definition.id, "mode": mode.value},
        )
    return app.final_state, app.final_projection


__all__ = ["FlowTuiApp", "run_flow_tui"]
