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
from textual.widgets import Input

from ....adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.overview import ProfileOverview, build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ..components.host import ScreenHostApp
from ..components.status import PinnedStatusBar
from ..profile.overview import ProfileFieldPersist, ProfileManagerScreen
from .manager_pilot import wait_until_settled

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


def _ensure_logged_in() -> None:
    """Unlock the registered profile so the capsule will serve its record.

    Registration closes its own session and the custody capsule is the sole
    profile authority, so every read or write door below needs an authenticated
    session. Logging in derives the same DEK the capsule was sealed under.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    login_profile(
        name=_LABEL,
        passphrase_callback=lambda: _CREDENTIAL_INPUT,
        profile_decode_context=_profile_decode_context_for_test,
    )


def _live_overview(label: str = _LABEL):
    # Building the overview validates facts against registry authority; lease it here, on whatever thread runs this.
    with bundled_indexed_authority().operation():
        _ensure_logged_in()
        record = load_test_profile_record(require_active_bucket_id())
        return build_profile_overview(record, label=label, schema=_profile_contexts_for_test()[1].schema)


def _write(
    path: str, value: str, expected_revision: int | None = None, expected_content_digest: str | None = None
) -> ProfileOverview:
    """The production write door, so an edit here travels the real path."""
    # Building the overview validates facts against registry authority; lease it here, on whatever thread runs this.
    with bundled_indexed_authority().operation():
        _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
        _ensure_logged_in()
        record = apply_manager_profile_field_mutation(
            profile_id=require_active_bucket_id(),
            path=path,
            value=value,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
            profile_decode_context=_profile_decode_context_for_test,
        )
        return build_profile_overview(record, label=_LABEL, schema=_profile_contexts_for_test()[1].schema)


def _persist_door(path: str, value: str, expected_revision: int, expected_content_digest: str) -> ProfileOverview:
    """The screen's door, bound to its declared signature so a change fails type-checking, not a run."""
    return _write(path, value, expected_revision, expected_content_digest)


_persist: ProfileFieldPersist = _persist_door


def _stored() -> dict[str, object | None]:
    _ensure_logged_in()
    reloaded = load_test_profile_record(require_active_bucket_id())
    return {fact.path: fact.value for fact in reloaded.facts}


def _notice(app: ProfileManagerScreen) -> str:
    return app.query_one("#manager-status", PinnedStatusBar).message


async def _submit(app, pilot, path: str, value: str) -> None:
    """Drive one real edit: open the dialog, type, press save."""
    from ..profile.overview import FieldEditScreen

    field = app._field_by_key[path]
    app.app.push_screen(FieldEditScreen(field), app._apply_edit_for(field))
    await pilot.pause()
    app.app.screen.query_one("#edit-input", Input).value = value
    await pilot.click("#btn-edit-save")
    await pilot.pause()


@pytest.mark.asyncio
async def test_a_blank_submission_on_a_required_field_does_not_clear_it(tmp_path) -> None:
    """The value on the record must be exactly what it was before the edit."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
            register_profile_with_credentials(
                label=_LABEL,
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=_profile_create_context_for_test,
                profile_decode_context=_profile_decode_context_for_test,
            )
        _write(_REQUIRED_PATH, "12345678Z")
        assert _stored().get(_REQUIRED_PATH) == "12345678Z", "fixture must start with a value to lose"

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _submit(app, pilot, _REQUIRED_PATH, "")
            assert _notice(app), "the operator must be told why nothing happened"
            pilot.app.exit(None)

        assert _stored().get(_REQUIRED_PATH) == "12345678Z"


@pytest.mark.asyncio
async def test_a_whitespace_only_submission_on_a_required_field_does_not_clear_it(tmp_path) -> None:
    """Spaces are blank to every reader, so they must not delete the value either."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
            register_profile_with_credentials(
                label=_LABEL,
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=_profile_create_context_for_test,
                profile_decode_context=_profile_decode_context_for_test,
            )
        _write(_REQUIRED_PATH, "12345678Z")

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
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
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
            register_profile_with_credentials(
                label=_LABEL,
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=_profile_create_context_for_test,
                profile_decode_context=_profile_decode_context_for_test,
            )
        _write(_OPTIONAL_PATH, "Ada Lovelace")
        assert _stored().get(_OPTIONAL_PATH) == "Ada Lovelace"

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
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
    with isolated_profile_storage_root(tmp_path=tmp_path):
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
            register_profile_with_credentials(
                label=_LABEL,
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=_profile_create_context_for_test,
                profile_decode_context=_profile_decode_context_for_test,
            )

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
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
