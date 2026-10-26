"""Profile capture frames prove real saved state and reachable production screens."""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Input, Static

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.components.widgets import DisclosureGroup
from cadrumo.entrypoints.tui.profile.edit_screens import FieldEditScreen
from cadrumo.entrypoints.tui.profile.setup_journey import ProfileSetupStage
from dev.tui.harness.profile_fixtures import (
    ProfileFixtureState,
    build_profile_fixture,
    profile_fixture_interfaces,
    profile_fixture_storage,
    profile_review_doors,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", list(ProfileFixtureState))
async def test_profile_frames_reach_their_declared_state_and_keep_real_saved_facts(state: ProfileFixtureState) -> None:
    """A successful render cannot conceal an unfinished write or a pretend success."""
    with profile_fixture_storage():
        app = build_profile_fixture(state)
        async with app.run_test(size=(80, 24)) as pilot:
            await asyncio.wait_for(app.frame_ready.wait(), timeout=15)
            await pilot.pause()
            screen = app.profile_screen
            assert f"{type(app.screen).__module__}.{type(app.screen).__qualname__}" in profile_fixture_interfaces(state)
            editing = state in {
                ProfileFixtureState.EDIT,
                ProfileFixtureState.OPTIONAL_EDIT,
                ProfileFixtureState.SAVED_EDIT,
            }
            assert screen._onboarding is not editing
            if editing:
                assert screen.query_one("#manager-sources-fold", DisclosureGroup).collapsed
            completed = editing or state is ProfileFixtureState.READY
            assert (screen.overview.setup_state is ProfileSetupState.COMPLETE) is completed
            if state in {
                ProfileFixtureState.OVERVIEW,
                ProfileFixtureState.GET_DATA,
                ProfileFixtureState.REQUIRED,
                ProfileFixtureState.REVIEW,
                ProfileFixtureState.READY,
            }:
                assert screen._setup_stage is ProfileSetupStage(state.value.replace("-", "_"))
            if state in {ProfileFixtureState.REVIEW, ProfileFixtureState.READY} or editing:
                assert not screen.overview.missing_required
                assert any(
                    not field.required and not field.present
                    for section in screen.overview.sections
                    for field in section.fields
                )
            if isinstance(app.screen, FieldEditScreen):
                dialog = app.screen
                assert dialog._field.required is (state is not ProfileFixtureState.OPTIONAL_EDIT)
                assert dialog.query_one("#edit-requirement", Static).render()
                assert dialog.query_one("#edit-help-fold", DisclosureGroup).collapsed is (
                    state is not ProfileFixtureState.HELP_QUESTION
                )
                if state is ProfileFixtureState.INVALID_ANSWER:
                    assert str(dialog.query_one("#edit-refusal", Static).render())
                    assert dialog.query_one("#edit-input", Input).value == ""
                    assert "identity.tax_id" in screen.overview.missing_required
            if state is ProfileFixtureState.SAVED_EDIT:
                with bundled_indexed_authority().operation() as operation:
                    saved = profile_review_doors(operation).overview()
                field = next(
                    field for section in saved.sections for field in section.fields if field.path == "identity.name"
                )
                assert field.value == "Synthetic edited name"
                assert saved.setup_state is ProfileSetupState.COMPLETE


@pytest.mark.asyncio
async def test_new_capture_starts_incomplete_after_a_previous_capture_finished() -> None:
    """Separate provisioning prevents saved answers leaking into question frames."""
    with profile_fixture_storage():
        ready = build_profile_fixture(ProfileFixtureState.READY)
        async with ready.run_test(size=(80, 24)) as pilot:
            await asyncio.wait_for(ready.frame_ready.wait(), timeout=15)
            await pilot.pause()
            assert ready.profile_screen.overview.setup_state is ProfileSetupState.COMPLETE
    with profile_fixture_storage():
        fresh = build_profile_fixture(ProfileFixtureState.OVERVIEW)
        async with fresh.run_test(size=(80, 24)) as pilot:
            await asyncio.wait_for(fresh.frame_ready.wait(), timeout=15)
            await pilot.pause()
            assert fresh.profile_screen.overview.setup_state is ProfileSetupState.INCOMPLETE
            assert "identity.tax_id" in fresh.profile_screen.overview.missing_required
