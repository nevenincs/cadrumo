"""Changing the page's language from the page itself.

The language the manager is written in is an ordinary profile field, so it
was editable in principle: find its row among all the others and change a
two-letter token. That is the wrong place for it. An operator whose page
is in a language they do not read is exactly the one who cannot go looking
for a row, and ``hu`` is not a word they can recognise when they get there.

These tests pin the two halves of the fix: the setting is named in the
footer, so it is reachable without reading the table, and taking it
re-words the page down to the chrome.

Expectations are resolved from the catalogues beside each assertion, in an
explicitly named language, rather than captured once at import. A helper
that resolved them under the active language would compare the page after
the switch against strings that had moved with it, which is the one
comparison that cannot fail.
"""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, OptionList
from textual.widgets._footer import FooterKey

from .....application.user_profile import (
    build_profile_overview,
    login_profile,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
from .....core.i18n import tr
from .....entrypoints.cli import persist_active_profile_field
from .....entrypoints.tui.profile.overview import _LANGUAGE_KEY, _OUTPUT_LANGUAGE_PATH, ProfileManagerApp
from .....tests.manager_pilot import wait_until_settled
from .....tests.profile_capsule import load_test_profile_record
from .....tests.secure_sql import isolated_profile_storage_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-language-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Language Subject"
_STARTING_LANGUAGE = "en"
_TARGET_LANGUAGE = "es"

_LANGUAGE_LABEL_KEY = "profile.schema.field.preferences.output_language.label"
"""The catalogue leaf naming the language setting for the operator.

The footer names the key with the same words its row does, so this is the
one key both surfaces resolve.
"""

_FOOTER_DRAIN_LIMIT = 20
"""How many barriers the footer gets to settle within before the test gives up.

A cap, not a wait: exhausting it fails and names what the footer last
showed, because a footer that cannot reach a settled state is a finding
about the page rather than a slow machine.
"""

_MINIMUM_FOOTER_DRAINS = 2
"""Barriers that must pass before an unchanged footer counts as settled.

A barrier covers the widgets that exist when it is posted, so the first
one can be queued ahead of a rebuild the render had only just scheduled,
and the reads either side of it would agree while that rebuild was still
pending. A second barrier is necessarily queued behind the rebuild, and a
widget processes its messages in order, so it cannot overtake it. The
bound comes from the queue's ordering, not from a frame count chosen by
eye.
"""

_COLUMN_KEYS = (
    "flows.manager.column.state",
    "flows.manager.column.field",
    "flows.manager.column.value",
)
"""The table's column headings: chrome the incremental repaint never touches."""


def _register_in(language: str) -> None:
    """Create the profile already carrying a language, as registration does."""
    from .....domain.user_profile import UserProfileFact

    register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label=_LABEL,
        passphrase=_PASSWORD,
        facts=(UserProfileFact(path=_OUTPUT_LANGUAGE_PATH, value=language),),
    )


def _ensure_logged_in() -> None:
    """Unlock the registered profile so the capsule will serve its record.

    Registration closes its own session and the custody capsule is the sole
    profile authority, so a read here meets a locked capsule without one.
    """
    login_profile(name=_LABEL, passphrase_callback=lambda: _PASSWORD)


def _manager() -> ProfileManagerApp:
    _ensure_logged_in()
    record = load_test_profile_record(require_active_bucket_id())
    return ProfileManagerApp(
        build_profile_overview(record, label=_LABEL),
        persist=lambda path, value: persist_active_profile_field(path, value, label=_LABEL),
    )


def _footer_entries(app: ProfileManagerApp) -> dict[str, str]:
    """Every key the footer names, with the words it names it by.

    Read off the rendered footer rather than the binding table, because a
    binding can be declared shown and still be dropped from the footer —
    which is how the key came to be invisible in the first place.
    """
    return {entry.key: entry.description for entry in app.query(FooterKey)}


def _column_headings(app: ProfileManagerApp) -> list[str]:
    """Every table's column headings, in the words currently on screen."""
    return [str(column.label) for table in app.query(DataTable) for column in table.columns.values()]


