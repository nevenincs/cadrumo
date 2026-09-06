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

from typing import TYPE_CHECKING

import questionary
from pydantic import TypeAdapter

from ...core.flows import DEFER_TOKEN, FlowMode, FlowWidgetKind, PageStatus
from ...core.i18n import tr
from ...core.parsing import parse_bool
from ...core.tty import stdin_is_tty
from .capability import NO_CONSOLE_ERRORS as _NO_CONSOLE_ERRORS
from .checkpoint import CheckpointStore, checkpoint_available, discard_checkpoint, save_checkpoint
from .copy import (
    PAGE_REQUIREMENT_LOCALE_KEYS,
    PageCopy,
    assemble_page_copy,
    assemble_section_titles,
    resolve_optional_copy,
)
from .definition import FlowDefinition
from .engine import (
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
from .errors import FlowCheckpointError, FlowRunAbandonedError, FlowUnsupportedConsoleError
from .review import ReviewProjection, assert_submit_eligible, review

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output

_REVIEW_ACTION_SUBMIT = "submit"
_REVIEW_ACTION_EDIT = "edit"
_REVIEW_ACTION_RESTART = "restart"
_REVIEW_ACTION_SAVE_EXIT = "save_exit"
_CHECKBOX_VALUES = TypeAdapter(list[object])


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
        """Bind one flow definition to optional explicit terminal adapters."""
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
        if not stdin_is_tty():
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
                if action == _REVIEW_ACTION_SUBMIT and self._store is not None:
                    # A submitted flow must not stay resumable: save-and-exit
                    # writes a checkpoint, and without this the next run would
                    # offer to resume a run that was already submitted.
                    discard_checkpoint(self._definition, self._store)
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
                # The resolved title, never the internal slug: line mode and
                # the full-screen header read identically in the profile's
                # language.
                section=assemble_section_titles(self._definition).get(entry.section_id, entry.section_id),
            ),
        )
        self._render_page_copy(copy)
        self._render_current_answer(state, entry)
        requirement_key = PAGE_REQUIREMENT_LOCALE_KEYS[entry.page.required]
        self._emit(tr(requirement_key))

    def _render_page_copy(self, copy: PageCopy) -> None:
        """Emit the page's guidance blocks: help, format hint, failures, legal zone."""
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

    def _render_current_answer(self, state: FlowState, entry: VisiblePage) -> None:
        """Echo the committed answer, masking a SECRET page's value."""
        current = state.answers.get(entry.key)
        if not current:
            return
        # A SECRET page's committed value must never reach the terminal
        # or a captured session log; render a fixed masked marker while
        # the raw answer stays only in the engine state.
        if entry.page.widget is FlowWidgetKind.SECRET:
            self._emit(tr("flows.progress.current_answer_secret"))
        else:
            self._emit(tr("flows.progress.current_answer", value=current))

    def _prompt_widget(self, entry: VisiblePage, copy: PageCopy, *, current: str | None) -> str:
        """Prompt the page's widget and return the raw answer token.

        The per-widget construction is a table rather than a ``match`` so
        each widget's prompt is one small, independently readable unit and
        adding a kind is a table row. A kind absent from the table raises
        rather than falling through to ``None``: the previous ``match`` had
        no default arm, so an unhandled widget silently returned ``None``
        from a ``str``-typed call.
        """
        prompt = copy.prompt
        default = current if current is not None else (entry.page.default or "")
        try:
            return self._widget_prompts()[entry.page.widget](prompt, default, copy)
        except _NO_CONSOLE_ERRORS as exc:
            raise FlowUnsupportedConsoleError(
                translated_message="flows.errors.unsupported_console",
            ) from exc

    def _prompt_text_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        return self._stringify(
            self._ask(questionary.text(prompt, default=default, input=self._input, output=self._output)),
        )

    def _prompt_secret_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        return self._stringify(self._ask(questionary.password(prompt, input=self._input, output=self._output)))

    def _prompt_confirm_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        result = self._ask(
            questionary.confirm(
                prompt,
                default=parse_bool(default) is True,
                input=self._input,
                output=self._output,
            ),
        )
        if result is True:
            return "true"
        if result is False:
            return "false"
        return self._stringify(result)

    def _prompt_path_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        return self._stringify(
            self._ask(questionary.path(prompt, default=default, input=self._input, output=self._output)),
        )

    def _prompt_select_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        return self._select_one(prompt, default, self._render_choices(copy))

    def _prompt_compare_select_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        choices = self._render_choices(copy)
        choices.append(
            questionary.Choice(
                title=f"{len(choices) + 1}. {tr('flows.compare_select.defer_label')}",
                value=DEFER_TOKEN,
            ),
        )
        return self._select_one(prompt, default, choices)

    def _prompt_checkbox_widget(self, prompt: str, default: str, copy: PageCopy) -> str:
        result = self._ask(
            questionary.checkbox(
                prompt,
                choices=self._render_choices(copy),
                input=self._input,
                output=self._output,
            ),
        )
        if not isinstance(result, list):
            return ""
        return ",".join(str(item) for item in _CHECKBOX_VALUES.validate_python(result))

    def _select_one(self, prompt: str, default: str, choices: list[questionary.Choice]) -> str:
        """Run a single-choice select over already-rendered choices."""
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

    def _widget_prompts(self) -> Mapping[FlowWidgetKind, Callable[[str, str, PageCopy], str]]:
        """Map every widget kind to the bound prompt that builds it."""
        return {
            FlowWidgetKind.TEXT: self._prompt_text_widget,
            FlowWidgetKind.INTEGER: self._prompt_text_widget,
            FlowWidgetKind.DATE: self._prompt_text_widget,
            FlowWidgetKind.DECIMAL: self._prompt_text_widget,
            FlowWidgetKind.SECRET: self._prompt_secret_widget,
            FlowWidgetKind.CONFIRM: self._prompt_confirm_widget,
            FlowWidgetKind.PATH: self._prompt_path_widget,
            FlowWidgetKind.SELECT: self._prompt_select_widget,
            FlowWidgetKind.COMPARE_SELECT: self._prompt_compare_select_widget,
            FlowWidgetKind.CHECKBOX: self._prompt_checkbox_widget,
        }

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
        """Render the review listing, ask for one action, and apply it.

        Returns the chosen action, the resulting state, and whether the
        review loop is finished.
        """
        projection = review(self._definition, state)
        self._emit(tr("flows.review.header", answered=projection.answered_count))
        rows_by_number = self._render_review_listing(state, projection)
        action = self._ask_review_action(state, projection)

        if action == _REVIEW_ACTION_SUBMIT:
            return action, state, True
        if action == _REVIEW_ACTION_SAVE_EXIT:
            return action, self._save_and_exit(state), True
        if action == _REVIEW_ACTION_RESTART:
            return action, self._restart_if_confirmed(state), False
        return action, self._edit_by_number(state, rows_by_number), False

    def _render_review_listing(self, state: FlowState, projection: ReviewProjection) -> dict[str, str]:
        """Emit the section-grouped review rows and blockers.

        Returns the mapping from the number shown beside each row to the
        page key it addresses, which is what edit-by-number resolves against.
        """
        prompts = {
            entry.key: assemble_page_copy(entry.page).prompt for entry in visible_sequence(self._definition, state)
        }
        section_titles = assemble_section_titles(self._definition)
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
        return rows_by_number

    def _ask_review_action(self, state: FlowState, projection: ReviewProjection) -> str:
        """Offer the actions this state permits and return the chosen one."""
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
        return self._select_one(tr("flows.review.action_prompt"), "", actions)

    def _save_and_exit(self, state: FlowState) -> FlowState:
        """Persist the checkpoint the save-and-exit action promises."""
        # ``run`` refused at start when an available mode lacked a store, so
        # reaching here without one is unreachable by construction; the
        # refusal is the defence-in-depth backstop, never a silent no-save exit.
        if self._store is None:
            raise FlowCheckpointError(
                translated_message="flows.errors.checkpoint_store_missing",
                context={"flow_id": self._definition.id, "mode": state.mode.value},
            )
        save_checkpoint(self._definition, state, self._store)
        return state

    def _restart_if_confirmed(self, state: FlowState) -> FlowState:
        """Restart the flow only on an explicit confirmation."""
        confirmed = self._ask(
            questionary.confirm(
                tr("flows.review.restart_confirm"),
                default=False,
                input=self._input,
                output=self._output,
            ),
        )
        if confirmed is True:
            return restart_flow(self._definition, state)
        return state

    def _edit_by_number(self, state: FlowState, rows_by_number: dict[str, str]) -> FlowState:
        """Re-ask the page the operator names by its listing number."""
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
            return state
        entry = next(
            (item for item in visible_sequence(self._definition, state) if item.key == target_key),
            None,
        )
        if entry is None:
            return self._resolve_orphan(state, target_key)
        state = jump_to(self._definition, state, target_key)
        return self._ask_page(state, entry)

    def _resolve_orphan(self, state: FlowState, target_key: str) -> FlowState:
        """Offer the recovery affordance for an answer with no visible page.

        A stale orphan — an answer whose page a gating change or a shrunk
        group removed from the visible sequence — cannot be re-asked, but it
        must stay resolvable: the affordance is a confirmed reset that clears
        the orphaned answer, unblocking submission without silent loss.
        """
        if page_status(state, target_key) is not PageStatus.STALE:
            self._emit(tr("flows.review.edit_not_editable", page_key=target_key))
            return state
        confirmed = questionary.confirm(
            tr("flows.review.reset_stale_confirm", page_key=target_key),
            default=False,
            input=self._input,
            output=self._output,
        ).ask()
        if confirmed is True:
            state = reset_page(self._definition, state, target_key)
            self._emit(tr("flows.review.reset_stale_done", page_key=target_key))
        return state

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
