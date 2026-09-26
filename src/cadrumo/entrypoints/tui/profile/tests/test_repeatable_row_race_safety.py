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
from textual.widgets import Button, DataTable, Input, Label, OptionList

from .....application.user_profile.capsule_record import ProfileRecordConflictError
from .....application.user_profile.overview import (
    ProfileFieldChoice,
    ProfileFieldView,
    ProfileOverview,
    ProfileSectionView,
)
from .....core.i18n.render import tr
from .....domain.user_profile.errors import ProfileSchemaValidationError
from .....domain.user_profile.schema import ProfileFieldType
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...tests.manager_pilot import wait_until_settled
from ..overview import ProfileManagerScreen, RepeatableRowAddScreen, RepeatableRowRemoveScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (120, 40)
_PROFILE_A = "00000000-0000-4000-8000-0000000000a1"
_PROFILE_B = "00000000-0000-4000-8000-0000000000b2"
_SECTION = "activities"
_EDITED_ROW = "19"
_EDITED_PATH = f"{_SECTION}.{_EDITED_ROW}.description"


type UpdateRowDoor = Callable[[str, str, Mapping[str, str], Sequence[str], int, str], ProfileOverview]
type AddRowDoor = Callable[[str, Mapping[str, str], int, str], ProfileOverview]
type RemoveRowDoor = Callable[[str, str, int, str], ProfileOverview]


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
        sections=(
            ProfileSectionView(
                key=_SECTION, title="Activities", summary="Economic activities", repeatable=True, fields=fields
            ),
        ),
    )


def _empty_repeatable_overview(
    *,
    profile_id: str = _PROFILE_A,
    revision: int = 7,
    digest: str = _digest("a"),
    fields: Sequence[ProfileFieldView] | None = None,
    label: str = "Profile A",
) -> ProfileOverview:
    """Make the blank schema template a real empty repeatable section renders.

    An empty section still projects its declared unindexed fields so its add
    modal can collect a first row.  That is deliberately distinct from a
    section with no fields at all: the latter would make an unusable empty
    dialog and hide a schema regression behind a test fixture.
    """
    template = (
        tuple(fields)
        if fields is not None
        else (
            ProfileFieldView(
                path=f"{_SECTION}.description",
                label="Description",
                value=None,
                masked=False,
                required=False,
            ),
            ProfileFieldView(
                path=f"{_SECTION}.reference",
                label="Reference",
                value=None,
                masked=False,
                required=False,
            ),
        )
    )
    return ProfileOverview(
        profile_id=profile_id,
        record_revision=revision,
        content_digest=digest,
        label=label,
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key=_SECTION, title="Activities", summary="Economic activities", repeatable=True, fields=template
            ),
        ),
    )


def _unreachable_persist(_path: str, _value: str, _revision: int, _digest: str) -> ProfileOverview:
    raise AssertionError("a repeatable-row field must use update_row, never the scalar write door")


def _screen(
    overview: ProfileOverview,
    update: UpdateRowDoor | None = None,
    *,
    add: AddRowDoor | None = None,
    remove: RemoveRowDoor | None = None,
) -> ProfileManagerScreen:
    return ProfileManagerScreen(
        overview,
        persist=_unreachable_persist,
        add_row=add,
        update_row=update,
        remove_row=remove,
    )


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


