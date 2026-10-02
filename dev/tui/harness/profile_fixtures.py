"""Profile review states reached through real local profile and UI doors.

Each capture provisions its own encrypted, synthetic profile. Required answers
are validated and saved by installed account composition; completion uses its
guarded door. These fixtures never hand-build a profile projection.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from typing import override
from uuid import uuid4

from textual.events import Mount
from textual.widgets import Input, OptionList

from cadrumo.application.user_profile.login_interaction import profile_login_choices
from cadrumo.application.user_profile.overview import ProfileOverview
from cadrumo.core.bucket_pointer import require_active_bucket_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.widgets import ContentScroll, DisclosureGroup
from cadrumo.entrypoints.tui.installed_session import compose_authenticated_account_inputs
from cadrumo.entrypoints.tui.launcher import InstalledWorkbenchAccountInputsV1
from cadrumo.entrypoints.tui.profile.overview import FieldEditScreen, ProfileManagerScreen
from cadrumo.entrypoints.tui.tests.fixture import PROFILE_LABEL, ensure_session, harness_storage


class ProfileFixtureState(StrEnum):
    """Reachable setup and ongoing-editing frames."""

    OVERVIEW = "overview"
    GET_DATA = "get-data"
    REQUIRED = "required"
    REVIEW = "review"
    READY = "ready"
    TYPED_QUESTION = "typed-question"
    CHOICE_QUESTION = "choice-question"
    INVALID_ANSWER = "invalid-answer"
    HELP_QUESTION = "help-question"
    EDIT = "edit"
    OPTIONAL_EDIT = "optional-edit"
    SAVED_EDIT = "saved-edit"


@contextmanager
def profile_fixture_storage() -> Iterator[str]:
    """Create fresh state so a prior capture cannot answer a later one's questions."""
    with harness_storage(namespace=f"profile-review-{uuid4().hex}"), bundled_indexed_authority().operation():
        yield ensure_session()


def _populate_required(inputs: InstalledWorkbenchAccountInputsV1, overview: ProfileOverview) -> ProfileOverview:
    """Supply synthetic answers, letting the application discover conditional requirements."""
    for _ in range(overview.total_count):
        if not overview.missing_required:
            return overview
        field = next(iter(overview.missing_required_fields), None)
        if field is None:
            raise ValueError("profile fixture has a required path with no editor")
        if field.choices:
            value = field.choices[0].value
        elif field.path == "identity.tax_id":
            value = "12345678Z"
        else:
            raise ValueError(f"profile fixture needs a synthetic answer for {field.path}")
        overview = inputs.persist_profile_field(field.path, value, overview.record_revision, overview.content_digest)
    raise ValueError("profile fixture could not complete required answers")