async def _drained_footer(app: ProfileManagerApp, pilot) -> dict[str, str]:
    """Drain the page's pending messages until the footer settles, then report it.

    ``pilot.pause()`` is a barrier, not a sleep: it posts a callback to the
    application and to every widget in the screen tree *as that tree stands
    when it runs*, and returns once all of them have answered. That walk is
    what bounds it — a widget mounted after the callbacks went out is not
    among them, so nothing waits for it — and the footer answers a bindings
    change by rebuilding its children. The entries read here are therefore
    mounted *by* the work the barrier is waiting on, which is why passing
    one barrier is no evidence that they exist yet.

    Hence a fixed point rather than a count of frames or a wait for an
    expected wording. Draining until two consecutive reads agree waits on
    the page reaching quiescence, which is a property of its message queue
    rather than of the machine's speed, and it never waits for a particular
    string — so the wait cannot decide the answer. Whatever the footer
    settled on is what comes back, a footer that never named the key
    included.

    Kept here rather than folded into the shared
    :func:`~cadrumo.tests.manager_pilot.wait_until_settled`, which waits on the page
    holding no unfinished background work. That is a different question
    with a different answer: the footer carries no such flag, and a
    recompose is not work anything is waiting on, so there is nothing to
    watch but the reading itself. A wait for quiescence of a *value* and a
    wait for a *state* only look alike from far enough away.
    """
    previous: dict[str, str] | None = None
    for drained in range(1, _FOOTER_DRAIN_LIMIT + 1):
        await pilot.pause()
        current = _footer_entries(app)
        # An empty footer has not composed at all, which is not a settled
        # state for a page that mounts one.
        if current and current == previous and drained >= _MINIMUM_FOOTER_DRAINS:
            return current
        previous = current
    message = (
        f"the footer never settled: still changing after {_FOOTER_DRAIN_LIMIT} "
        f"drained message queues, last showing {previous}"
    )
    raise AssertionError(message)


@pytest.mark.asyncio
async def test_the_language_is_named_in_the_footer_not_hidden_in_the_table(tmp_path) -> None:
    """The one setting an unreadable page must not hide behind itself.

    Named in the footer rather than left as a row like any other, because
    finding a row means reading the table this setting exists to fix. The
    footer has to carry the words, not just the key: an operator cannot
    guess what an unlabelled function key would do.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_in(_STARTING_LANGUAGE)
        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()

            settled = await _drained_footer(app, pilot)
            assert settled.get(_LANGUAGE_KEY) == tr(_LANGUAGE_LABEL_KEY, locale=_STARTING_LANGUAGE), (
                f"the footer must name the language chooser in the page's own language, but showed {settled}"
            )

            await pilot.press(_LANGUAGE_KEY)
            await pilot.pause()

            options = app.screen.query_one("#edit-options", OptionList)
            rendered = [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]
            tokens = _language_tokens(app)
            assert len(tokens) > 1, "a profile offering one language cannot prove a chooser"
            assert not set(rendered) & set(tokens), (
                f"the chooser must name languages, not stored tokens, but showed {rendered}"
            )
            assert rendered == [
                tr(f"wizard.setup.profile.output-language.choices.{token}.label", locale=_STARTING_LANGUAGE)
                for token in tokens
            ], f"each row must name its own language, in the page's language, but showed {rendered}"
            app.exit(None)


@pytest.mark.asyncio
async def test_choosing_a_language_rewords_the_page_through_the_ordinary_door(tmp_path) -> None:
    """The switch reaches the whole page, and writes like any other field.

    The chrome assertions are what make this more than a cell repaint: the
    column headings and the footer's own label are not table content, so a
    page that only refreshed the rows would keep them in the language the
    operator has just left.

    The record assertion is the other half: the language must travel the
    same write door every other edit uses, so a second path that only
    restyled the screen would fail here even while the page looked right.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_in(_STARTING_LANGUAGE)
        app = _manager()
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()

            started_in = tr(_COLUMN_KEYS[0], locale=_STARTING_LANGUAGE)
            assert started_in != tr(_COLUMN_KEYS[0], locale=_TARGET_LANGUAGE), (
                "the two languages must word this heading differently, or the test cannot see a change"
            )
            assert started_in in _column_headings(app), (
                f"the page must start in {_STARTING_LANGUAGE}, but showed {_column_headings(app)}"
            )

            await pilot.press(_LANGUAGE_KEY)
            await pilot.pause()
            options = app.screen.query_one("#edit-options", OptionList)
            options.highlighted = _language_tokens(app).index(_TARGET_LANGUAGE)
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)

            headings = _column_headings(app)
            expected = [tr(key, locale=_TARGET_LANGUAGE) for key in _COLUMN_KEYS]
            assert set(headings) == set(expected), (
                f"the column headings must be rewritten in {_TARGET_LANGUAGE}, but read {sorted(set(headings))}"
            )
            settled = await _drained_footer(app, pilot)
            assert settled.get(_LANGUAGE_KEY) == tr(_LANGUAGE_LABEL_KEY, locale=_TARGET_LANGUAGE), (
                f"the footer must be rewritten too, but showed {settled}"
            )
            app.exit(None)

        _ensure_logged_in()

        record = load_test_profile_record(require_active_bucket_id())
        stored = {fact.path: fact.value for fact in record.facts}
        assert stored.get(_OUTPUT_LANGUAGE_PATH) == _TARGET_LANGUAGE, (
            "the choice must reach the encrypted record through the ordinary write door"
        )


def _language_tokens(app: ProfileManagerApp) -> tuple[str, ...]:
    """The stored tokens behind the chooser's rows, in the order shown."""
    for section in app.overview.sections:
        for field in section.fields:
            if field.path == _OUTPUT_LANGUAGE_PATH:
                return tuple(choice.value for choice in field.choices)
    return ()
