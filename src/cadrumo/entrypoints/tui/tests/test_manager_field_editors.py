"""The editor a field gets must match what the schema says the field holds.

The manager chose its editor from one signal — does this field declare an
enum — so every other declared type landed in the same free-text box. A
boolean was the worst case, because the box gave the operator no way to
learn what a boolean is spelled like here: ``on`` was refused with the write
door's own words ("profile facts failed schema validation", naming neither
the field nor anything acceptable), while ``yes`` was ACCEPTED and stored as
the literal word, leaving the record carrying a token no other writer in the
system produces.

These tests pin both halves of the fix. A field with a closed answer set is
picked from rather than typed into, so the unanswerable value is not
reachable and the stored token is canonical. A field that IS typed into says
what shape it accepts and refuses a bad value at the box, while the operator
is still looking at it.
"""

from __future__ import annotations

import pytest
from textual.widgets import Label, OptionList, Static

from ....application.user_profile import (
    apply_manager_profile_field_mutation,
    build_profile_overview,
    login_profile,
    register_profile_with_credentials,
)
from ....core.bucket_pointer import require_active_bucket_id
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..profile.overview import FieldEditScreen, ProfileManagerApp
from .manager_pilot import wait_until_settled

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-field-editor-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Field Editor Subject"

_BOOLEAN_PATH = "capabilities.llm_vision"
"""A field the schema declares ``boolean``. Optional and unmasked, so the
editor is the only thing under test."""

_DATE_PATH = "auth.fecha_validez"
"""A field the schema declares ``date``. Typed into, and its accepted layout
is exactly what a box cannot state for itself."""

_TEXT_PATH = "identity.name"
"""A plain ``string`` field, so "everything became a choice" cannot pass."""

_VALID_DATE = "1978-03-15"


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


def _manager() -> ProfileManagerApp:
    """The manager wired exactly as the entry point wires it.

    The judge is injected in production, so a test that left it out would be
    exercising a screen the operator never meets.
    """
    return ProfileManagerApp(_live_overview(), persist=_persist)


def _open(app: ProfileManagerApp, path: str) -> None:
    field = app._field_by_key[path]
    app.push_screen(
        FieldEditScreen(field, validate=app._validator_for(field)),
        app._apply_edit_for(field),
    )


@pytest.mark.asyncio
async def test_a_boolean_field_is_picked_from_two_options_not_typed_into(tmp_path) -> None:
    """The operator must never have to guess how yes is spelled."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            declared = app._field_by_key[_BOOLEAN_PATH]
            assert [choice.value for choice in declared.choices] == ["true", "false"], (
                "a boolean must offer exactly the two canonical tokens"
            )
            _open(app, _BOOLEAN_PATH)
            await pilot.pause()
            assert app.screen.query("#edit-options"), "a boolean must be offered as a list"
            assert not app.screen.query("#edit-input"), "a boolean must not be typed into"
            app.exit(None)


@pytest.mark.asyncio
async def test_picking_yes_stores_the_canonical_boolean(tmp_path) -> None:
    """A picked answer must reach the record as a boolean, not as a word.

    This is the half that makes the choice editor worth having rather than
    merely nicer: the old text box accepted ``yes`` and stored the string,
    so the record carried a token no other writer produces and every reader
    had to recognise a spelling only this surface could create.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _BOOLEAN_PATH)
            await pilot.pause()
            app.screen.query_one("#edit-options", OptionList).highlighted = 0
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_BOOLEAN_PATH) is True, "picking the affirmative option must store a real boolean"


@pytest.mark.asyncio
async def test_picking_no_stores_the_canonical_false(tmp_path) -> None:
    """The negative option must be reachable and store ``False``.

    Without this, an editor that ignored the highlight and always wrote the
    first option would pass the affirmative test above.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _BOOLEAN_PATH)
            await pilot.pause()
            app.screen.query_one("#edit-options", OptionList).highlighted = 1
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        assert _stored().get(_BOOLEAN_PATH) is False


@pytest.mark.asyncio
async def test_an_enum_field_keeps_its_choice_editor(tmp_path) -> None:
    """The editor that already worked must not have been traded for the new one."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, PROFILE_OUTPUT_LANGUAGE_PATH)
            await pilot.pause()
            assert app.screen.query("#edit-options")
            assert not app.screen.query("#edit-input")
            app.exit(None)


@pytest.mark.asyncio
async def test_a_plain_text_field_is_still_typed_into(tmp_path) -> None:
    """The scope of the choice editor must be the fields that declare a set.

    Without this the change could have turned every field into a list and
    the boolean tests would still pass.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _TEXT_PATH)
            await pilot.pause()
            assert app.screen.query("#edit-input"), "a free-text field must keep its box"
            assert not app.screen.query("#edit-options")
            assert not app.screen.query("#edit-hint"), "a name box explains itself; a hint there is noise"
            app.exit(None)


@pytest.mark.asyncio
async def test_edit_dialog_uses_the_operator_label_without_exposing_the_schema_path(tmp_path) -> None:
    """A storage address is not usable guidance and must never enter the dialog."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_TEXT_PATH]
            assert field.label != field.path, "the fixture needs distinct operator and storage names"
            _open(app, _TEXT_PATH)
            await pilot.pause()

            assert str(app.screen.query_one("#edit-label", Label).render()) == field.label
            assert not app.screen.query("#edit-path")
            assert field.path not in app.export_screenshot()
            app.exit(None)


@pytest.mark.asyncio
async def test_a_date_box_says_which_layout_it_wants(tmp_path) -> None:
    """A typed box whose shape is not evident must state it before it is used."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _DATE_PATH)
            await pilot.pause()
            hint = str(app.screen.query_one("#edit-hint", Static).content)
            assert hint.strip(), "a date box must say what layout it accepts"
            assert _VALID_DATE in hint, "the hint must show the layout by example, not only describe it"
            app.exit(None)
