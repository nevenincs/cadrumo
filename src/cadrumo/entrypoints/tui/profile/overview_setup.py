"""Guided profile setup navigation and completion."""

from __future__ import annotations

from contextvars import copy_context
from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, ProgressBar, Static
from textual.worker import Worker, WorkerState

from ....core.i18n.render import tr
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.values import ProfileSetupState
from ..components.status import PinnedStatusBar
from ..components.widgets import (
    ContentScroll,
    DisclosureGroup,
)
from .overview_contracts import (
    _CONTINUE_BUTTON_ID,
    _REQUIRED_ONLY_ID,
    _SEARCH_ID,
    _SETUP_COPY_LOCALE_KEYS,
    _SETUP_NAV_LOCALE_KEYS,
    _SETUP_TITLE_LOCALE_KEYS,
)
from .setup_journey import SETUP_STAGES, ProfileSetupStage

if TYPE_CHECKING:
    from ....application.user_profile.overview import ProfileOverview
    from .overview import ProfileManagerScreen


class ProfileOverviewSetupRenderMixin:
    """Render the guided setup status and actions."""

    def _render_onboarding(self: ProfileManagerScreen) -> None:
        """Render the current stage and saved progress from the application projection."""
        _render_onboarding_prompts(self)
        if not self._onboarding:
            return
        overview = self.overview
        total, answered, missing, done = _setup_progress_values(self, overview)
        stage = self._setup_stage
        index = SETUP_STAGES.index(stage)
        _render_setup_progress(self, stage, total, answered)
        action = _setup_continue_action(stage, done, missing)
        _render_setup_copy(self, stage, total, missing, index)
        _render_setup_checklist(self, stage, missing)
        busy = self._pending_write is not None or self._pending_completion is not None
        _render_setup_navigation(self, overview, stage, index, done, busy)
        button = self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button)
        button.disabled = busy
        if str(button.label) != action:
            button.label = action
            # The label can change while a question covers the page; measure
            # the button again so its new label is not clipped to the old width.
            button.refresh(layout=True)


class ProfileOverviewSetupNavigationMixin:
    """Move through setup stages without changing saved profile data."""

    async def _show_setup_stage(self: ProfileManagerScreen, stage: ProfileSetupStage) -> None:
        """Move without acquiring data, discarding answers or completing the profile."""
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        self._walking = False
        self._setup_stage = stage
        self._query = ""
        self.query_one(f"#{_SEARCH_ID}", Input).value = ""
        self.query_one("#manager-field-help", Static).display = False
        for section in self.overview.sections:
            self.query_one(f"#fold-{section.key}", DisclosureGroup).collapsed = (
                stage is ProfileSetupStage.REVIEW
                or not any(field.path in self.overview.missing_required for field in section.fields)
            )
        self.query_one("#manager-sources-fold", DisclosureGroup).collapsed = False
        await self._redraw()
        self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()
        self.call_after_refresh(
            self.query_one("#manager-body", ContentScroll).scroll_home, animate=False, immediate=True
        )

    async def action_continue_setup(self: ProfileManagerScreen) -> None:
        """Advance the journey; only the reviewed Finish action requests completion."""
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        await _continue_setup_journey(self)


class ProfileOverviewSetupWalkMixin:
    """Carry the guided walk forward after an answer lands."""

    def _carry_walk_on(self: ProfileManagerScreen) -> None:
        """After an answer lands, open the next required question, or hand back to Continue."""
        if not self._walking:
            return
        if self.overview.missing_required_fields:
            self.run_worker(self.action_continue_setup(), group="profile-setup-walk", exclusive=True)
            return
        self._walking = False
        if self._onboarding:
            self.run_worker(
                self._show_setup_stage(ProfileSetupStage.REVIEW), group="profile-setup-walk", exclusive=True
            )


class ProfileOverviewCompletionMixin:
    """Offer and settle the profile setup completion request."""

    @property
    def _completion_offered(self: ProfileManagerScreen) -> bool:
        """Whether the page offers to declare setup complete right now."""
        return (
            self._complete_setup is not None
            and self.overview.setup_state is ProfileSetupState.INCOMPLETE
            and (not self._onboarding or self._setup_stage is ProfileSetupStage.REVIEW)
        )

    def action_complete_setup(self: ProfileManagerScreen) -> None:
        """Ask the store to declare this profile's setup complete, off the event loop."""
        door = self._complete_setup
        if door is None or not self._completion_offered:
            return
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        completion_context = copy_context()
        self.query_one("#manager-status", PinnedStatusBar).show_progress(tr("flows.manager.complete_setup.running"))
        self._pending_completion = self.run_worker(
            lambda: completion_context.run(door),
            name="profile-complete-setup",
            group="profile-complete-setup",
            exit_on_error=False,
            thread=True,
        )
        self._render_onboarding()

    async def _settle_completion(self: ProfileManagerScreen, worker: Worker[ProfileOverview]) -> None:
        """Show the completed page, or why the store would not complete it."""
        self._pending_completion = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            await _settle_successful_completion(self, worker.result)
            return
        self._render_onboarding()
        _settle_completion_refusal(self, worker.error)


