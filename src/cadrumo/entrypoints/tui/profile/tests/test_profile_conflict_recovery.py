"""A stale wizard page recovers its baseline without replaying a refused edit."""

from __future__ import annotations

import pytest
from textual.widgets import Input

from cadrumo_client.transport.profile_mutations import ProfileMutationRunError

from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationTerminalCondition
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...tests.manager_pilot import wait_until_settled
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _overview(revision: int, value: str) -> ProfileOverview:
    return ProfileOverview(
        profile_id="00000000-0000-4000-8000-0000000000a1",
        label="Synthetic profile",
        record_revision=revision,
        content_digest=f"{revision:064x}",
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key="identity",
                title="Identity",
                summary="",
                repeatable=False,
                fields=(
                    ProfileFieldView(
                        path="identity.name",
                        label="Given name",
                        value=value,
                        masked=False,
                        required=True,
                    ),
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_cached_wizard_and_remote_conflict_allow_a_fresh_explicit_edit() -> None:
    current = _overview(2, "Current name")
    calls: list[tuple[str, str, int, str]] = []

    def persist(path: str, value: str, revision: int, digest: str) -> ProfileOverview:
        nonlocal current
        calls.append((path, value, revision, digest))
        if revision != current.record_revision:
            raise ProfileMutationRunError(
                operation_id="a" * 64,
                code="FAIL_PROFILE_RECORD_CONFLICT",
                terminal_condition=OperationTerminalCondition.FAILED,
                effect=OperationEffect.NONE,
            )
        current = _overview(revision + 1, value)
        return current

    screen = ProfileManagerScreen(
        _overview(1, "Old name"),
        persist=persist,
        refresh_overview_language=lambda: current,
    )
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert screen.overview.record_revision == 2
        screen._open_field_editor(screen.overview.sections[0].fields[0])
        await pilot.pause()
        assert pilot.app.screen.query_one("#edit-input", Input).value == "Current name"
        current = _overview(3, "Another frontend")
        pilot.app.screen.query_one("#edit-input", Input).value = "Refused draft"
        await pilot.click("#btn-edit-save")
        await wait_until_settled(screen, pilot)
        assert screen.overview.record_revision == 3
        assert screen.query_one("#manager-status", PinnedStatusBar).message == tr("flows.manager.edit.conflict")
        assert len(calls) == 1
        assert current.sections[0].fields[0].value == "Another frontend"
        screen._open_field_editor(screen.overview.sections[0].fields[0])
        await pilot.pause()
        pilot.app.screen.query_one("#edit-input", Input).value = "Explicit new edit"
        await pilot.click("#btn-edit-save")
        await wait_until_settled(screen, pilot)
        assert calls[-1] == ("identity.name", "Explicit new edit", 3, f"{3:064x}")
        assert screen.overview.record_revision == 4
