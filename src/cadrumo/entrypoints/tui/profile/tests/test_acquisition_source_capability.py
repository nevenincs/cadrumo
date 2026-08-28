"""Real proofs that the source-action panel renders credential posture honestly.

Drives the real `ProfileManagerScreen` with a real registered profile. The
posture rendered is built by the real `resolve_acquisition_source_credential_
postures` against a real `AuthState`, never a value invented in the test or
in the screen -- the screen only classifies what a `RequirementBadge` glyph
to show for a posture the application already resolved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.widgets import Button

from .....application.auth.models import AuthState
from .....application.user_profile.acquisition_sources import resolve_acquisition_source_credential_postures
from .....application.user_profile.overview import ProfileOverview, build_profile_overview
from .....application.user_profile.registration import register_profile_with_credentials
from .....entrypoints.tui.components.widgets import RequirementBadge, RequirementStatus
from .....tests.secure_sql import isolated_profile_storage_root
from ...components.host import ScreenHostApp
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "acquisition-capability-passphrase"  # noqa: S105 - isolated integration fixture


def _persist_not_exercised(path: str, value: str) -> ProfileOverview:
    raise AssertionError("no field edit is exercised by this test")


async def _launch_not_exercised(source: object) -> None:
    raise AssertionError("no launch is exercised by this test")


def _build_overview():
    return build_profile_overview(_register())


def _register():
    enrolled = register_profile_with_credentials(
        label="Acquisition capability subject",
        passphrase=_PASSPHRASE,
        facts=(),
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    from uuid import UUID

    from .....application.user_profile.login_session import login_profile
    from .....application.user_profile.profile_record_repository import ProfileRecordRepository

    login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
    return ProfileRecordRepository.for_current_session(UUID(enrolled.profile_id)).load(UUID(enrolled.profile_id))


@pytest.mark.asyncio
async def test_with_no_aeat_credential_every_source_shows_missing_and_is_disabled(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        postures = resolve_acquisition_source_credential_postures(AuthState())
        app = ProfileManagerScreen(
            _build_overview(),
            persist=_persist_not_exercised,
            launch_source=_launch_not_exercised,
            credential_postures=postures,
        )
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            card = app.query_one("#source-censal_review")
            badge = card.query_one("#source-credential-requirement", RequirementBadge)
            assert badge.status is RequirementStatus.REQUIRED_MISSING
            assert card.query_one(Button).disabled is True


@pytest.mark.asyncio
async def test_with_an_aeat_credential_on_file_every_source_shows_held_and_is_enabled(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        auth = AuthState(provider="certificate", authenticated_at=datetime.now(UTC))
        postures = resolve_acquisition_source_credential_postures(auth)
        app = ProfileManagerScreen(
            _build_overview(),
            persist=_persist_not_exercised,
            launch_source=_launch_not_exercised,
            credential_postures=postures,
        )
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            card = app.query_one("#source-filed_history")
            badge = card.query_one("#source-credential-requirement", RequirementBadge)
            assert badge.status is RequirementStatus.REQUIRED_PRESENT
            assert card.query_one(Button).disabled is False


@pytest.mark.asyncio
async def test_a_held_credential_does_not_override_a_missing_launch_door(tmp_path: Path) -> None:
    """A satisfied credential is necessary, not sufficient: the launch door still gates the button."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        auth = AuthState(provider="certificate", authenticated_at=datetime.now(UTC))
        postures = resolve_acquisition_source_credential_postures(auth)
        app = ProfileManagerScreen(
            _build_overview(),
            persist=_persist_not_exercised,
            credential_postures=postures,
        )
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            card = app.query_one("#source-censal_review")
            assert card.query_one(Button).disabled is True


@pytest.mark.asyncio
async def test_with_no_posture_supplied_the_panel_renders_no_credential_claim(tmp_path: Path) -> None:
    """Unknown posture is not the same claim as "missing" -- no badge is rendered at all."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = ProfileManagerScreen(
            _build_overview(),
            persist=_persist_not_exercised,
            launch_source=_launch_not_exercised,
        )
        async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            card = app.query_one("#source-censal_review")
            assert len(card.query(RequirementBadge)) == 0
            assert card.query_one(Button).disabled is False
