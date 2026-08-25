"""A masked field that is also required, where the two guards meet.

Two guards govern an empty box, and each was written without the other's
case in view. The required guard refuses a blank because it would delete
something the schema says must be there. The masked guard reads a blank
as "I typed nothing", because a masked box opens empty by design and the
operator was never shown the value they would be destroying.

On a field that is both, the masked guard wins -- it runs first, in the
dialog, and dismisses a no-change the required guard downstream never
sees. That is right where the box is concealing a value and wrong where
it is not, and the dialog itself already knows the difference: it shows
the note explaining the no-change reading only when the box is hiding
something. So the explanation and the behaviour were governed by
different predicates, and the operator met the behaviour without the
explanation in exactly the case where the behaviour was wrong -- an
empty REQUIRED field, opened to be filled in, saved blank, answered with
nothing at all.

No field ships masked and required today; the two secrets are optional
and every required field renders in the clear. These tests therefore
hold the SHAPE, as the masked-enum tests beside them do: the path, the
dialog, the write door and the storage are real, and only the ``required``
flag on the view is what a schema author has not yet declared.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input

from ....application.user_profile.overview import MASKED_PLACEHOLDER, ProfileFieldView, build_profile_overview
from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....core.classification import SensitivityClass
from ....domain.user_profile import load_user_profile_schema
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..components.status import PinnedStatusBar
from ..profile.overview import FieldEditScreen, ProfileManagerApp
from .manager_pilot import wait_until_settled

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-masked-required-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Masked Required Subject"

#: A real masked path, so the write door and storage below are the real ones.
_MASKED_PATH = "auth.numero_soporte"
_MASKED_VALUE = "SUPPORT-0042"

#: Unmasked and optional, for the comparison that measures what the
#: narrowed reading costs an empty field rather than reasoning about it.
_PLAIN_PATH = "identity.name"


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
    record = apply_manager_profile_field_mutation(
        profile_id=require_active_bucket_id(),
        path=path,
        value=value,
    )
    return build_profile_overview(record, label=_LABEL)


def _stored() -> dict[str, object | None]:
    _ensure_logged_in()
    reloaded = load_test_profile_record(require_active_bucket_id())
    return {fact.path: fact.value for fact in reloaded.facts}


def _notice(app: ProfileManagerApp) -> str:
    return app.query_one("#manager-status", PinnedStatusBar).message


def _view(*, required: bool, present: bool) -> ProfileFieldView:
    """One masked field in the state under test.

    ``present`` is expressed the way the projection expresses it -- a
    masked field that holds a value carries the placeholder, never the
    value -- so the view handed to the dialog is shaped exactly like the
    one the real overview would build.
    """
    return ProfileFieldView(
        path=_MASKED_PATH,
        label="Support number",
        value=MASKED_PLACEHOLDER if present else None,
        masked=True,
        required=required,
    )


async def _save(app, pilot, field: ProfileFieldView, typed: str) -> None:
    """Drive one real edit: open the dialog, type, press save, let it settle."""
    app.push_screen(FieldEditScreen(field), app._apply_edit_for(field))
    await pilot.pause()
    assert app.screen.query_one("#edit-input", Input).value == "", (
        "a masked dialog must open empty, or this is not the gesture under test"
    )
    app.screen.query_one("#edit-input", Input).value = typed
    await pilot.click("#btn-edit-save")
    await wait_until_settled(app, pilot)


def test_the_combination_under_test_does_not_ship() -> None:
    """Says out loud that these tests hold a shape rather than a live field.

    A tripwire, not a prohibition. Declaring a field both secret and
    required is well defined and safe -- that is what the tests below
    establish -- so this exists to make the declaration ARRIVE HERE
    rather than to prevent it. Two things need a human when it does: the
    answers below were chosen with no real subject to check them
    against, and they are pinned through a constructed view that a real
    field would let them stop using.

    Without it the question is answered only in a module nobody has
    reason to open, and the next author meets the behaviour through an
    operator instead.
    """
    both = [
        f"{section.key}.{field.key}"
        for section in load_user_profile_schema().sections
        for field in section.fields
        if field.required and field.sensitivity is SensitivityClass.SECRET
    ]
    assert not both, (
        "a field now ships both secret and required, so these tests can be pointed at a real "
        f"one instead of a constructed view -- and the behaviour they pin re-read: {both}"
    )


@pytest.mark.asyncio
async def test_a_required_masked_field_holding_a_value_keeps_it_on_a_blank_save(tmp_path) -> None:
    """The concealed value must survive, exactly as an optional one does.

    Nothing is reported and nothing needs to be, which is asserted here
    rather than left implicit: the dialog's note has already said that
    leaving the box empty keeps the value, so the save did what the
    operator was told it would do and a notice would be noise. That the
    note is really shown in this state is the neighbouring test's
    subject -- it is the whole reason silence is acceptable here, so the
    two are worth reading together.
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
            await _save(app, pilot, _view(required=True, present=True), "")
            assert not _notice(app), f"keeping the value is not a refusal, but reported {_notice(app)!r}"
            app.exit(None)

        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE


@pytest.mark.asyncio
async def test_the_dialog_explains_the_no_change_reading_wherever_it_applies(tmp_path) -> None:
    """The note and the behaviour must be governed by the same condition.

    This is the invariant the defect broke. A dialog that silently keeps
    the value while explaining nothing leaves the operator unable to tell
    whether their save did anything; a dialog that explains the reading
    it does not apply is worse still. Asserted over both states of the
    same field, so neither half can drift alone.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()

            app.push_screen(FieldEditScreen(_view(required=True, present=True)))
            await pilot.pause()
            assert app.screen.query("#edit-masked-note"), (
                "a box concealing a value must say that leaving it empty keeps the value"
            )
            app.screen.dismiss(None)
            await pilot.pause()

            app.push_screen(FieldEditScreen(_view(required=True, present=False)))
            await pilot.pause()
            assert not app.screen.query("#edit-masked-note"), (
                "a box concealing nothing must not claim there is a value to keep"
            )
            app.exit(None)


@pytest.mark.asyncio
async def test_a_required_masked_field_holding_nothing_refuses_a_blank_save(tmp_path) -> None:
    """The case the masked guard swallowed: an empty required field, saved empty.

    Here the box is empty because the field IS empty, not because a value
    is being withheld -- so the reasoning behind the no-change reading
    does not apply, and the operator opening a required field they still
    have to fill in must be told that a blank will not do. Silence would
    leave them with a field still counted as missing and no account of
    why saving it changed nothing.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        assert _MASKED_PATH not in _stored(), "the field must start empty for this to be the case under test"

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _save(app, pilot, _view(required=True, present=False), "")
            assert _notice(app), "the operator must be told why saving an empty required field did nothing"
            app.exit(None)

        assert _MASKED_PATH not in _stored()


@pytest.mark.asyncio
async def test_whitespace_in_an_empty_required_masked_field_refuses_too(tmp_path) -> None:
    """Spaces read as blank everywhere else, so they must draw the same refusal."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _save(app, pilot, _view(required=True, present=False), "   ")
            assert _notice(app), "a whitespace-only submission must be refused like any other blank"
            app.exit(None)

        assert _MASKED_PATH not in _stored()


@pytest.mark.asyncio
async def test_a_typed_value_still_reaches_the_record(tmp_path) -> None:
    """The refusal must be scoped to blanks, not to this field.

    Without this the guard above could be satisfied by refusing every
    save on a required masked field, which would make the field
    unfillable -- a worse failure than the one being fixed.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _save(app, pilot, _view(required=True, present=False), _MASKED_VALUE)
            app.exit(None)

        assert _stored().get(_MASKED_PATH) == _MASKED_VALUE


@pytest.mark.asyncio
async def test_an_empty_optional_masked_field_behaves_like_any_other_empty_field(tmp_path) -> None:
    """Narrowing the reading must leave an optional blank uncomplained-about.

    An optional masked field holding nothing, saved blank, asks to clear
    what is already clear. The refusal belongs to required fields alone,
    so this must draw none.

    It does reach the write door now, where before it was dismissed as a
    no-change -- so the second half measures what that costs rather than
    reasoning about it, by driving an UNMASKED optional field through the
    identical gesture and comparing. The two land in the same state, which
    is the point: a masked field holding nothing is not a special case,
    and the outcome is the one every empty optional field already had.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _save(app, pilot, _view(required=False, present=False), "")
            assert not _notice(app), f"an optional blank must draw no complaint, but reported {_notice(app)!r}"

            plain = app._field_by_key[_PLAIN_PATH]
            assert not plain.masked and not plain.required and not plain.present, (
                f"{_PLAIN_PATH} must be an unmasked, optional, empty field for this comparison to mean anything"
            )
            app.push_screen(FieldEditScreen(plain), app._apply_edit_for(plain))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = ""
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        stored = _stored()
        assert stored.get(_MASKED_PATH) is None, "the field must still hold no value"
        assert (_MASKED_PATH in stored) == (_PLAIN_PATH in stored), (
            "a blank save on an empty masked field must leave the record exactly as an unmasked one does, "
            f"but masked gave {_MASKED_PATH in stored} and unmasked gave {_PLAIN_PATH in stored}"
        )


@pytest.mark.asyncio
async def test_a_required_masked_field_is_never_offered_a_clear_button(tmp_path) -> None:
    """A required field has no deletion to offer, whether or not it is masked.

    The button exists because a masked box cannot express a clear by
    being emptied. On a required field there is no clear to express: the
    write door refuses one, so offering the button would promise an
    outcome the dialog then has to take back.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )
        _persist(_MASKED_PATH, _MASKED_VALUE)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            app.push_screen(FieldEditScreen(_view(required=True, present=True)))
            await pilot.pause()
            assert not app.screen.query("#btn-edit-clear"), (
                "a required field's deletion is refused downstream, so no button may offer it"
            )
            app.screen.dismiss(None)
            await pilot.pause()

            # The same field made optional still offers it, so the
            # assertion above is about `required` rather than about a
            # button that never appears.
            app.push_screen(FieldEditScreen(_view(required=False, present=True)))
            await pilot.pause()
            assert app.screen.query("#btn-edit-clear"), (
                "an optional masked field holding a value must still be deletable"
            )
            app.exit(None)