def _render_onboarding_prompts(screen: ProfileManagerScreen) -> None:
    """Keep setup prompts and search labels current in every manager mode."""
    screen.query_one("#manager-sources-summary", Static).update(tr("flows.manager.onboarding.sources_summary"))
    screen.query_one("#manager-sources-fold", DisclosureGroup).title = tr("flows.manager.onboarding.sources_title")
    screen.query_one(f"#{_SEARCH_ID}", Input).placeholder = tr("flows.manager.onboarding.search_placeholder")
    screen.query_one(f"#{_REQUIRED_ONLY_ID}", Checkbox).label = tr("flows.manager.onboarding.required_only")


def _setup_progress_values(
    screen: ProfileManagerScreen, overview: ProfileOverview
) -> tuple[int, int, frozenset[str], bool]:
    """Count visible and unresolved required facts for the progress display."""
    required = [
        (section, field)
        for section in overview.sections
        for field in section.fields
        if screen._required_now(overview, field)
    ]
    missing = frozenset(overview.missing_required)
    # A requirement with no row to show still counts, so the bar never reads
    # as finished while the store would refuse completion.
    total = len(required) + sum(1 for path in missing if path not in screen._field_by_key)
    answered = sum(1 for _section, field in required if field.path not in missing)
    done = overview.setup_state is ProfileSetupState.COMPLETE
    return total, answered, missing, done


def _render_setup_progress(screen: ProfileManagerScreen, stage: ProfileSetupStage, total: int, answered: int) -> None:
    """Update the progress bar and stage/answer count line."""
    done = screen.overview.setup_state is ProfileSetupState.COMPLETE
    index = SETUP_STAGES.index(stage)
    screen.query_one("#onboarding-progress", ProgressBar).update(
        total=total + 1, progress=answered + (1 if done else 0)
    )
    progress = tr("flows.manager.onboarding.progress", answered=answered, total=total)
    step = tr(
        "flows.manager.setup.step", step=index + 1, steps=len(SETUP_STAGES), remaining=len(SETUP_STAGES) - index - 1
    )
    screen.query_one("#onboarding-heading", Static).update(tr("flows.manager.onboarding.heading"))
    screen.query_one("#onboarding-step", Static).update(f"{step}\n{progress}")


def _setup_continue_action(stage: ProfileSetupStage, done: bool, missing: frozenset[str]) -> str:
    """Name the action for the stage and the outstanding required facts."""
    fixed = {
        ProfileSetupStage.READY: "flows.manager.onboarding.to_workbench",
        ProfileSetupStage.OVERVIEW: "flows.manager.setup.start",
        ProfileSetupStage.GET_DATA: "flows.manager.setup.skip_import",
    }
    key = fixed.get(stage)
    if key is not None:
        return tr(key)
    if stage is ProfileSetupStage.REQUIRED or done:
        return tr("flows.manager.onboarding.continue")
    if missing:
        return tr("flows.manager.setup.answer_required")
    return tr("flows.manager.onboarding.finish")


def _render_setup_copy(
    screen: ProfileManagerScreen, stage: ProfileSetupStage, total: int, missing: frozenset[str], index: int
) -> None:
    """Render the selected stage's title and explanatory copy."""
    title = screen.query_one("#onboarding-stage-title", Static)
    title.update(tr(_SETUP_TITLE_LOCALE_KEYS[stage]))
    title.set_class(stage is ProfileSetupStage.READY, "setup-success")
    screen.query_one("#onboarding-stage-copy", Static).update(
        tr(_SETUP_COPY_LOCALE_KEYS[stage], missing=len(missing), total=total)
    )


def _render_setup_checklist(screen: ProfileManagerScreen, stage: ProfileSetupStage, missing: frozenset[str]) -> None:
    """Render the stage-specific overview or review checklist."""
    checklist = screen.query_one("#onboarding-checklist", Static)
    checklist.display = stage in {ProfileSetupStage.OVERVIEW, ProfileSetupStage.REVIEW, ProfileSetupStage.READY}
    if stage is ProfileSetupStage.READY:
        checklist.update(tr("flows.manager.setup.achievement"))
    elif stage is ProfileSetupStage.OVERVIEW:
        checklist.update(tr("flows.manager.setup.overview_checklist"))
    else:
        checklist.update(
            tr("flows.manager.setup.review_missing", missing=len(missing))
            if missing
            else tr("flows.manager.setup.review_saved")
        )