class ProfileCaptureHost(ScreenHostApp[None]):
    """Drive the production screen to one declared, settled review state."""

    def __init__(self, screen: ProfileManagerScreen, state: ProfileFixtureState) -> None:
        """Bind the production screen and the path the capture must reach."""
        super().__init__(screen)
        self.profile_screen = screen
        self.fixture_state = state
        self.frame_ready = asyncio.Event()

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Textual also dispatches inherited handlers unless prevented. We
        # mount the host explicitly here before driving the fixture, so a
        # second inherited call would cover the question with the manager.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self._reach_state()
        self.frame_ready.set()

    async def _reach_state(self) -> None:
        """Reach the requested state after the hosted profile has mounted."""
        screen = self.profile_screen
        state = self.fixture_state
        if state in {ProfileFixtureState.EDIT, ProfileFixtureState.OPTIONAL_EDIT, ProfileFixtureState.SAVED_EDIT}:
            screen.query_one("#fold-identity", DisclosureGroup).collapsed = False
            screen.call_after_refresh(
                screen.query_one("#manager-body", ContentScroll).scroll_home, animate=False, immediate=True
            )
            if state is not ProfileFixtureState.EDIT:
                field = screen._field_by_key["identity.name"]
                screen._open_field_editor(field)
                dialog = await self._mounted_editor()
                if state is ProfileFixtureState.SAVED_EDIT:
                    dialog._submit_typed("Synthetic edited name")
                    await self._wait_for_profile_write()
            return
        if state is ProfileFixtureState.OVERVIEW:
            return
        await screen.action_continue_setup()
        if state is ProfileFixtureState.GET_DATA:
            return
        await screen.action_continue_setup()
        if state is ProfileFixtureState.REQUIRED:
            return
        if state in {ProfileFixtureState.REVIEW, ProfileFixtureState.READY}:
            await screen.action_continue_setup()
            if state is ProfileFixtureState.READY:
                await screen.action_continue_setup()
                await self._wait_for_profile_write()
            return
        await screen.action_continue_setup()
        dialog = await self._mounted_editor()
        if state is ProfileFixtureState.INVALID_ANSWER:
            dialog._submit_typed("")
        elif state is ProfileFixtureState.CHOICE_QUESTION:
            dialog.query_one("#edit-options", OptionList).highlighted = None
        else:
            dialog.query_one("#edit-input", Input).value = ""
        if state is ProfileFixtureState.HELP_QUESTION:
            dialog.query_one("#edit-help-fold", DisclosureGroup).collapsed = False

    async def _mounted_editor(self) -> FieldEditScreen:
        """Wait for the pushed modal's controls before driving its answer."""
        dialog = self.screen
        if not isinstance(dialog, FieldEditScreen):
            raise TypeError("the profile question did not open")
        await asyncio.wait_for(dialog._mounted_event.wait(), timeout=10)
        return dialog

    async def _wait_for_profile_write(self) -> None:
        """Wait for UI settlement, including the persisted-result repaint."""
        screen = self.profile_screen
        for _ in range(1000):
            if screen._pending_write is None and screen._pending_completion is None:
                await asyncio.sleep(0)
                return
            await asyncio.sleep(0.01)
        raise TimeoutError("the profile capture did not settle its write")


def build_profile_fixture(state: ProfileFixtureState) -> ProfileCaptureHost:
    """Bind the same account doors the installed authenticated session uses."""
    with bundled_indexed_authority().operation() as operation:
        inputs = compose_authenticated_account_inputs(
            profile_id=require_active_bucket_id(),
            profile_label=PROFILE_LABEL,
            login_choices=profile_login_choices(),
            operation=operation,
        )
        overview = inputs.profile_overview
        if state in {
            ProfileFixtureState.REVIEW,
            ProfileFixtureState.READY,
            ProfileFixtureState.EDIT,
            ProfileFixtureState.OPTIONAL_EDIT,
            ProfileFixtureState.SAVED_EDIT,
        }:
            overview = _populate_required(inputs, overview)
        elif state is ProfileFixtureState.CHOICE_QUESTION:
            overview = inputs.persist_profile_field(
                "identity.tax_id", "12345678Z", overview.record_revision, overview.content_digest
            )
        if state in {ProfileFixtureState.EDIT, ProfileFixtureState.OPTIONAL_EDIT, ProfileFixtureState.SAVED_EDIT}:
            if inputs.complete_setup is None:
                raise ValueError("installed account composition has no completion door")
            overview = inputs.complete_setup()
    screen = ProfileManagerScreen(
        overview,
        persist=inputs.persist_profile_field,
        complete_setup=inputs.complete_setup,
        add_row=inputs.add_profile_row,
        update_row=inputs.update_profile_row,
        remove_row=inputs.remove_profile_row,
        list_plantilla_media=inputs.list_plantilla_media,
        set_plantilla_media=inputs.set_plantilla_media,
        remove_plantilla_media=inputs.remove_plantilla_media,
    )
    return ProfileCaptureHost(screen, state)


def profile_fixture_interfaces(state: ProfileFixtureState) -> tuple[str, ...]:
    """The production interfaces actually on screen at each opening frame."""
    if state in {
        ProfileFixtureState.TYPED_QUESTION,
        ProfileFixtureState.CHOICE_QUESTION,
        ProfileFixtureState.INVALID_ANSWER,
        ProfileFixtureState.HELP_QUESTION,
        ProfileFixtureState.OPTIONAL_EDIT,
    }:
        return ("cadrumo.entrypoints.tui.profile.overview.FieldEditScreen",)
    return ("cadrumo.entrypoints.tui.profile.overview.ProfileManagerScreen",)
