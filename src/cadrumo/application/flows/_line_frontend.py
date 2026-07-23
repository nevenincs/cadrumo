"""The line-mode frontend: sequential paging over the engine, no full screen.

This is the degradation tier for hosts that cannot run the full-screen
TUI: a forward-sequential walk that renders each page's assembled copy
(prompt, help, format hint, failure modes, current-answer echo) as
plain lines, prompts through ``questionary`` primitives on injectable
``prompt_toolkit`` IO, re-prompts in place on a failing verdict, and
finishes in a review loop that lists every page with its status and
offers edit-by-number, restart, save-and-exit (only where the
definition declares checkpointing for the mode — the no-op arm renders
an explicit unavailability line instead), and submit.

The frontend contains zero flow logic: every semantic — visibility,
validation, staleness, deferral, submit eligibility — is an engine
transition or projection. Back-navigation in line mode is served by the
review loop's jump-to-edit; free cursor movement is the full-screen
frontend's job.

IO injection mirrors the retired one-shot prompter's contract: explicit
``input``/``output`` devices host the prompts (the headless pipe-input
test drive), and an un-injected frontend applies the full non-TTY /
Windows no-console refusal before any progress.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import questionary

from ...core.flows import DEFER_TOKEN, FlowMode, FlowWidgetKind, PageStatus
from ...core.i18n import tr
from ._capability import NO_CONSOLE_ERRORS as _NO_CONSOLE_ERRORS
from ._checkpoint import CheckpointStore, checkpoint_available, save_checkpoint
from ._copy import PageCopy, assemble_page_copy, resolve_copy, resolve_optional_copy
from ._definition import FlowDefinition
from ._engine import (
    SECTION_VERDICT_PREFIX,
    FlowState,
    VisiblePage,
    answer,
    jump_to,
    next_page,
    page_status,
    reset_page,
    restart_flow,
    start_flow,
    visible_sequence,
)
from ._errors import FlowCheckpointError, FlowRunAbandonedError, FlowUnsupportedConsoleError
from ._review import ReviewProjection, assert_submit_eligible, review

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output

_REVIEW_ACTION_SUBMIT = "submit"
_REVIEW_ACTION_EDIT = "edit"
_REVIEW_ACTION_RESTART = "restart"
_REVIEW_ACTION_SAVE_EXIT = "save_exit"


class LineFlowFrontend:
    """Sequential line-mode projection of one flow run."""

    def __init__(
        self,
        definition: FlowDefinition,
        *,
        input: Input | None = None,
        output: Output | None = None,
        checkpoint_store: CheckpointStore | None = None,
        on_answer_committed: Callable[[str, str], None] | None = None,
    ) -> None:
        self._definition = definition
        self._input = input
        self._output = output
        self._store = checkpoint_store
        self._on_answer_committed = on_answer_committed
        """Generic post-commit notification, fired after each successful engine
        answer commit with ``(page_key, canonical_committed_value)`` and before
        the next page is rendered. Domain-blind — not a language hook itself,
        though a consumer may use it to re-activate a locale mid-walk (line
        mode re-assembles every page's copy per page, so the next page renders
        in the new language). The value may be a SECRET page's raw answer, so a
        consumer MUST NOT log it."""

    def ensure_interactive_environment(self) -> None:
        """Refuse before progress when this process cannot host prompts.

        A frontend carrying explicit IO is already bound to a device
        that can host a prompt, so the process-stdio probe does not
        apply to it.
        """
        if self._input is not None or self._output is not None:
            return
        if not sys.stdin.isatty():
            raise FlowUnsupportedConsoleError(
                translated_message="flows.errors.unsupported_console",
            )
        try:
            from prompt_toolkit.output.defaults import create_output

            output = create_output(always_prefer_tty=True)
            output.flush()
        except _NO_CONSOLE_ERRORS as exc:
            raise FlowUnsupportedConsoleError(
                translated_message="flows.errors.unsupported_console",
            ) from exc

    def run(self, *, mode: FlowMode, resume_state: FlowState | None = None) -> tuple[FlowState, ReviewProjection]:
        """Walk the flow to a submitted state and return it with its projection.

        ``resume_state`` continues a projection built by ``resume_flow``;
        otherwise the run starts fresh. The walk prompts every visible
        unanswered page in order, then enters the review loop until the
        operator submits, or saves and exits — the save is performed
        HERE, through the checkpoint port, before the state is returned;
        the caller never re-persists (single writer).

        A mode whose definition declares checkpointing AVAILABLE demands
        an injected store: refusing up front is what keeps the
        save-and-exit affordance honest — a mis-wired frontend must
        never offer a save it cannot perform and then silently discard.
        """
        self.ensure_interactive_environment()
        if checkpoint_available(self._definition, mode) and self._store is None:
            raise FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context={"flow_id": self._definition.id, "mode": mode.value},
            )
        state = resume_state if resume_state is not None else start_flow(self._definition, mode=mode)
        intro = resolve_optional_copy(self._definition.intro)
        if intro is not None:
            self._emit(intro)

        while True:
            state = self._walk_unanswered(state)
            action, state, done = self._review_round(state)
            if done:
                projection = (
                    assert_submit_eligible(self._definition, state)
                    if action == _REVIEW_ACTION_SUBMIT
                    else review(self._definition, state)
                )
                return state, projection

    def _walk_unanswered(self, state: FlowState) -> FlowState:
        while True:
            target = self._first_unanswered(state)
            if target is None:
                return state
            state = jump_to(self._definition, state, target.key)
            state = self._ask_page(state, target)
            state = next_page(self._definition, state)
            state = self._render_section_blocks(state)

    def _first_unanswered(self, state: FlowState) -> VisiblePage | None:
        for entry in visible_sequence(self._definition, state):
            if entry.key not in state.answers:
                return entry
        return None

    def _ask_page(self, state: FlowState, entry: VisiblePage) -> FlowState:
        copy = assemble_page_copy(entry.page)
        while True:
            self._render_page_header(state, entry, copy)
            raw = self._prompt_widget(entry, copy, current=state.answers.get(entry.key))
            state = answer(self._definition, state, entry.key, raw)
            failing = state.verdicts.get(entry.key)
            if not failing:
                # Successful commit: notify before the walk moves to the next
                # page, so a locale-switch hook applies to what renders next.
                if self._on_answer_committed is not None:
                    self._on_answer_committed(entry.key, state.answers.get(entry.key, ""))
                return state
            for verdict in failing:
                if verdict.message_key:
                    self._emit(tr(verdict.message_key, **verdict.context))

    def _render_page_header(self, state: FlowState, entry: VisiblePage, copy: PageCopy) -> None:
        sequence = visible_sequence(self._definition, state)
        position = next((index for index, item in enumerate(sequence) if item.key == entry.key), 0)
        self._emit(
            tr(
                "flows.progress.page_header",
                position=position + 1,
                total=len(sequence),
                section=entry.section_id,
            ),
        )
        if copy.help:
            self._emit(copy.help)
        if copy.format_hint:
            self._emit(tr("flows.progress.format_hint", hint=copy.format_hint))
        for failure_mode in copy.failure_modes:
            self._emit(tr("flows.progress.failure_mode", text=failure_mode))
        for legal_ref in copy.legal_zone:
            if legal_ref.label:
                self._emit(tr("flows.progress.legal_ref", ref=legal_ref.ref, label=legal_ref.label))
            else:
                self._emit(legal_ref.ref)
        current = state.answers.get(entry.key)
        if current:
            # A SECRET page's committed value must never reach the terminal
            # or a captured session log; render a fixed masked marker while
            # the raw answer stays only in the engine state.
            if entry.page.widget is FlowWidgetKind.SECRET:
                self._emit(tr("flows.progress.current_answer_secret"))
            else:
                self._emit(tr("flows.progress.current_answer", value=current))
        requirement_key = "flows.progress.required" if entry.page.required else "flows.progress.optional"
        self._emit(tr(requirement_key))

    def _prompt_widget(self, entry: VisiblePage, copy: PageCopy, *, current: str | None) -> str:
        prompt = copy.prompt
        default = current if current is not None else (entry.page.default or "")
        try:
            match entry.page.widget:
                case FlowWidgetKind.TEXT | FlowWidgetKind.INTEGER:
                    return self._stringify(
                        self._ask(questionary.text(prompt, default=default, input=self._input, output=self._output)),
                    )
                case FlowWidgetKind.SECRET:
                    return self._stringify(
                        self._ask(questionary.password(prompt, input=self._input, output=self._output)),
                    )
                case FlowWidgetKind.CONFIRM:
                    result = self._ask(
                        questionary.confirm(
                            prompt,
                            default=default.strip().lower() in {"true", "yes", "1", "y"},
                            input=self._input,
                            output=self._output,
                        ),
                    )
                    if result is True:
                        return "true"
                    if result is False:
                        return "false"
                    return self._stringify(result)
                case FlowWidgetKind.PATH:
                    return self._stringify(
                        self._ask(questionary.path(prompt, default=default, input=self._input, output=self._output)),
                    )
                case FlowWidgetKind.SELECT:
                    return self._stringify(
                        self._ask(
                            questionary.select(
                                prompt,
                                choices=self._render_choices(copy),
                                default=default or None,
                                input=self._input,
                                output=self._output,
                            ),
                        ),
                    )
                case FlowWidgetKind.COMPARE_SELECT:
                    choices = self._render_choices(copy)
                    choices.append(
                        questionary.Choice(
                            title=f"{len(choices) + 1}. {tr('flows.compare_select.defer_label')}",
                            value=DEFER_TOKEN,
                        ),
                    )
                    return self._stringify(
                        self._ask(
                            questionary.select(
                                prompt,
                                choices=choices,
                                default=default or None,
                                input=self._input,
                                output=self._output,
                            ),
                        ),
                    )
                case FlowWidgetKind.CHECKBOX:
                    result = self._ask(
                        questionary.checkbox(
                            prompt,
                            choices=self._render_choices(copy),
                            input=self._input,
                            output=self._output,
                        ),
                    )
                    if result is None:
                        return ""
                    return ",".join(str(item) for item in result)
        except _NO_CONSOLE_ERRORS as exc:
            raise FlowUnsupportedConsoleError(
                translated_message="flows.errors.unsupported_console",
            ) from exc

    def _render_choices(self, copy: PageCopy) -> list[questionary.Choice]:
        rendered: list[questionary.Choice] = []
        for number, choice in enumerate(copy.choices, start=1):
            title = choice.label
            if choice.provenance:
                title = tr("flows.compare_select.candidate", label=choice.label, provenance=choice.provenance)
            # Number every row so "item 3" names the same choice on both
            # frontends (the full-screen list is numbered identically).
            rendered.append(
                questionary.Choice(title=f"{number}. {title}", value=choice.value, description=choice.description),
            )
        return rendered

    def _render_section_blocks(self, state: FlowState) -> FlowState:
        for key, verdicts in state.verdicts.items():
            if not key.startswith(SECTION_VERDICT_PREFIX):
                continue
            for verdict in verdicts:
                if verdict.message_key:
                    self._emit(tr(verdict.message_key, **verdict.context))
        return state

    def _review_round(self, state: FlowState) -> tuple[str, FlowState, bool]:
        projection = review(self._definition, state)
        self._emit(tr("flows.review.header", answered=projection.answered_count))
        prompts = {
            entry.key: assemble_page_copy(entry.page).prompt for entry in visible_sequence(self._definition, state)
        }
        section_titles = {section.id: resolve_copy(section.title) for section in self._definition.sections}
        rows_by_number: dict[str, str] = {}
        current_section: str | None = None
        for number, row in enumerate(projection.rows, start=1):
            if row.section_id != current_section:
                # Group the listing by section (a resolved section-title
                # heading) so line-mode review reads as a complete-profile
                # summary, matching the full-screen table's grouping.
                current_section = row.section_id
                self._emit(section_titles.get(row.section_id, row.section_id))
            rows_by_number[str(number)] = row.key
            self._emit(
                tr(
                    "flows.review.row",
                    number=number,
                    # Resolved prompt copy where the page is visible; a
                    # non-visible stale orphan keeps its raw key, exactly as
                    # the full-screen review table renders it.
                    page_key=prompts.get(row.key, row.key),
                    status=row.status.value,
                ),
            )
        for verdict in projection.blocking:
            if verdict.message_key:
                self._emit(tr(verdict.message_key, **verdict.context))

        actions = [questionary.Choice(title=tr("flows.review.action_edit"), value=_REVIEW_ACTION_EDIT)]
        if projection.submit_eligible:
            actions.insert(0, questionary.Choice(title=tr("flows.review.action_submit"), value=_REVIEW_ACTION_SUBMIT))
        if checkpoint_available(self._definition, state.mode):
            actions.append(
                questionary.Choice(title=tr("flows.review.action_save_exit"), value=_REVIEW_ACTION_SAVE_EXIT),
            )
        else:
            self._emit(tr("flows.review.save_unavailable", mode=state.mode.value))
        actions.append(questionary.Choice(title=tr("flows.review.action_restart"), value=_REVIEW_ACTION_RESTART))

        action = self._stringify(
            self._ask(
                questionary.select(
                    tr("flows.review.action_prompt"),
                    choices=actions,
                    input=self._input,
                    output=self._output,
                ),
            ),
        )
        if action == _REVIEW_ACTION_SUBMIT:
            return action, state, True
        if action == _REVIEW_ACTION_SAVE_EXIT:
            # ``run`` refused at start when an available mode lacked a
            # store, so reaching this arm without one is unreachable by
            # construction; the refusal below is the defence-in-depth
            # backstop, never a silent no-save exit.
            if self._store is None:
                raise FlowCheckpointError(
                    translated_message="flows.errors.checkpoint_store_missing",
                    context={"flow_id": self._definition.id, "mode": state.mode.value},
                )
            save_checkpoint(self._definition, state, self._store)
            return action, state, True
        if action == _REVIEW_ACTION_RESTART:
            confirmed = self._ask(
                questionary.confirm(
                    tr("flows.review.restart_confirm"),
                    default=False,
                    input=self._input,
                    output=self._output,
                ),
            )
            if confirmed is True:
                return action, restart_flow(self._definition, state), False
            return action, state, False
        target_number = self._stringify(
            self._ask(
                questionary.text(
                    tr("flows.review.edit_which"),
                    input=self._input,
                    output=self._output,
                ),
            ),
        ).strip()
        target_key = rows_by_number.get(target_number)
        if target_key is None:
            self._emit(tr("flows.review.edit_unknown", number=target_number))
            return action, state, False
        entry = next(
            (item for item in visible_sequence(self._definition, state) if item.key == target_key),
            None,
        )
        if entry is None:
            # A stale orphan — an answer whose page a gating change or a
            # shrunk group removed from the visible sequence — cannot be
            # re-asked, but it must stay resolvable: the recovery
            # affordance is a confirmed reset that clears the orphaned
            # answer, unblocking submission without silent loss.
            if page_status(state, target_key) is PageStatus.STALE:
                confirmed = questionary.confirm(
                    tr("flows.review.reset_stale_confirm", page_key=target_key),
                    default=False,
                    input=self._input,
                    output=self._output,
                ).ask()
                if confirmed is True:
                    state = reset_page(self._definition, state, target_key)
                    self._emit(tr("flows.review.reset_stale_done", page_key=target_key))
                return action, state, False
            self._emit(tr("flows.review.edit_not_editable", page_key=target_key))
            return action, state, False
        state = jump_to(self._definition, state, target_key)
        state = self._ask_page(state, entry)
        return action, state, False

    def _ask(self, question: questionary.Question) -> object:
        """Run one prompt to an answer, mapping Ctrl-C to a typed abandonment.

        ``unsafe_ask`` (unlike ``ask``) re-raises ``KeyboardInterrupt``
        instead of swallowing it into a silent ``None`` and printing an
        untranslated "Cancelled by user" to ``sys.stdout``; the frontend
        catches it at this single boundary and refuses with a typed,
        translated error so a required page can be abandoned rather than
        re-prompting forever with no cancel path.
        """
        try:
            return question.unsafe_ask()
        except KeyboardInterrupt as exc:
            raise FlowRunAbandonedError(
                translated_message="errors.refused.refused_flow_run_abandoned",
                context={"flow_id": self._definition.id},
            ) from exc

    def _emit(self, text: str) -> None:
        """Write one operator-facing line to the device the prompts render on."""
        output = self._output
        if output is None:
            from prompt_toolkit.application.current import get_app_session

            output = get_app_session().output
        output.write(f"{text}\n")
        output.flush()

    @staticmethod
    def _stringify(value: object) -> str:
        return "" if value is None else str(value)


__all__ = ["LineFlowFrontend"]
