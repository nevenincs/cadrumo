"""Changing the language of the first screen from the first screen.

The registration screen is the first surface of the application, and it
carries the language chooser. That makes it the one page where picking a
language and not seeing the page answer is unrecoverable: there is no
profile yet to hold a preference, and nowhere else to go and set one. So
the choice has to reach the page itself, not only the profile it will
create.

Expectations are resolved from the catalogues beside each assertion, in
an explicitly named language, rather than under whatever language the
page happens to be showing. A helper that resolved them under the active
language would compare the page after the switch against strings that had
moved with it, which is the one comparison that cannot fail. Each test
first pins that the two languages genuinely word the string differently,
so a catalogue that translated nothing could not pass either.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, Label, Select, Static
from textual.widgets._select import SelectOverlay

from .....application.user_profile import login_profile
from .....core import assess_profile_password, require_active_bucket_id
from .....core.i18n import output_language, tr
from .....entrypoints.cli._config._manager_frontend import attempt_registration
from .....tests.profile_capsule import load_test_profile_record
from .....tests.secure_sql import isolated_profile_storage_root
from .. import RegistrationApp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)
_PASSWORD = "registration-language-operator-secret"  # noqa: S105 - synthetic test fixture
_STARTING_LANGUAGE = "en"
_TARGET_LANGUAGE = "hu"

_OUTPUT_LANGUAGE_PATH = "preferences.output_language"
"""Where the created profile keeps the language chosen on this screen."""


def _screen() -> RegistrationApp:
    """The production composition, wired to the doors the CLI gives it."""
    return RegistrationApp(assess=assess_profile_password, register=attempt_registration)


def _text(app: RegistrationApp, selector: str) -> str:
    """What one zone of the page currently says."""
    return str(app.query_one(selector, Static).content)


def _page_copy(app: RegistrationApp) -> list[str]:
    """The page's words, in the order the operator reads them."""
    return [
        app.title,
        _text(app, "#registration-banner"),
        _text(app, "#registration-intro"),
        _text(app, "#registration-why"),
        str(app.query_one("#label-username", Label).content),
        _text(app, "#hint-username"),
        str(app.query_one("#label-password", Label).content),
        str(app.query_one("#label-confirm", Label).content),
        str(app.query_one("#label-output-language", Label).content),
    ]


def _expected_copy(locale: str) -> list[str]:
    """The same page, resolved from the catalogue under a named language."""
    return [
        tr("flows.registration.title", locale=locale),
        tr("flows.registration.title", locale=locale),
        tr("flows.registration.intro", locale=locale),
        tr("flows.registration.why_password", locale=locale),
        tr("flows.registration.username_label", locale=locale),
        tr("flows.registration.username_hint", locale=locale),
        tr("flows.registration.password_label", locale=locale),
        tr("flows.registration.confirm_label", locale=locale),
        tr("wizard.setup.profile.output-language.prompt", locale=locale),
    ]


def _chooser_rows(app: RegistrationApp) -> list[str]:
    """The language chooser's own rows, as displayed.

    Read off the overlay the chooser opens rather than its internals,
    because the rows the operator can pick from are the rows that matter.
    """
    overlay = app.query_one(SelectOverlay)
    return [str(overlay.get_option_at_index(index).prompt) for index in range(overlay.option_count)]


async def _choose(pilot, language: str) -> None:
    """Take the language chooser, as an operator does."""
    pilot.app.query_one("#field-output-language", Select).value = language
    await pilot.pause()
    await pilot.pause()


