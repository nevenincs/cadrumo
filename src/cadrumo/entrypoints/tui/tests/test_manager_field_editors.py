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
from textual.widgets import Input, Label, OptionList, Static

from ....application.user_profile import (
    build_profile_overview,
    login_profile,
    register_profile_with_credentials,
)
from ....application.user_profile.manager_projection import (
    persist_active_profile_manager_field,
    profile_manager_field_value_refusal,
)
from ....core import require_active_bucket_id
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

_ENUM_PATH = "preferences.output_language"
"""A field the schema declares ``enum``, kept beside the boolean so the
choice editor is not proved only by the case that just gained it."""

_EMAIL_PATH = "identity.email"
"""A field the schema declares ``email``. Typed into, and the one content
format the schema names that nothing used to check."""

_TEXT_PATH = "identity.name"
"""A plain ``string`` field, so "everything became a choice" cannot pass."""

_MALFORMED_DATE = "15/03/1978"
"""A date in the layout an operator most plausibly reaches for, and one the
schema does not take."""

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
    return persist_active_profile_manager_field(path, value, label=_LABEL)


def _stored() -> dict[str, object | None]:
    _ensure_logged_in()
    reloaded = load_test_profile_record(require_active_bucket_id())
    return {fact.path: fact.value for fact in reloaded.facts}


def _manager() -> ProfileManagerApp:
    """The manager wired exactly as the entry point wires it.

    The judge is injected in production, so a test that left it out would be
    exercising a screen the operator never meets.
    """
    return ProfileManagerApp(
        _live_overview(),
        persist=_persist,
        validate=profile_manager_field_value_refusal,
    )


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
            _open(app, _ENUM_PATH)
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


@pytest.mark.asyncio
async def test_a_refused_value_holds_the_dialog_open_and_says_why(tmp_path) -> None:
    """The operator must be answered at the box, while they can still fix it.

    Three things are asserted together because any one alone would let the
    defect back: the dialog must stay open, the reason must name the value
    the operator actually typed, and nothing may reach the record.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _DATE_PATH)
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = _MALFORMED_DATE
            await pilot.click("#btn-edit-save")
            await pilot.pause()

            assert app.screen.query("#edit-input"), "the dialog must stay open on a refused value"
            refusal = str(app.screen.query_one("#edit-refusal", Static).content)
            assert _MALFORMED_DATE in refusal, "the refusal must quote back what was typed"
            assert _VALID_DATE in refusal, "the refusal must show an acceptable value, not only reject one"
            app.exit(None)

        assert _DATE_PATH not in _stored(), "a value refused at the box must never reach the record"


@pytest.mark.asyncio
async def test_an_acceptable_value_is_not_refused(tmp_path) -> None:
    """The control for the guard above: it must refuse a value, not every value.

    A validator wired to reject unconditionally would satisfy the refusal
    test completely, and the field would simply have become uneditable —
    which is the complaint this whole change answers.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
        )

        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            _open(app, _DATE_PATH)
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = _VALID_DATE
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            assert not app.screen.query("#edit-input"), "an acceptable value must close the dialog"
            app.exit(None)

        assert str(_stored().get(_DATE_PATH)) == _VALID_DATE


def test_the_dialog_judge_agrees_with_the_write_door() -> None:
    """What the box refuses and what storage refuses must be one answer.

    The dialog exists to answer earlier, not to answer differently. A judge
    stricter than the door would refuse values the record would have taken;
    a looser one would close on values the door then rejects, which is the
    behaviour the operator met before this seam existed.
    """
    from ....domain.user_profile import (
        UserProfileFact,
        load_user_profile_schema,
        profile_value_refusal,
        section_field_key,
    )

    schema = load_user_profile_schema()
    cases = (
        (_DATE_PATH, _MALFORMED_DATE),
        (_DATE_PATH, _VALID_DATE),
        (_BOOLEAN_PATH, "on"),
        (_BOOLEAN_PATH, "true"),
        (_ENUM_PATH, "klingon"),
        (_ENUM_PATH, "en"),
        (_TEXT_PATH, "Ada Lovelace"),
        (_EMAIL_PATH, "banana"),
        (_EMAIL_PATH, "op@example.test"),
    )
    for path, value in cases:
        declared = schema.field(section_field_key(path))
        door_refuses = profile_value_refusal(declared, UserProfileFact(path=path, value=value).value) is not None
        dialog_refuses = profile_manager_field_value_refusal(path, value) is not None
        assert dialog_refuses is door_refuses, f"the two judges disagree about {value!r} at {path}"


def test_every_refusal_kind_reaches_the_operator_as_words() -> None:
    """A verdict with no sentence would surface as a blank refusal line.

    Driven through the public seam with one real refusal per kind rather
    than by calling the wording helper directly, so what is proved is that
    the whole path — judge, then words — produces something an operator can
    read, not merely that a copy table has four rows.

    The offending value must come back in the sentence. A refusal that says
    only "invalid" leaves the operator re-reading a box whose contents they
    already believed were right.
    """
    from ....domain.user_profile import ProfileValueRefusalKind

    by_kind = {
        ProfileValueRefusalKind.DATE: (_DATE_PATH, _MALFORMED_DATE),
        ProfileValueRefusalKind.ENUM: (_ENUM_PATH, "klingon"),
        ProfileValueRefusalKind.BOOLEAN: (_BOOLEAN_PATH, "on"),
        ProfileValueRefusalKind.NUMERIC: ("attribution_entity_socios.share_pct", "999"),
        ProfileValueRefusalKind.EMAIL: (_EMAIL_PATH, "banana"),
    }
    assert set(by_kind) == set(ProfileValueRefusalKind), (
        "every refusal kind the rule can return must have a case here, or a kind ships unworded"
    )
    for kind, (path, value) in by_kind.items():
        sentence = profile_manager_field_value_refusal(path, value)
        assert sentence, f"{kind} produced no words for {value!r} at {path}"
        assert value in sentence, f"{kind} must quote back the refused value"