@pytest.mark.asyncio
async def test_late_older_result_for_the_same_profile_is_discarded_with_an_honest_notice() -> None:
    """A different revision of A is as unsafe to repaint as a result for B."""
    opened = _overview()
    visible_newer = _overview(
        revision=9,
        digest=_digest("d"),
        descriptions={"4": "First activity", _EDITED_ROW: "Changed elsewhere"},
    )
    late_older = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"4": "First activity", _EDITED_ROW: "Late worker result"},
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
        return late_older

    screen = _screen(opened, delayed_update)
    try:
        async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            screen._apply_edit_for(screen._field_by_key[_EDITED_PATH])("Late worker result")
            await pilot.pause()
            assert screen._pending_write is not None

            await screen._apply_overview(visible_newer)
            assert screen.overview == visible_newer
            assert _rendered_value(screen, _EDITED_PATH) == "Changed elsewhere"

            release.set()
            await wait_until_settled(screen, pilot)

            assert screen.overview == visible_newer
            assert _rendered_value(screen, _EDITED_PATH) == "Changed elsewhere"
            assert _notice(screen) == tr("flows.manager.edit.stale_result")
            assert screen.query_one("#manager-status", PinnedStatusBar).tone == "error"
            pilot.app.exit(None)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_empty_repeatable_section_opens_an_add_modal_and_refreshes_after_success() -> None:
    """The blank schema template is an add affordance, not a nonexistent base row."""
    opened = _empty_repeatable_overview()
    refreshed = _overview(
        revision=8,
        digest=_digest("b"),
        descriptions={"23": "First activity"},
    )
    calls: list[tuple[str, Mapping[str, str], int, str]] = []

    def add(
        section: str,
        values: Mapping[str, str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, values, revision, digest))
        return refreshed

    screen = _screen(opened, add=add)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._open_add_row(_SECTION)
        await pilot.pause()

        dialog = pilot.app.screen
        assert isinstance(dialog, RepeatableRowAddScreen)
        dialog.query_one("#row-input-0", Input).value = "First activity"
        dialog.query_one("#btn-row-save", Button).press()
        await pilot.pause()
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, {"description": "First activity"}, 7, _digest("a"))]
        assert screen.overview == refreshed
        assert _rendered_value(screen, f"{_SECTION}.23.description") == "First activity"
        assert _notice(screen) == tr("flows.manager.edit.saved")
        assert screen.query_one("#manager-status", PinnedStatusBar).tone == "success"
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_empty_row_add_uses_choice_lists_and_submits_their_stored_tokens() -> None:
    """Boolean and enum labels are display-only; the row door receives canonical tokens."""
    fields = (
        ProfileFieldView(
            path=f"{_SECTION}.description",
            label="Description",
            value=None,
            masked=False,
            required=False,
        ),
        ProfileFieldView(
            path=f"{_SECTION}.enabled",
            label="Enabled",
            value=None,
            masked=False,
            required=False,
            field_type=ProfileFieldType.BOOLEAN,
            choices=(
                ProfileFieldChoice(value="true", label="Yes"),
                ProfileFieldChoice(value="false", label="No"),
            ),
        ),
        ProfileFieldView(
            path=f"{_SECTION}.classification",
            label="Classification",
            value=None,
            masked=False,
            required=False,
            field_type=ProfileFieldType.ENUM,
            choices=(
                ProfileFieldChoice(value="ordinary", label="Ordinary activity"),
                ProfileFieldChoice(value="special", label="Special activity"),
            ),
        ),
    )
    opened = _empty_repeatable_overview(fields=fields)
    refreshed = _overview(revision=8, digest=_digest("b"), descriptions={"23": "First activity"})
    calls: list[tuple[str, Mapping[str, str], int, str]] = []

    def add(
        section: str,
        values: Mapping[str, str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, values, revision, digest))
        return refreshed

    screen = _screen(opened, add=add)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._open_add_row(_SECTION)
        await pilot.pause()

        dialog = pilot.app.screen
        assert isinstance(dialog, RepeatableRowAddScreen)
        dialog.query_one("#row-input-0", Input).value = "First activity"
        enabled = dialog.query_one("#row-option-1", OptionList)
        classification = dialog.query_one("#row-option-2", OptionList)
        assert enabled.option_count == 2
        assert classification.option_count == 2
        assert not dialog.query("#row-input-1")
        assert not dialog.query("#row-input-2")
        enabled.highlighted = 1
        classification.highlighted = 0
        dialog.query_one("#btn-row-save", Button).press()
        await pilot.pause()
        await wait_until_settled(screen, pilot)

        assert calls == [
            (
                _SECTION,
                {
                    "description": "First activity",
                    "enabled": "false",
                    "classification": "ordinary",
                },
                7,
                _digest("a"),
            )
        ]
        assert screen.overview == refreshed
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_confirmed_remove_keeps_the_selected_stable_row_identity_and_refreshes() -> None:
    """Confirmation names and deletes row 19, never whichever row is first on screen."""
    opened = _overview()
    refreshed = _overview(revision=8, digest=_digest("b"), descriptions={"4": "First activity"})
    calls: list[tuple[str, str, int, str]] = []

    def remove(section: str, row_key: str, revision: int, digest: str) -> ProfileOverview:
        calls.append((section, row_key, revision, digest))
        return refreshed

    screen = _screen(opened, remove=remove)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        table = screen._table_by_section[_SECTION]
        table.move_cursor(row=table.get_row_index(_EDITED_PATH))
        screen._open_remove_selected_row(_SECTION)
        await pilot.pause()

        dialog = pilot.app.screen
        assert isinstance(dialog, RepeatableRowRemoveScreen)
        confirmation = str(dialog.query_one("#edit-label", Label).render())
        assert _SECTION in confirmation
        assert _EDITED_ROW in confirmation
        dialog.query_one("#btn-row-remove", Button).press()
        await pilot.pause()
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, _EDITED_ROW, 7, _digest("a"))]
        assert screen.overview == refreshed
        assert _EDITED_PATH not in screen._field_by_key
        assert _notice(screen) == tr("flows.manager.edit.saved")
        assert screen.query_one("#manager-status", PinnedStatusBar).tone == "success"
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_add_validation_refusal_never_reports_a_success_or_refreshes_the_page() -> None:
    """An add door's typed validation refusal leaves the operator on the original record."""
    opened = _empty_repeatable_overview()
    calls: list[tuple[str, Mapping[str, str], int, str]] = []

    def refused_add(
        section: str,
        values: Mapping[str, str],
        revision: int,
        digest: str,
    ) -> ProfileOverview:
        calls.append((section, values, revision, digest))
        raise ProfileSchemaValidationError(context={"section": section})

    screen = _screen(opened, add=refused_add)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        screen._open_add_row(_SECTION)
        await pilot.pause()
        dialog = pilot.app.screen
        assert isinstance(dialog, RepeatableRowAddScreen)
        dialog.query_one("#row-input-0", Input).value = "Rejected activity"
        dialog.query_one("#btn-row-save", Button).press()
        await pilot.pause()
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, {"description": "Rejected activity"}, 7, _digest("a"))]
        assert screen.overview == opened
        status = screen.query_one("#manager-status", PinnedStatusBar)
        assert status.tone == "error"
        assert status.message
        assert status.message != tr("flows.manager.edit.saved")
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_remove_persistence_failure_never_reports_a_success_or_refreshes_the_page() -> None:
    """A failed confirmed removal stays visibly failed rather than looking committed."""
    opened = _overview()
    calls: list[tuple[str, str, int, str]] = []

    def failed_remove(section: str, row_key: str, revision: int, digest: str) -> ProfileOverview:
        calls.append((section, row_key, revision, digest))
        raise OSError("secure capsule unavailable")

    screen = _screen(opened, remove=failed_remove)
    async with ScreenHostApp(screen).run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        table = screen._table_by_section[_SECTION]
        table.move_cursor(row=table.get_row_index(_EDITED_PATH))
        screen._open_remove_selected_row(_SECTION)
        await pilot.pause()
        dialog = pilot.app.screen
        assert isinstance(dialog, RepeatableRowRemoveScreen)
        dialog.query_one("#btn-row-remove", Button).press()
        await pilot.pause()
        await wait_until_settled(screen, pilot)

        assert calls == [(_SECTION, _EDITED_ROW, 7, _digest("a"))]
        assert screen.overview == opened
        assert _rendered_value(screen, _EDITED_PATH) == "Later activity"
        status = screen.query_one("#manager-status", PinnedStatusBar)
        assert status.tone == "error"
        assert status.message == tr("flows.manager.edit.write_failed")
        assert status.message != tr("flows.manager.edit.saved")
        pilot.app.exit(None)
