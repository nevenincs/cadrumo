"""Pilot-driven proofs for the profile manager.

The manager replaces a page that listed the wizard's *steps*. These tests
pin the two properties that make it a profile page instead: every declared
field is on screen whether or not it has a value, and selecting a row and
saving writes through to the encrypted record.

The write is proven by reloading the profile from storage rather than by
inspecting the screen, so a manager that updated only its own in-memory
view would fail.
"""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import DataTable, Input, Static

from .....application.user_profile import (
    ProfileRepository,
    build_profile_overview,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
from .....core.i18n import tr
from .....entrypoints.cli._config._manager_frontend import persist_active_profile_field
from .....tests.secure_sql import isolated_profile_storage_root
from .. import ProfileManagerApp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-screen-operator-secret"  # noqa: S105 - synthetic test fixture
_EDITED_PATH = "identity.name"


def _live_overview(label: str = "Manager Subject"):
    """Build the overview from whatever the store currently holds."""
    aggregate = ProfileRepository().load(require_active_bucket_id())
    return build_profile_overview(aggregate.record, label=label)


def _persist(path: str, value: str):
    """The production write door, so an edit here travels the real path."""
    return persist_active_profile_field(path, value, label="Manager Subject")


async def _settled_notice(app: ProfileManagerApp, pilot, expected: str) -> str:
    """Wait for an action's outcome to reach the page, then return it.

    Actions run on a worker thread, so pressing the button starts the work
    rather than finishing it: the outcome lands a repaint or two later.
    Waiting for the expected text rather than a fixed number of pauses
    keeps the test from passing on a page that simply has not caught up.

    Returns whatever the channel holds when the wait ends, so a test that
    never sees its text still asserts against the real content and reports
    what was actually shown.
    """
    for _ in range(80):
        await pilot.pause()
        content = str(app.query_one("#manager-notice", Static).content)
        if expected in content:
            return content
    return str(app.query_one("#manager-notice", Static).content)


def _rows(app: ProfileManagerApp) -> dict[str, list[str]]:
    """Every rendered row across every section table, keyed by field path."""
    collected: dict[str, list[str]] = {}
    for table in app.query(DataTable):
        for row_key in table.rows:
            if row_key.value is not None:
                collected[str(row_key.value)] = [str(cell) for cell in table.get_row(row_key)]
    return collected


@pytest.mark.asyncio
async def test_the_page_shows_every_declared_field_including_the_empty_ones(tmp_path) -> None:
    """A freshly-registered profile still renders its whole schema.

    This is the paradigm difference in one assertion. The profile has
    almost no facts, so a fact-driven page would be nearly blank; the
    manager must show the full field set so the operator can see what is
    there to fill in.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        overview = _live_overview()

        app = ProfileManagerApp(overview, persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            rendered = _rows(app)
            assert len(rendered) == overview.total_count
            assert overview.total_count > overview.present_count, (
                "the fixture must have blanks, or this test proves nothing"
            )
            app.exit(None)


@pytest.mark.asyncio
async def test_editing_a_row_writes_through_to_the_encrypted_record(tmp_path) -> None:
    """Save persists: the value survives a reload from storage.

    Asserted against a fresh read of the profile rather than the screen's
    own state, so an implementation that only repainted would fail here.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await pilot.pause()
            app.exit(None)

        reloaded = ProfileRepository().load(require_active_bucket_id()).record
        stored = {fact.path: fact.value for fact in reloaded.facts}
        assert stored.get(_EDITED_PATH) == "Ada Lovelace"


@pytest.mark.asyncio
async def test_editing_one_field_repaints_that_row_without_rebuilding_the_tables(tmp_path) -> None:
    """One edit repaints one row, and leaves the rest of the page standing.

    The page carries a table per schema section and a row per declared
    field, so redrawing all of them to change a single value made a
    one-field edit cost the whole screen — the operator felt it as a
    freeze. The edit now writes just the cells whose content moved.

    Widget identity is what pins that. A wholesale redraw unmounts every
    table and mounts new ones, so asserting the very same ``DataTable``
    objects are still on screen afterwards fails the moment the
    incremental path is swapped back for a full rebuild — which a check
    on the rendered values alone would not catch, since both paths
    ultimately show the right number.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            before = _rows(app)
            assert before[_EDITED_PATH][2] == "", "the fixture must start blank, or the glyph cannot flip"
            tables = list(app.query(DataTable))
            progress = str(app.query_one("#manager-progress", Static).content)
            untouched = {path: cells for path, cells in before.items() if path != _EDITED_PATH}

            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            # The write runs on a worker thread now, so the assertions wait
            # for storage to answer rather than for a repaint that has not
            # been asked for yet.
            await app.workers.wait_for_complete()
            await pilot.pause()

            after = _rows(app)
            assert after[_EDITED_PATH][2] == "Ada Lovelace", "the edited row must show the stored value"
            assert after[_EDITED_PATH][0] == "●", "the edited row must now read as filled in"
            assert {path: cells for path, cells in after.items() if path != _EDITED_PATH} == untouched, (
                "an incremental repaint must leave every other row exactly as it was"
            )
            assert [id(table) for table in app.query(DataTable)] == [id(table) for table in tables], (
                "the tables must survive the edit; remounting them is the full rebuild this replaced"
            )
            assert str(app.query_one("#manager-progress", Static).content) != progress, (
                "the filled-in count must follow the edit"
            )
            app.exit(None)


@pytest.mark.asyncio
async def test_a_second_edit_is_refused_before_its_dialog_opens(tmp_path) -> None:
    """Serialising writes costs the operator no typed input.

    Two writes in flight together would each merge into the same pre-edit
    record, so the second save would drop the first field — they have to be
    serialised. What matters is WHERE the refusal lands. Refusing after the
    box closed would throw away what the operator had already typed, which
    is a worse failure than the freeze this work removed: a freeze is
    irritating, losing input is destructive.

    The guard therefore sits at row selection, upstream of the box. A
    write can only start from a dialog dismissal, and no dialog can open
    while one is in flight, so the operator is stopped before they type
    rather than after — there is never anything to lose.
    """
    import threading

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        release = threading.Event()

        def _gated(path: str, value: str):
            """The real write door, held open while the second edit is tried."""
            release.wait(timeout=30)
            return _persist(path, value)

        app = ProfileManagerApp(_live_overview(), persist=_gated)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await pilot.pause()
            assert app._pending_write is not None, "the first write must still be in flight to prove anything"

            settled = len(app.screen_stack)
            table = next(candidate for candidate in app.query(DataTable) if candidate.row_count)
            row_key = next(iter(table.rows))
            app.on_data_table_row_selected(DataTable.RowSelected(table, 0, row_key))
            await pilot.pause()

            assert len(app.screen_stack) == settled, (
                "no edit box may open while a write is in flight; opening one is how typed input gets discarded"
            )
            assert str(app.query_one("#manager-notice", Static).content), (
                "the operator must be told why the row did not open"
            )

            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            app.exit(None)

        reloaded = ProfileRepository().load(require_active_bucket_id()).record
        assert {fact.path: fact.value for fact in reloaded.facts}.get(_EDITED_PATH) == "Ada Lovelace", (
            "the gated door must be the real one, or this test proves nothing about production"
        )


def _edit_screen(field):
    from .._manager_screen import FieldEditScreen

    return FieldEditScreen(field)


@pytest.mark.asyncio
async def test_a_masked_field_opens_empty_rather_than_prefilled(tmp_path) -> None:
    """The dialog must not pre-fill the mask placeholder.

    Pre-filling would submit the dots back as the literal new value the
    moment the operator pressed save, silently overwriting the secret with
    a row of bullets.
    """
    from .....application.user_profile import MASKED_PLACEHOLDER, ProfileFieldView
    from .._manager_screen import FieldEditScreen

    masked = ProfileFieldView(
        path="access.token",
        label="Token",
        value=MASKED_PLACEHOLDER,
        masked=True,
        required=False,
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Masked Subject", passphrase=_PASSWORD)
        app = ProfileManagerApp(_live_overview("Masked Subject"), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            app.push_screen(FieldEditScreen(masked))
            await pilot.pause()
            assert app.screen.query_one("#edit-input", Input).value == ""
            app.exit(None)


# ── actions ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_action_runs_and_reports_what_it_did(tmp_path) -> None:
    """The bar renders one button per action and shows its message."""
    from .. import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        ran: list[str] = []

        def _run() -> ManagerActionOutcome:
            ran.append("yes")
            return ManagerActionOutcome(message="DID-THE-THING")

        action = ManagerAction(key="probe", label="Probe", run=_run)
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[action])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-probe")
            reported = await _settled_notice(app, pilot, "DID-THE-THING")
            assert ran == ["yes"]
            assert "DID-THE-THING" in reported
            app.exit(None)


@pytest.mark.asyncio
async def test_an_action_that_changed_the_record_redraws_the_page(tmp_path) -> None:
    """A returned overview replaces the page; withholding one leaves it alone.

    An export writes a file and changes nothing, so it must not redraw —
    a redraw from stale data is how a page starts lying about storage.
    """
    from .. import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        _persist(_EDITED_PATH, "Before")
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert _rows(app)[_EDITED_PATH][2] == "Before"
            app.exit(None)

        # The action writes through the real door, then hands back the page.
        def _rename() -> ManagerActionOutcome:
            return ManagerActionOutcome(message="renamed", overview=_persist(_EDITED_PATH, "After"))

        refreshing = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="rename", label="Rename", run=_rename)],
        )
        async with refreshing.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert _rows(refreshing)[_EDITED_PATH][2] == "Before"
            await pilot.click("#action-rename")
            # An action runs on a worker thread, so the page is repainted from
            # ``on_worker_state_changed`` rather than inline with the click.
            # ``pause`` only drains the event loop and would let this assert
            # race the write, reading the pre-action value.
            await refreshing.workers.wait_for_complete()
            await pilot.pause()
            assert _rows(refreshing)[_EDITED_PATH][2] == "After"
            refreshing.exit(None)


@pytest.mark.asyncio
async def test_a_refusing_action_reports_it_instead_of_taking_the_screen_down(tmp_path) -> None:
    """A door that raises must leave the operator on their page.

    The censal pull reaches the network and the certificate action reads
    key material; both can refuse for ordinary reasons. Losing the whole
    screen mid-edit over one of them would be the worse failure.
    """
    from .. import ManagerAction, ManagerActionOutcome

    def _refuse() -> ManagerActionOutcome:
        raise RuntimeError("NO-CERTIFICATE-REGISTERED")

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="boom", label="Boom", run=_refuse)],
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-boom")
            reported = await _settled_notice(app, pilot, "NO-CERTIFICATE-REGISTERED")
            assert app.is_running, "the screen must survive a refusing action"
            assert "NO-CERTIFICATE-REGISTERED" in reported
            app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raise_wordlessly",
    [RuntimeError, asyncio.CancelledError],
    ids=["a-door-that-raises-bare", "a-worker-that-was-cancelled"],
)
async def test_a_failure_carrying_no_text_is_named_rather_than_shown_blank(
    tmp_path,
    raise_wordlessly: type[BaseException],
) -> None:
    """A failure with nothing to say must not reach the operator as an empty line.

    ``str(exc)`` is the empty string for any exception built without
    arguments, and the settling handler used to render it as itself. That
    put an error-styled line carrying no text in the one place the
    operator looks for what went wrong — worse than silence, because it
    says something happened and then refuses to say what.

    Both shapes are driven because emptiness belongs to no single type.
    ``asyncio.CancelledError`` is the one Textual produces on its own:
    ``Worker._run`` stores the cancellation it caught, and its text is
    empty. A door raising bare reaches the same blank through the
    ordinary failure branch, which is why the fallback keys on the
    rendered text rather than on the exception.

    What is asserted is the rendered notice, not the handling: the whole
    complaint is about what is on the operator's screen.
    """
    from .. import ManagerAction, ManagerActionOutcome

    def _wordless() -> ManagerActionOutcome:
        raise raise_wordlessly

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="silent", label="Silent", run=_wordless)],
        )
        # Resolved here rather than at import: the page words itself under
        # the language this profile carries, so a value read outside this
        # context would be compared against a sentence produced elsewhere.
        expected = tr("flows.manager.action.failed")

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-silent")
            reported = await _settled_notice(app, pilot, expected)
            app.exit(None)

        assert reported == expected, f"a failure with no text of its own showed {reported!r} rather than naming itself"


@pytest.mark.asyncio
async def test_a_write_failing_wordlessly_is_named_rather_than_shown_blank(tmp_path) -> None:
    """The write path settles the same way, and had the same blank.

    ``_settle_write`` rendered ``str(worker.error)`` exactly as the action
    path did, so a storage door raising bare emptied the notice line while
    styling it as a refusal. Proved separately because it is a separate
    handler with its own fallback wording, and fixing one of the two would
    otherwise pass on the other's test.
    """

    def _persist_wordlessly(path: str, value: str):
        raise RuntimeError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        app = ProfileManagerApp(_live_overview(), persist=_persist_wordlessly)
        expected = tr("flows.manager.edit.write_failed")

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            reported = await _settled_notice(app, pilot, expected)
            app.exit(None)

        assert reported == expected, (
            f"a write failing with no text of its own showed {reported!r} rather than naming itself"
        )


@pytest.mark.asyncio
async def test_a_page_with_no_actions_renders_no_action_bar(tmp_path) -> None:
    """Empty is a valid action set, and shows nothing rather than an empty box."""
    from textual.css.query import NoMatches

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Manager Subject", passphrase=_PASSWORD)
        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            with pytest.raises(NoMatches):
                app.query_one("#manager-actions")
            app.exit(None)