def _render_setup_navigation(
    screen: ProfileManagerScreen,
    overview: ProfileOverview,
    stage: ProfileSetupStage,
    index: int,
    done: bool,
    busy: bool,
) -> None:
    """Update stage buttons, previous, and tools from the current progress."""
    previous = screen.query_one("#onboarding-previous", Button)
    previous.label = tr("flows.manager.setup.previous")
    previous.disabled = index == 0 or busy
    for position, candidate in enumerate(SETUP_STAGES):
        stage_button = screen.query_one(f"#setup-stage-{candidate.value}", Button)
        passed = {
            ProfileSetupStage.OVERVIEW: index > 0,
            ProfileSetupStage.GET_DATA: screen._sources_skipped,
            ProfileSetupStage.REQUIRED: overview.complete,
            ProfileSetupStage.REVIEW: done,
            ProfileSetupStage.READY: done,
        }[candidate]
        marker = "✓" if passed else str(position + 1)
        stage_button.label = f"{marker} {tr(_SETUP_NAV_LOCALE_KEYS[candidate])}"
        stage_button.variant = "primary" if candidate is stage else "default"
        stage_button.set_class(candidate is stage, "setup-current")
        stage_button.disabled = busy or (candidate is ProfileSetupStage.READY and not done)
    screen.query_one("#manager-tools", Horizontal).display = stage in {
        ProfileSetupStage.REQUIRED,
        ProfileSetupStage.REVIEW,
    }


async def _continue_setup_journey(screen: ProfileManagerScreen) -> None:
    """Dispatch Continue to the action for its current stage."""
    stage = screen._setup_stage
    if stage is ProfileSetupStage.READY:
        screen._walking = False
        await screen.action_quit()
        return
    if stage is ProfileSetupStage.OVERVIEW:
        await screen._show_setup_stage(ProfileSetupStage.GET_DATA)
        return
    if stage is ProfileSetupStage.GET_DATA:
        screen._sources_skipped = True
        await screen._show_setup_stage(ProfileSetupStage.REQUIRED)
        return
    if stage is ProfileSetupStage.REVIEW:
        await _continue_setup_review(screen)
        return
    await _continue_required_setup(screen)


async def _continue_setup_review(screen: ProfileManagerScreen) -> None:
    """Return to missing answers, show readiness, or request completion."""
    if screen.overview.missing_required:
        await screen._show_setup_stage(ProfileSetupStage.REQUIRED)
    elif screen.overview.setup_state is ProfileSetupState.COMPLETE:
        await screen._show_setup_stage(ProfileSetupStage.READY)
    else:
        screen.action_complete_setup()


async def _continue_required_setup(screen: ProfileManagerScreen) -> None:
    """Open the first required answer, or move to review when all are filled."""
    field = next(iter(screen.overview.missing_required_fields), None)
    if field is None:
        screen._walking = False
        if screen.overview.missing_required:
            screen._refuse(tr("flows.manager.complete_setup.incomplete_unnamed"))
            return
        await screen._show_setup_stage(ProfileSetupStage.REVIEW)
        return
    section = screen._section(field.path.split(".", 1)[0])
    if section is None:
        return
    fold = screen.query_one(f"#fold-{section.key}", DisclosureGroup)
    fold.collapsed = False
    fold.scroll_visible()
    required = [
        candidate
        for candidate_section in screen.overview.sections
        for candidate in candidate_section.fields
        if screen._required_now(screen.overview, candidate)
    ]
    number = 1 + sum(1 for candidate in required if candidate.path not in screen.overview.missing_required)
    context = "\n".join(
        (
            tr(
                "flows.manager.onboarding.question",
                number=number,
                total=len(required),
                section=section.title,
            ),
            section.summary,
        )
    )
    screen._walking = True
    screen._open_field_editor(field, context=context)


async def _settle_successful_completion(screen: ProfileManagerScreen, result: ProfileOverview) -> None:
    """Accept only the completed projection for this profile and revision."""
    if (
        result.profile_id != screen.overview.profile_id
        or result.record_revision < screen.overview.record_revision
        or result.setup_state is not ProfileSetupState.COMPLETE
        or result.missing_required
    ):
        screen._render_onboarding()
        screen._refuse(tr("flows.manager.complete_setup.failed"))
        return
    screen.overview = result
    if screen._onboarding:
        screen._setup_stage = ProfileSetupStage.READY
    await screen._redraw()
    screen.refresh_bindings()
    if screen._onboarding:
        screen.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()
    else:
        screen.query_one("#manager-status", PinnedStatusBar).show_success(tr("flows.manager.complete_setup.completed"))


def _settle_completion_refusal(screen: ProfileManagerScreen, error: BaseException | None) -> None:
    """Show schema incompleteness specifically, otherwise report the worker error."""
    if isinstance(error, ProfileSchemaValidationError):
        missing = [field.label for field in screen.overview.missing_required_fields]
        message = (
            tr("flows.manager.complete_setup.incomplete", fields=", ".join(missing))
            if missing
            else tr("flows.manager.complete_setup.incomplete_unnamed")
        )
        screen._refuse(message)
        return
    screen._refuse_worker(error, message_key="flows.manager.complete_setup.failed")
