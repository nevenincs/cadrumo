"""An empty box on a masked field must not delete what the operator cannot see.

A masked field's dialog opens EMPTY on purpose: the overview carries the
mask placeholder rather than the value, so pre-filling would submit a row
of dots back as the literal new value. But an empty box is a CLEAR at the
write door, and every masked field is optional -- so the guard that stops
a blank submission deleting a REQUIRED field protects exactly the fields
that cannot suffer this and misses exactly the ones that can.

The operator's reading of the gesture is what decides the fix. They were
never shown the value they would be preserving, so an empty box means "I
typed nothing", which is "leave this alone" -- not "delete it". The
ability to delete is not removed, it is given its own gesture, and these
tests hold both halves: the accident cannot destroy, and the deliberate
act still can.

The enum half of the dialog carries the same fault under a different
shape. It cannot clear -- it only ever writes a declared token -- but the
list highlights its first row the moment it takes focus, so opening an
enum field and pressing enter writes a token the operator never chose.
For a masked enum that would overwrite a secret, since the placeholder
matches no token and the dialog can therefore never find the current one.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, OptionList

from ....application.user_profile import (
    MASKED_PLACEHOLDER,
    ProfileFieldChoice,
    ProfileFieldView,
    build_profile_overview,
    login_profile,
    register_profile_with_credentials,
)
from ....core import require_active_bucket_id
from ....entrypoints.cli import persist_active_profile_field
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..profile.overview import ProfileManagerApp
from .manager_pilot import wait_until_settled

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-masked-field-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Masked Field Subject"

#: A masked, optional field: the exact shape an accidental blank destroys.
_MASKED_PATH = "auth.numero_soporte"
_MASKED_VALUE = "SUPPORT-0042"

#: Unmasked and optional, so emptying its box still means what it always did.
_PLAIN_PATH = "identity.name"

#: An unanswered enum, where the list's own highlight is the hazard.
_ENUM_PATH = "renta_taxpayer.sex"


def _ensure_logged_in() -> None:
    """Unlock the registered profile so the capsule will serve its record.

    Registration closes its own session and the custody capsule is the sole
    profile authority, so every read or write door below needs an authenticated
    session. Logging in derives the same DEK the capsule was sealed under.
    """
    login_profile(name=_LABEL, passphrase_callback=lambda: _PASSWORD)


def _live_overview():
    _ensure_logged_in()
    record = load_test_profile_record(require_active_bucket_id())
    return build_profile_overview(record, label=_LABEL)


def _persist(path: str, value: str):
    """The production write door, so an edit here travels the real path."""
    _ensure_logged_in()
    return persist_active_profile_field(path, value, label=_LABEL)


def _stored() -> dict[str, object | None]:
    _ensure_logged_in()
    reloaded = load_test_profile_record(require_active_bucket_id())
    return {fact.path: fact.value for fact in reloaded.facts}


def _open(app, field):
    """Open one field's dialog exactly as selecting its row does."""
    from ..profile.overview import FieldEditScreen

    app.push_screen(FieldEditScreen(field), app._apply_edit_for(field))


@pytest.mark.asyncio
async def test_the_masked_field_under_test_really_is_masked_and_optional(tmp_path) -> None:
    """Without this the other tests could pass on a field that was never at risk.

    Masking is being reclassified field by field, and an optional masked
    field is the whole precondition for the loss: the required guard
    already covers the rest. If this field stops being either, these
    tests stop proving anything and must be pointed at one that is.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        field = next(
            found for section in _live_overview().sections for found in section.fields if found.path == _MASKED_PATH
        )
        assert field.masked, f"{_MASKED_PATH} must be masked, or an empty box is not a blind one"
        assert not field.required, f"{_MASKED_PATH} must be optional, or the required guard already saves it"
        assert field.value == MASKED_PLACEHOLDER, f"the overview must withhold the value, but carried {field.value!r}"


@pytest.mark.asyncio
async def test_saving_a_masked_field_without_typing_does_not_clear_it(tmp_path) -> None:
    """The headline: pressing save on an untouched dialog must lose nothing.

    The operator opens the row, sees an empty box, and presses save
    believing they changed nothing. Before this guard that emptiness was
    submitted as a clear and the stored value was destroyed with no
    warning of any kind.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)
        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE, "fixture must start with a value to lose"

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            assert app.screen.query_one("#edit-input", Input).value == "", (
                "the dialog must still open empty, or this is not the gesture under test"
            )
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE


@pytest.mark.asyncio
async def test_pressing_enter_in_an_untouched_masked_box_does_not_clear_it(tmp_path) -> None:
    """The keyboard path submits without the button, and must be just as safe.

    Enter in the input is the faster of the two ways to dismiss the
    dialog and the likelier one for an operator who opened the row to
    look rather than to edit.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            await pilot.press("enter")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE


@pytest.mark.asyncio
async def test_whitespace_typed_into_a_masked_box_does_not_clear_it(tmp_path) -> None:
    """Spaces read as blank everywhere else, so they must not delete here either."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "   "
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE


@pytest.mark.asyncio
async def test_a_masked_field_can_still_be_deliberately_cleared(tmp_path) -> None:
    """Losing the accident must not cost the operator the deliberate act.

    This is what keeps the guard narrow rather than a blanket refusal to
    ever empty a masked field: without it the whole ability could be
    removed and every test above would still pass.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)
        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            await pilot.click("#btn-edit-clear")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_MASKED_PATH) is None


@pytest.mark.asyncio
async def test_the_clear_gesture_is_offered_only_where_the_box_cannot_express_it(tmp_path) -> None:
    """An unmasked field already expresses a clear by being emptied.

    The button exists because a masked box cannot say "delete this" --
    not as a second way to do what emptying already does. Offering it
    everywhere would be harmless but would misdescribe why it is there,
    and offering it on a field holding nothing would promise a deletion
    with nothing to delete.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_PLAIN_PATH, "Ada Lovelace")

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()

            _open(app, app._field_by_key[_PLAIN_PATH])
            await pilot.pause()
            assert not app.screen.query("#btn-edit-clear"), (
                "an unmasked field's own box already says 'delete this' by being emptied"
            )
            app.screen.dismiss(None)
            await pilot.pause()

            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            assert not app.screen.query("#btn-edit-clear"), (
                "a masked field holding nothing has nothing to offer to clear"
            )
            app.exit(None)


@pytest.mark.asyncio
async def test_an_unmasked_field_is_still_cleared_by_emptying_its_box(tmp_path) -> None:
    """The new reading of an empty box must not have leaked past masked fields.

    An operator who deletes a value they can see means it. Widening the
    guard to every field would turn that into a silent no-op, which is
    the opposite failure and just as surprising.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_PLAIN_PATH, "Ada Lovelace")
        assert _stored().get(_PLAIN_PATH) == "Ada Lovelace"

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_PLAIN_PATH])
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = ""
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_PLAIN_PATH) is None


@pytest.mark.asyncio
async def test_the_clear_button_is_not_the_one_enter_reaches(tmp_path) -> None:
    """A destructive button must not be what a stray keystroke presses.

    Enter in the dialog belongs to the input, and the primary button is
    save. If clearing were reachable by the same reflex the guard above
    removes, the fix would have moved the accident rather than closed it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, app._field_by_key[_MASKED_PATH])
            await pilot.pause()
            assert app.screen.focused is app.screen.query_one("#edit-input", Input), (
                "the box must hold focus, so enter submits rather than pressing a button"
            )
            clear = app.screen.query_one("#btn-edit-clear", Button)
            assert "-primary" not in clear.classes, "the destructive button must not be the emphasised one"
            app.exit(None)


# ── the enum half of the same dialog ─────────────────────────────────────