@pytest.mark.asyncio
async def test_choosing_a_language_rewords_the_first_screen(tmp_path) -> None:
    """The page answers in the language just picked, down to the chrome.

    The chooser's own rows are part of the claim: they are translated too,
    so a page that re-worded its labels and left the chooser behind would
    still be showing the operator the language names in a language they
    may have just navigated away from.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()

            started = _expected_copy(_STARTING_LANGUAGE)
            target = _expected_copy(_TARGET_LANGUAGE)
            assert all(left != right for left, right in zip(started, target, strict=True)), (
                "the two languages must word every zone differently, or this test cannot see a change"
            )

            await _choose(pilot, _STARTING_LANGUAGE)
            assert _page_copy(app) == started, "the page must open in the language the chooser is showing"

            await _choose(pilot, _TARGET_LANGUAGE)
            assert _page_copy(app) == target, "taking the chooser must re-word the whole page"

            expected_rows = [
                tr(f"wizard.setup.profile.output-language.choices.{language}.label", locale=_TARGET_LANGUAGE)
                for language in ("es", "en", "ca", "hu")
            ]
            assert set(_chooser_rows(app)) == set(expected_rows), (
                f"the chooser's own rows must be re-worded too, but read {_chooser_rows(app)}"
            )
            assert str(app.query_one("#btn-create", Button).label) == tr(
                "flows.registration.create_button", locale=_TARGET_LANGUAGE
            ), "the button that creates the profile must be re-worded too"

            await pilot.press("escape")

        assert app.outcome is None


@pytest.mark.asyncio
async def test_the_language_switch_keeps_what_has_already_been_typed(tmp_path) -> None:
    """Re-wording the page must not empty the fields under it.

    An operator who fills the form and then notices the language chooser
    would otherwise be punished for using it. The strength line is here
    too: it is derived from the password rather than stored, so a page
    that kept the field and dropped its advisory would still have lost
    half of what was on screen.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _choose(pilot, _STARTING_LANGUAGE)

            app.query_one("#field-username", Input).value = "Half Filled"
            app.query_one("#field-password", Input).value = _PASSWORD
            app.query_one("#field-confirm", Input).value = _PASSWORD
            await pilot.pause()
            assert app.query_one("#strength-line", Static).has_class("strength-strong")

            await _choose(pilot, _TARGET_LANGUAGE)

            assert app.query_one("#field-username", Input).value == "Half Filled"
            assert app.query_one("#field-password", Input).value == _PASSWORD
            assert app.query_one("#field-confirm", Input).value == _PASSWORD
            assert app.query_one("#strength-line", Static).has_class("strength-strong"), (
                "the advisory must survive the re-word, in the new language"
            )
            assert _text(app, "#strength-line") == tr("flows.registration.strength.strong", locale=_TARGET_LANGUAGE), (
                "and it must be re-worded, not merely kept"
            )

            await pilot.press("escape")

        assert app.outcome is None


@pytest.mark.asyncio
async def test_the_chosen_language_is_the_one_the_profile_is_created_with(tmp_path) -> None:
    """Re-wording the page must not cost the screen its actual job.

    The chooser has two consequences — the page in front of the operator
    and the preference the new profile carries — and this pins the second
    one against a change that only addressed the first.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _choose(pilot, _TARGET_LANGUAGE)

            app.query_one("#field-username", Input).value = "Language Subject"
            app.query_one("#field-password", Input).value = _PASSWORD
            app.query_one("#field-confirm", Input).value = _PASSWORD
            await pilot.pause()
            await pilot.click("#btn-create")
            await app.workers.wait_for_complete()
            await pilot.pause()

        assert app.error is None
        assert app.outcome is not None, "the screen must still create the profile"

        # The screen registers on a worker thread, so the session it
        # unlocked belongs to that thread's context and not this one.
        # Unlocking again through the ordinary login door is how the test
        # reaches the encrypted record the screen actually wrote.
        login_profile(name="Language Subject", passphrase_callback=lambda: _PASSWORD)
        record = load_test_profile_record(require_active_bucket_id())
        stored = {fact.path: fact.value for fact in record.facts}
        assert stored.get(_OUTPUT_LANGUAGE_PATH) == _TARGET_LANGUAGE, (
            "the profile must be created in the language the chooser was left on"
        )


@pytest.mark.asyncio
async def test_the_chosen_language_does_not_outlive_the_screen(tmp_path) -> None:
    """The override the screen renders under must not colour anything after it.

    This is the hazard the sanctioned-override inventory in
    ``locales/tests/test_dynamic_prefix_registry_coverage.py`` exists to
    bound: an override held outside a command's own settings scope keeps
    rendering once the command unwinds, and the operator gets a closing
    notice in a language they did not ask that command to speak. The
    registration screen is listed there as reviewed rather than
    ctx-scoped, because a Textual app has no command context to scope to.

    What this pins is the outcome, not the means. The screen closes its
    override on the way out, but removing that close does not fail this
    test and is not what makes the screen safe: the override is entered
    on the app's own message-pump task, whose context the caller does not
    share. What does fail this test is moving the site to a mechanism
    that reaches past the task — an environment variable and a
    settings-cache reset — which is the substitution worth catching.

    The mid-screen assertion is the control: without proof that the
    override was live inside the screen, an unchanged caller language
    would be equally consistent with a chooser that never worked at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        before = output_language()
        assert before != _TARGET_LANGUAGE, (
            "the caller must not already be speaking the target language, or this test proves nothing"
        )

        app = _screen()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await _choose(pilot, _TARGET_LANGUAGE)
            assert app.title == tr("flows.registration.title", locale=_TARGET_LANGUAGE), (
                "the override must be live inside the screen, or the assertion below is vacuous"
            )
            await pilot.press("escape")

        assert output_language() == before, (
            "the screen's language override must not survive it and reach the caller's rendering"
        )
