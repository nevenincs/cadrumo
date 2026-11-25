"""An empty box must not delete a field the schema says must be filled.

The manager turns a blank submission into a CLEAR, which is right for an
optional field and wrong for a required one: it asks to remove something
the profile is not allowed to be without. Dismissing the dialog is how
"leave this alone" is already expressed, so an empty box has no second
meaning to preserve.

The refusal sits at the box rather than only at the write door because the
door defers completeness for a profile still in setup — which is exactly
when an operator is typing into these fields. The two guards cover
different halves and neither is redundant.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input, Static

from ....application.user_profile.overview import ProfileOverview
from ..components.host import ScreenHostApp
from ..components.status import PinnedStatusBar
from ..profile.overview import ProfileManagerScreen
from .manager_pilot import wait_until_settled
from .manager_subject_profile import (
    manager_subject_overview,
    manager_subject_persist,
    manager_subject_stored_facts,
    registered_manager_subject,
    write_manager_subject_field,
)
from .settling import settle

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_CREDENTIAL_INPUT = "manager-required-field-operator-secret"
_LABEL = "Required Field Subject"
_REQUIRED_PATH = "identity.tax_id"
_OPTIONAL_PATH = "identity.name"

#: A typed field the door rejects a malformed value for in either
#: completeness mode, used to prove the screen survives a refusal.
_MALFORMED_PATH = "auth.fecha_validez"


def _live_overview(label: str = _LABEL):
    return manager_subject_overview(label=label, passphrase=_CREDENTIAL_INPUT)


def _write(path: str, value: str) -> ProfileOverview:
    """The production write door, so an edit here travels the real path."""
    return write_manager_subject_field(label=_LABEL, passphrase=_CREDENTIAL_INPUT, path=path, value=value)


_persist = manager_subject_persist(label=_LABEL, passphrase=_CREDENTIAL_INPUT)


def _stored() -> dict[str, object | None]:
    return manager_subject_stored_facts(label=_LABEL, passphrase=_CREDENTIAL_INPUT)


def _notice(app: ProfileManagerScreen) -> str:
    return app.query_one("#manager-status", PinnedStatusBar).message


async def _submit(app, pilot, path: str, value: str) -> None:
    """Drive one real edit: open the dialog, type, press save."""
    from ..profile.edit_screens import FieldEditScreen

    field = app._field_by_key[path]
    app.app.push_screen(FieldEditScreen(field), app._apply_edit_for(field))
    await settle(pilot)
    app.app.screen.query_one("#edit-input", Input).value = value
    await pilot.click("#btn-edit-save")
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_blank_submission_on_a_required_field_does_not_clear_it(tmp_path) -> None:
    """The value on the record must be exactly what it was before the edit."""
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        _write(_REQUIRED_PATH, "12345678Z")
        assert _stored().get(_REQUIRED_PATH) == "12345678Z", "fixture must start with a value to lose"

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _submit(app, pilot, _REQUIRED_PATH, "")
            assert str(app.app.screen.query_one("#edit-refusal", Static).content)
            assert app.app.screen is not app, "the question stays open for correction"
            pilot.app.exit(None)

        assert _stored().get(_REQUIRED_PATH) == "12345678Z"


@pytest.mark.asyncio
async def test_a_whitespace_only_submission_on_a_required_field_does_not_clear_it(tmp_path) -> None:
    """Spaces are blank to every reader, so they must not delete the value either."""
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        _write(_REQUIRED_PATH, "12345678Z")

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _submit(app, pilot, _REQUIRED_PATH, "   ")
            pilot.app.exit(None)

        assert _stored().get(_REQUIRED_PATH) == "12345678Z"


@pytest.mark.asyncio
async def test_a_blank_submission_on_an_optional_field_still_clears_it(tmp_path) -> None:
    """The refusal must be scoped to required fields, not to blanking in general.

    Without this the previous behaviour could be lost wholesale and the
    two tests above would still pass, so this is what keeps the guard
    narrow rather than merely present.
    """
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        _write(_OPTIONAL_PATH, "Ada Lovelace")
        assert _stored().get(_OPTIONAL_PATH) == "Ada Lovelace"

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            await _submit(app, pilot, _OPTIONAL_PATH, "")
            await wait_until_settled(app, pilot)
            pilot.app.exit(None)

        assert _stored().get(_OPTIONAL_PATH) is None


@pytest.mark.asyncio
async def test_a_write_door_refusal_is_reported_rather_than_taking_the_screen_down(tmp_path) -> None:
    """A value the door rejects must not drop the whole screen.

    The manager persists edit by edit with the operator mid-page, so an
    uncaught refusal costs them the page over one rejected value — the
    same reasoning the action buttons already carry. Driven with a
    malformed date rather than a blank required field because shape is
    validated in both completeness modes, so the refusal does not depend
    on the profile's lifecycle state.
    """
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await settle(pilot)
            app._persist(
                _MALFORMED_PATH,
                "not-a-date",
                app.overview.record_revision,
                app.overview.content_digest,
            )
            # The write runs on a worker thread and the refusal reaches the
            # notice line only when its completion is delivered back, so a
            # bare `pause` reads the page a beat early and finds it empty --
            # intermittently, and more often the busier the machine.
            await wait_until_settled(app, pilot)
            assert app.is_running, "the refusal must not have taken the screen down"
            assert _notice(app), "the refusal must be shown to the operator"
            pilot.app.exit(None)

        assert _MALFORMED_PATH not in _stored(), "a refused value must not reach the record"
