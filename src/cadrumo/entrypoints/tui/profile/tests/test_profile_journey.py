"""Real behavioral proofs for the five-stage profile journey shell.

Drives the real production schema through a real registered profile record
(`build_profile_presentation` resolves the one committed schema, never an
injectable one) and a real Textual `App`/pilot -- no mocks, no synthetic
projection. The load-bearing assertions are that navigation is linear, that
progressive disclosure genuinely groups by the D6 classification the
application already computed (never a re-derived requirement policy), and
that an inactive stage's body is unmounted -- not merely hidden -- so it
cannot become a keyboard trap.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from textual.widgets import Button

from .....application.user_profile.login_session import login_profile
from .....application.user_profile.presentation import build_profile_presentation
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....core.i18n import tr
from .....tests.secure_sql import isolated_profile_storage_root
from ...components.host import ScreenHostApp
from ...components.widgets import DisclosureGroup, RequirementBadge
from ..app import ProfileJourneyScreen, ProfileJourneyStage
from ..journey_status import overview_readiness_summary

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "profile-journey-passphrase"  # noqa: S105 - isolated integration fixture

_SIZE = (100, 30)


def _real_presentation(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Profile journey subject",
            passphrase=_PASSPHRASE,
            facts=(),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        return build_profile_presentation(record)


@pytest.mark.asyncio
async def test_only_the_active_stage_body_is_mounted_never_only_hidden(tmp_path: Path) -> None:
    """Moving off Overview must remove its body from the DOM, not merely style it away."""
    presentation = _real_presentation(tmp_path)
    app = ProfileJourneyScreen(presentation)
    async with ScreenHostApp(app).run_test(size=_SIZE) as pilot:
        await pilot.pause()
        assert app.query("#overview-summary")
        assert not app.query("#get-data-placeholder")

        await pilot.click("#btn-journey-next")
        await pilot.pause(0.1)

        assert not app.query("#overview-summary"), "the Overview body must be unmounted, not just hidden"
        assert app.query("#get-data-placeholder")


@pytest.mark.asyncio
async def test_navigation_is_linear_and_bounded_at_both_ends(tmp_path: Path) -> None:
    presentation = _real_presentation(tmp_path)
    app = ProfileJourneyScreen(presentation)
    async with ScreenHostApp(app).run_test(size=_SIZE) as pilot:
        await pilot.pause()
        previous = app.query_one("#btn-journey-previous", Button)
        next_button = app.query_one("#btn-journey-next", Button)
        assert previous.disabled, "Overview is the first stage; Previous must start disabled"
        assert not next_button.disabled

        for _ in range(len(ProfileJourneyStage) - 1):
            await pilot.click("#btn-journey-next")
            await pilot.pause(0.1)

        assert next_button.disabled, "Ready is the last stage; Next must be disabled there"
        assert app.query("#ready-stage-body")

        await pilot.click("#btn-journey-previous")
        await pilot.pause(0.1)
        assert not app.query("#ready-stage-body")
        assert app.query("#review-placeholder")


@pytest.mark.asyncio
async def test_stage_strip_advances_with_navigation(tmp_path: Path) -> None:
    presentation = _real_presentation(tmp_path)
    app = ProfileJourneyScreen(presentation)
    async with ScreenHostApp(app).run_test(size=_SIZE) as pilot:
        await pilot.pause()
        assert str(app.query_one("#stage-0").render()).startswith("\u25b8")

        await pilot.click("#btn-journey-next")
        await pilot.pause(0.1)

        assert str(app.query_one("#stage-0").render()).startswith("\u2713")
        assert str(app.query_one("#stage-1").render()).startswith("\u25b8")


@pytest.mark.asyncio
async def test_required_stage_groups_by_the_applications_own_classification_never_a_local_policy(
    tmp_path: Path,
) -> None:
    """A blank profile's needs-applicability rows must appear expanded, and the counts must
    match the settled presentation projection exactly -- this shell computes no requirement
    policy of its own."""
    presentation = _real_presentation(tmp_path)
    needs_applicability_paths = {
        field.path for field in presentation.fields if field.classification.value == "needs_applicability"
    }
    missing_paths = {
        field.path for field in presentation.fields if field.classification.value == "applicable_required_missing"
    }
    assert needs_applicability_paths, "a freshly registered profile must have at least one unassessed trigger"

    app = ProfileJourneyScreen(presentation)
    async with ScreenHostApp(app).run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-journey-next")
        await pilot.pause(0.1)
        await pilot.click("#btn-journey-next")
        await pilot.pause(0.1)

        rendered_ids = {widget.id for widget in app.query(RequirementBadge) if widget.id is not None}
        rendered_expanded_badges = sum(
            1
            for widget_id in rendered_ids
            if widget_id.startswith("required-needs-applicability-") or widget_id.startswith("required-missing-")
        )
        assert rendered_expanded_badges == len(needs_applicability_paths) + len(missing_paths)
        optional_groups = app.query(DisclosureGroup)
        if optional_groups:
            assert app.query_one("#required-optional-group", DisclosureGroup).collapsed is True


@pytest.mark.asyncio
async def test_ready_stage_readiness_line_matches_the_applications_own_ready_fact(tmp_path: Path) -> None:
    presentation = _real_presentation(tmp_path)
    app = ProfileJourneyScreen(presentation)
    async with ScreenHostApp(app).run_test(size=_SIZE) as pilot:
        await pilot.pause()
        for _ in range(len(ProfileJourneyStage) - 1):
            await pilot.click("#btn-journey-next")
            await pilot.pause(0.1)

        summary_line = str(app.query_one("#ready-summary").render())

    assert summary_line == overview_readiness_summary(presentation)
    assert presentation.ready is False, "a freshly registered profile with no facts cannot be filing-ready"
    assert summary_line == tr("profile.journey.ready.blocked")
