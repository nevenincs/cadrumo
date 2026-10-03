"""Profile review states reached through real local profile and UI doors.

Each capture provisions its own encrypted, synthetic profile. Required answers
are validated and saved through the application doors the profile worker runs;
completion uses the repository's guarded door. These fixtures never hand-build
a profile projection.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import override
from uuid import uuid4

from textual.events import Mount
from textual.widgets import Input, OptionList

from cadrumo.application.user_profile.fact_write import apply_manager_profile_field_mutation
from cadrumo.application.user_profile.overview import ProfileOverview, build_profile_overview
from cadrumo.application.user_profile.plantilla_media_rows import (
    PlantillaMediaWriteSurface,
    plantilla_media_years_of,
    remove_plantilla_media_year,
    set_plantilla_media_year,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.section_rows import (
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
    update_profile_repeatable_section_row,
)
from cadrumo.core.bucket_pointer import require_active_bucket_id
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from cadrumo.domain.user_profile.values import UserProfileRecord
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.widgets import ContentScroll, DisclosureGroup
from cadrumo.entrypoints.tui.profile.edit_screens import FieldEditScreen
from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
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


@dataclass(frozen=True, slots=True)
class ProfileReviewDoors:
    """The profile manager's doors over the application functions the profile worker executes."""

    profile_id: str
    label: str
    operation: PinnedAuthorityOperation

    def _project(self, record: UserProfileRecord) -> ProfileOverview:
        return build_profile_overview(record, label=self.label, schema=self.operation.profile_decode_context().schema)

    def overview(self) -> ProfileOverview:
        """Project the record as storage holds it now."""
        repository = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        )
        return self._project(repository.load(self.profile_id))

    def persist_profile_field(
        self, path: str, value: str, expected_revision: int, expected_content_digest: str
    ) -> ProfileOverview:
        """Validate and save one answer against the dialog's baseline."""
        return self._project(
            apply_manager_profile_field_mutation(
                profile_id=self.profile_id,
                path=path,
                value=value,
                expected_revision=expected_revision,
                expected_content_digest=expected_content_digest,
                profile_decode_context=self.operation.profile_decode_context(),
            )
        )

    def add_profile_row(
        self, section_key: str, values: Mapping[str, str], expected_revision: int, expected_content_digest: str
    ) -> ProfileOverview:
        """Append one repeatable-section row."""
        context = self.operation.profile_decode_context()
        applied = add_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section_key,
            values=values,
            schema=context.schema,
            profile_decode_context=context,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
        )
        return self._project(applied.record)

    def update_profile_row(
        self,
        section_key: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        expected_revision: int,
        expected_content_digest: str,
    ) -> ProfileOverview:
        """Change one repeatable-section row."""
        context = self.operation.profile_decode_context()
        applied = update_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section_key,
            row_key=row_key,
            values=values,
            clear_fields=clear_fields,
            schema=context.schema,
            profile_decode_context=context,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
        )
        return self._project(applied.record)

    def remove_profile_row(
        self, section_key: str, row_key: str, expected_revision: int, expected_content_digest: str
    ) -> ProfileOverview:
        """Remove one repeatable-section row."""
        context = self.operation.profile_decode_context()
        applied = remove_profile_repeatable_section_row(
            profile_id=self.profile_id,
            section_key=section_key,
            row_key=row_key,
            schema=context.schema,
            profile_decode_context=context,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
        )
        return self._project(applied.record)

    def list_plantilla_media(self) -> tuple[PlantillaMediaYear, ...]:
        """Read the recorded average workforce by year."""
        repository = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        )
        return plantilla_media_years_of(repository.load(self.profile_id))

    def set_plantilla_media(self, year: int, average_workforce: Decimal, state: PlantillaMediaState) -> ProfileOverview:
        """Record one year's average workforce from the manager."""
        set_plantilla_media_year(
            profile_id=self.profile_id,
            year=year,
            average_workforce=average_workforce,
            state=state,
            surface=PlantillaMediaWriteSurface.MANAGER,
            profile_decode_context=self.operation.profile_decode_context(),
        )
        return self.overview()

    def remove_plantilla_media(self, year: int) -> ProfileOverview:
        """Remove one year's average workforce from the manager."""
        remove_plantilla_media_year(
            profile_id=self.profile_id,
            year=year,
            surface=PlantillaMediaWriteSurface.MANAGER,
            profile_decode_context=self.operation.profile_decode_context(),
        )
        return self.overview()

    def complete_setup(self) -> ProfileOverview:
        """Promote setup to complete through the repository door ``complete-setup`` uses."""
        profiles = ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        )
        current = profiles.load(self.profile_id)
        return self._project(
            profiles.complete_setup(
                self.profile_id,
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
            )
        )


def profile_review_doors(operation: PinnedAuthorityOperation) -> ProfileReviewDoors:
    """Bind the active synthetic profile's doors under one pinned authority."""
    return ProfileReviewDoors(profile_id=require_active_bucket_id(), label=PROFILE_LABEL, operation=operation)


def _populate_required(inputs: ProfileReviewDoors, overview: ProfileOverview) -> ProfileOverview:
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
        if await self._reach_edit_state(screen, state):
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

    async def _reach_edit_state(self, screen: ProfileManagerScreen, state: ProfileFixtureState) -> bool:
        """Prepare an ongoing profile-edit state when requested."""
        if state not in {ProfileFixtureState.EDIT, ProfileFixtureState.OPTIONAL_EDIT, ProfileFixtureState.SAVED_EDIT}:
            return False
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
        return True

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
    """Bind the same application doors the profile worker runs for the installed session."""
    with bundled_indexed_authority().operation() as operation:
        inputs = profile_review_doors(operation)
        overview = inputs.overview()
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
