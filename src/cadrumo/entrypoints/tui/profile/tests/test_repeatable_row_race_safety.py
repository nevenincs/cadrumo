"""Race-safety proofs for repeatable profile-row edits in the manager.

These are deliberately manager-bound rather than private-store tests.  The
application row doors already prove their encrypted CAS behaviour; this file
proves that the TUI keeps the profile, stable row key, and displayed baseline
that the operator actually opened when it crosses that boundary.  The fake
doors are observable boundary probes, not substitutes for storage acceptance:
the installed cross-entrypoint lane exercises those doors for real.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence

import pytest
from textual.widgets import DataTable

from .....application.user_profile.capsule_record import ProfileRecordConflictError
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.i18n.render import tr
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...tests.manager_pilot import wait_until_settled
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (120, 40)
_PROFILE_A = "00000000-0000-4000-8000-0000000000a1"
_PROFILE_B = "00000000-0000-4000-8000-0000000000b2"
_SECTION = "activities"
_EDITED_ROW = "19"
_EDITED_PATH = f"{_SECTION}.{_EDITED_ROW}.description"


type UpdateRowDoor = Callable[[str, str, Mapping[str, str], Sequence[str], int, str], ProfileOverview]


def _digest(character: str) -> str:
    return character * 64


def _overview(
    *,
    profile_id: str = _PROFILE_A,
    revision: int = 7,
    digest: str = _digest("a"),
    descriptions: Mapping[str, str | None] | None = None,
    label: str = "Profile A",
) -> ProfileOverview:
    """Make one small but real manager projection with nonordinal row keys.

    The rows are intentionally 4 and 19.  A screen which uses visual order
    instead of the stable schema identity will call a door for the wrong row,
    and every test here catches that at its boundary.
    """
    values = descriptions or {"4": "First activity", _EDITED_ROW: "Later activity"}
    fields = tuple(
        field
        for row_key, description in values.items()
        for field in (
            ProfileFieldView(
                path=f"{_SECTION}.{row_key}.description",
                label="Description",
                value=description,
                masked=False,
                required=False,
                row_index=row_key,
            ),
            # This independent value keeps the row extant while its optional
            # description is explicitly cleared.
            ProfileFieldView(
                path=f"{_SECTION}.{row_key}.reference",
                label="Reference",
                value=f"ref-{row_key}",
                masked=False,
                required=False,
                row_index=row_key,
            ),
        )
    )
    return ProfileOverview(
        profile_id=profile_id,
        record_revision=revision,
        content_digest=digest,
        label=label,
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(ProfileSectionView(key=_SECTION, title="Activities", repeatable=True, fields=fields),),
    )


def _unreachable_persist(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
    raise AssertionError("a repeatable-row field must use update_row, never the scalar write door")


def _screen(overview: ProfileOverview, update: UpdateRowDoor) -> ProfileManagerScreen:
    return ProfileManagerScreen(overview, persist=_unreachable_persist, update_row=update)


def _notice(screen: ProfileManagerScreen) -> str:
    return screen.query_one("#manager-status", PinnedStatusBar).message


def _rendered_value(screen: ProfileManagerScreen, path: str) -> str:
    for table in screen.query(DataTable):
        for row_key in table.rows:
            if row_key.value == path:
                return str(table.get_row(row_key)[2])
    raise AssertionError(f"no rendered field for {path!r}")


@pytest.mark.asyncio
async def test_repeatable_edit_captures_stable_row_and_baseline_then_refuses_a_stale_conflict() -> None:
    """A row edit carries its original nonordinal identity and CAS witness."""
    opened = _overview()
    calls: list[tuple[str, str, Mapping[str, str], tuple[str, ...], int, str]] = []

    def stale_update(
        section: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, row_key, values, tuple(clear_fields), revision, digest))
        raise ProfileRecordConflictError("the record changed after this editor opened")

    screen = _screen(opened, stale_update)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("Corrected activity")
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, _EDITED_ROW, {"description": "Corrected activity"}, (), 7, _digest("a"))]
        assert screen.overview == opened, "a conflict must not optimistically repaint the stale edit"
        assert _rendered_value(screen, _EDITED_PATH) == "Later activity"
        assert _notice(screen) == tr("errors.fail.fail_storage_secure_object_revision_conflict")
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_a_row_removed_before_save_is_not_retargeted_or_recreated() -> None:
    """A stale edit of row 19 must not fall through to the first displayed row."""
    opened = _overview()
    calls: list[tuple[str, str, Mapping[str, str], tuple[str, ...], int, str]] = []

    def removed_update(
        section: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, row_key, values, tuple(clear_fields), revision, digest))
        # This is the CAS result once another editor has removed row 19.
        raise ProfileRecordConflictError("the targeted row no longer belongs to this baseline")

    screen = _screen(opened, removed_update)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("Must not recreate")
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, _EDITED_ROW, {"description": "Must not recreate"}, (), 7, _digest("a"))]
        assert _rendered_value(screen, f"{_SECTION}.4.description") == "First activity"
        assert _rendered_value(screen, _EDITED_PATH) == "Later activity"
        assert screen.overview == opened
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_repeated_repeatable_save_starts_one_mutation_and_refreshes_from_its_result() -> None:
    """A second activation while the first is landing never creates a second CAS command."""
    opened = _overview()
    refreshed = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"4": "First activity", _EDITED_ROW: "Saved once"},
    )
    release = threading.Event()
    calls: list[tuple[str, str, Mapping[str, str], tuple[str, ...], int, str]] = []

    def delayed_update(
        section: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, row_key, values, tuple(clear_fields), revision, digest))
        release.wait(timeout=5)
        return refreshed

    screen = _screen(opened, delayed_update)
    try:
        async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            apply = screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])
            apply("Saved once")
            await pilot.pause()
            assert screen._pending_write is not None, "the delayed first save must be in flight"

            apply("Saved twice")
            await pilot.pause()
            assert _notice(screen) == tr("flows.manager.edit.write_in_flight")

            release.set()
            await wait_until_settled(screen, pilot)
            assert calls == [(_SECTION, _EDITED_ROW, {"description": "Saved once"}, (), 7, _digest("a"))]
            assert screen.overview == refreshed
            assert _rendered_value(screen, _EDITED_PATH) == "Saved once"
            pilot.app.exit(None)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_cancel_before_a_repeatable_submission_calls_no_mutation_door() -> None:
    """Dismissing a dialog is unchanged, not an implicit clear or removal."""
    opened = _overview()
    calls: list[object] = []

    def unexpected_update(*_args: object) -> ProfileOverview:
        calls.append(_args)
        return opened

    screen = _screen(opened, unexpected_update)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])(None)
        await pilot.pause()

        assert calls == []
        assert screen._pending_write is None
        assert screen.overview == opened
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_navigation_during_a_landing_row_write_does_not_claim_a_rollback() -> None:
    """A thread-backed write stays bound and lands; quitting cannot call it cancelled."""
    opened = _overview()
    refreshed = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"4": "First activity", _EDITED_ROW: "Landed despite navigation"},
    )
    release = threading.Event()

    def delayed_update(
        _section: str,
        _row_key: str,
        _values: Mapping[str, str],
        _clear_fields: Sequence[str],
        _revision: int,
        _digest_value: str,
    ) -> ProfileOverview:
        release.wait(timeout=5)
        return refreshed

    screen = _screen(opened, delayed_update)
    try:
        async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("Landed despite navigation")
            await pilot.pause()
            assert screen._pending_write is not None

            await screen.action_quit()
            assert screen.is_running, "the page must remain while encrypted storage can still commit"
            assert _notice(screen) == tr("flows.manager.edit.write_in_flight")

            release.set()
            await wait_until_settled(screen, pilot)
            assert screen.overview == refreshed
            assert _rendered_value(screen, _EDITED_PATH) == "Landed despite navigation"
            pilot.app.exit(None)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_delayed_profile_a_result_cannot_replace_the_visible_profile_b() -> None:
    """An old completion is discarded after the visible profile has switched.

    ``_apply_overview`` is the narrow test seam standing in for the outer
    root's profile recomposition.  The important race is the same: A's worker
    started under A's baseline, B became visible, and A's result arrived late.
    """
    opened_a = _overview()
    completed_a = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"4": "First activity", _EDITED_ROW: "A late result"},
    )
    visible_b = _overview(
        profile_id=_PROFILE_B,
        revision=23,
        digest=_digest("c"),
        descriptions={"4": "B first", _EDITED_ROW: "B current"},
        label="Profile B",
    )
    release = threading.Event()
    calls: list[tuple[str, str, int, str]] = []

    def delayed_a_update(
        section: str,
        row_key: str,
        _values: Mapping[str, str],
        _clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, row_key, revision, digest))
        release.wait(timeout=5)
        return completed_a

    screen = _screen(opened_a, delayed_a_update)
    try:
        async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("A late result")
            await pilot.pause()
            assert screen._pending_write is not None

            await screen._apply_overview(visible_b)
            assert screen.overview == visible_b
            assert _rendered_value(screen, _EDITED_PATH) == "B current"

            release.set()
            await wait_until_settled(screen, pilot)
            assert calls == [(_SECTION, _EDITED_ROW, 7, _digest("a"))]
            assert screen.overview == visible_b
            assert _rendered_value(screen, _EDITED_PATH) == "B current"
            pilot.app.exit(None)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_blank_repeatable_edit_is_an_explicit_clear_and_refreshes_from_storage_projection() -> None:
    """Blank means clear only when the operator submits it; omission is not deletion."""
    opened = _overview()
    refreshed = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"4": "First activity", _EDITED_ROW: None},
    )
    calls: list[tuple[str, str, Mapping[str, str], tuple[str, ...], int, str]] = []

    def clear_update(
        section: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, row_key, values, tuple(clear_fields), revision, digest))
        return refreshed

    screen = _screen(opened, clear_update)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("")
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, _EDITED_ROW, {}, ("description",), 7, _digest("a"))]
        assert screen.overview == refreshed
        assert _rendered_value(screen, _EDITED_PATH) == ""
        # The sibling field makes the test distinguish a clear from removing
        # or reindexing the whole row.
        assert _rendered_value(screen, f"{_SECTION}.{_EDITED_ROW}.reference") == f"ref-{_EDITED_ROW}"
        pilot.app.exit(None)