@pytest.mark.asyncio
async def test_an_enum_dialog_pre_selects_nothing_it_cannot_confirm_is_current(tmp_path) -> None:
    """Opening an unanswered enum and pressing enter must write nothing.

    The list highlights its first row on focus, so before this the dialog
    arrived already pointing at a token the operator had not chosen and
    enter wrote it. Nothing is lost on an unanswered field, but the
    gesture is the same one the masked guard exists to disarm, and the
    operator reads it the same way.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_ENUM_PATH]
            assert field.choices, f"{_ENUM_PATH} must offer a closed answer set for this to test anything"
            assert not field.present, "the field must start unanswered, or the dialog would rightly pre-select"

            _open(app, field)
            await pilot.pause()
            assert app.screen.query_one("#edit-options", OptionList).highlighted is None, (
                "no token may be pre-selected when none of them is what the field holds"
            )
            await pilot.press("enter")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _ENUM_PATH not in _stored(), "an unchosen token must not have been written"


@pytest.mark.asyncio
async def test_an_enum_dialog_still_pre_selects_the_token_the_field_holds(tmp_path) -> None:
    """The answered case must keep its highlight, or the fix costs the feature.

    An operator opening a field they have already answered should see
    which answer it is. Without this the guard above could be satisfied
    by never highlighting anything.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_ENUM_PATH, "M")

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_ENUM_PATH]
            _open(app, field)
            await pilot.pause()
            highlighted = app.screen.query_one("#edit-options", OptionList).highlighted
            assert highlighted is not None, "an answered enum must show which answer it holds"
            assert field.choices[highlighted].value == "M"
            app.exit(None)


@pytest.mark.asyncio
async def test_a_masked_enum_pre_selects_nothing_so_enter_cannot_overwrite_it(tmp_path) -> None:
    """A masked enum can never be matched against its own tokens.

    The overview hands the dialog the placeholder, so the lookup that
    finds the current option cannot succeed for a masked field -- and the
    list's own highlight would then make enter overwrite the secret with
    the first token. No masked enum ships today, so this holds the shape
    rather than a live field: the masking of individual fields is being
    reclassified, and this is the combination that would arrive armed.

    With nothing highlighted the list reports no selection at all, so
    enter leaves the dialog standing rather than closing it on a value.
    That is the safer of the two outcomes and the one asserted here.
    """
    from ..profile.overview import FieldEditScreen

    masked_enum = ProfileFieldView(
        path="auth.contraste_method",
        label="Contraste method",
        value=MASKED_PLACEHOLDER,
        masked=True,
        required=False,
        choices=tuple(
            ProfileFieldChoice(value=token, label=token) for token in ("casilla", "numero_soporte", "fecha_validez")
        ),
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            dismissed: list[str | None] = []
            app.push_screen(FieldEditScreen(masked_enum), dismissed.append)
            await pilot.pause()
            assert app.screen.query_one("#edit-options", OptionList).highlighted is None
            await pilot.press("enter")
            await pilot.pause()
            assert not dismissed, f"enter must not have chosen anything, but dismissed {dismissed!r}"
            assert isinstance(app.screen, FieldEditScreen), (
                "the dialog must stay open so the operator can choose, rather than closing on nothing"
            )

            # The button reaches the same code by a different route, and
            # the key path passing says nothing about it. With no
            # highlight it dismisses None -- a no-change, never a blank --
            # which is the measured answer to whether this half of the
            # dialog can clear a value: it cannot. It only ever hands back
            # None or one of its own declared tokens, and neither reaches
            # the write door as a clear.
            await pilot.click("#btn-edit-save")
            await pilot.pause()
            assert dismissed == [None], f"save with nothing chosen must be a no-change, but gave {dismissed!r}"

            # The operator is not stranded: one arrow key reaches the first
            # token, which is where focus alone used to leave them.
            chosen: list[str | None] = []
            app.push_screen(FieldEditScreen(masked_enum), chosen.append)
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert app.screen.query_one("#edit-options", OptionList).highlighted == 0
            await pilot.press("enter")
            await pilot.pause()
            assert chosen == ["casilla"], f"a chosen token must still be written, but got {chosen!r}"
            app.exit(None)
