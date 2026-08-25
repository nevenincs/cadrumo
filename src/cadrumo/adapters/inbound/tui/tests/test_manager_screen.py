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
import threading

import pytest
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from .....application.user_profile import (
    build_profile_overview,
    login_profile,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id, resolve_active_bucket_id
from .....core.i18n import tr
from .....entrypoints.cli import persist_active_profile_field
from .....entrypoints.tui.components.status import PinnedStatusBar
from .....entrypoints.tui.profile.overview import ProfileManagerApp
from .....tests.manager_pilot import wait_until_settled
from .....tests.profile_capsule import load_test_profile_record
from .....tests.secure_sql import isolated_profile_storage_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-screen-operator-secret"  # noqa: S105 - synthetic test fixture
_EDITED_PATH = "identity.name"


def _live_overview(label: str = "Manager Subject"):
    # Registration closes its own session, so a freshly registered profile is
    # LOCKED and the capsule -- the sole profile authority -- will not yield its
    # record. Logging in with the passphrase derives the SAME DEK the capsule was
    # sealed under; synthesising a session instead gives a different key and the
    # capsule refuses it as a row addressed to another object key.
    login_profile(name=label, passphrase_callback=lambda: _PASSWORD)
    record = load_test_profile_record(require_active_bucket_id())
    return build_profile_overview(record, label=label)


def _persist(path: str, value: str):
    """The production write door, so an edit here travels the real path."""
    return persist_active_profile_field(path, value, label="Manager Subject")


def _notice(app: ProfileManagerApp) -> str:
    """Whatever the page's one diagnostic channel currently holds.

    Read only after :func:`wait_until_settled`, never polled for an expected wording.
    A poll for the text it hopes to see cannot fail on the text that is
    really there, and the press writes a progress line synchronously — so
    such a poll is satisfied before the work it is waiting on has run.
    """
    return app.query_one("#manager-status", PinnedStatusBar).message


def _select_row(app: ProfileManagerApp, path: str) -> None:
    """Select the row for ``path``, as the operator pressing enter on it does.

    Addressed by path rather than by ordinal because the row under any
    given index moves whenever the schema gains a field, and a case about
    one particular row must not silently start testing another.
    """
    for table in app.query(DataTable):
        for index, row_key in enumerate(table.rows):
            if str(row_key.value) == path:
                app.on_data_table_row_selected(DataTable.RowSelected(table, index, row_key))
                return
    message = f"no rendered row for {path!r}"
    raise AssertionError(message)


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
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
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
async def test_profile_context_names_missing_requirements_but_has_no_healthy_placeholder(tmp_path) -> None:
    """Only an actionable schema gap earns durable space in the profile body."""
    from textual.css.query import NoMatches

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        overview = _live_overview()

        app = ProfileManagerApp(overview, persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            requirements = str(app.query_one("#manager-requirements", Static).content)
            assert requirements == tr(
                "cli.diagnostics.summary.profile_missing_fields",
                count=len(overview.missing_required),
                fields=", ".join(field.label for field in overview.missing_required_fields),
            )
            assert str(overview.present_count) + " of " + str(overview.total_count) not in requirements

            app.overview = overview.model_copy(update={"missing_required": (), "missing_required_fields": ()})
            await app._render_profile_context()
            await pilot.pause()
            with pytest.raises(NoMatches):
                app.query_one("#manager-requirements")
            app.exit(None)


@pytest.mark.asyncio
async def test_profile_body_renders_the_envelopes_typed_advisories(tmp_path) -> None:
    """The manager consumes Notice in scrollable context, not permanent chrome."""
    from .....core.json_contract import Notice, NoticeSeverity

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        overview = _live_overview().model_copy(
            update={
                "notices": (
                    Notice(
                        severity=NoticeSeverity.WARNING,
                        code="test.manager.profile_advisory",
                        message="SCHEMA-ENVELOPE-ADVISORY",
                    ),
                ),
            },
        )

        app = ProfileManagerApp(overview, persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            rendered = str(app.query_one("#manager-notice-band #notice-0", Static).content)
            assert "SCHEMA-ENVELOPE-ADVISORY" in rendered
            await app._render_profile_context()
            await pilot.pause()
            assert len(app.query("#manager-notice-band")) == 1, (
                "repainting profile context must replace the notice band before mounting its successor"
            )
            assert app.query_one("#manager-context", Widget).region.y >= app.query_one("#manager-body", Widget).region.y
            assert not app.query_one("#manager-status", PinnedStatusBar).display
            app.exit(None)


@pytest.mark.asyncio
async def test_editing_a_row_writes_through_to_the_encrypted_record(tmp_path) -> None:
    """Save persists: the value survives a reload from storage.

    Asserted against a fresh read of the profile rather than the screen's
    own state, so an implementation that only repainted would fail here.

    The wait after the save is the load-bearing part. Saving only *starts*
    the write -- it runs on a worker thread -- so reading storage after a
    bare pause races it, and the race is decided by how busy the machine
    is. This case read one beat early and was the last in the file still
    doing so; under load it reported a persisted value of ``None`` and read
    as a write-through defect rather than as an under-waited test.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            app.exit(None)

        reloaded = load_test_profile_record(require_active_bucket_id())
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
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            before = _rows(app)
            assert before[_EDITED_PATH][2] == "", "the fixture must start blank, or the glyph cannot flip"
            tables = list(app.query(DataTable))
            required_context = str(app.query_one("#manager-requirements", Static).content)
            untouched = {path: cells for path, cells in before.items() if path != _EDITED_PATH}

            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            # The write runs on a worker thread now, so the assertions wait
            # for storage to answer rather than for a repaint that has not
            # been asked for yet.
            await wait_until_settled(app, pilot)

            after = _rows(app)
            assert after[_EDITED_PATH][2] == "Ada Lovelace", "the edited row must show the stored value"
            assert after[_EDITED_PATH][0] == "●", "the edited row must now read as filled in"
            assert {path: cells for path, cells in after.items() if path != _EDITED_PATH} == untouched, (
                "an incremental repaint must leave every other row exactly as it was"
            )
            assert [id(table) for table in app.query(DataTable)] == [id(table) for table in tables], (
                "the tables must survive the edit; remounting them is the full rebuild this replaced"
            )
            assert str(app.query_one("#manager-requirements", Static).content) == required_context, (
                "editing an optional field must not change the schema-required information"
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
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
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
            assert _notice(app), "the operator must be told why the row did not open"

            release.set()
            await wait_until_settled(app, pilot)
            app.exit(None)

        reloaded = load_test_profile_record(require_active_bucket_id())
        assert {fact.path: fact.value for fact in reloaded.facts}.get(_EDITED_PATH) == "Ada Lovelace", (
            "the gated door must be the real one, or this test proves nothing about production"
        )


def _edit_screen(field):
    from .....entrypoints.tui.profile.editor import FieldEditScreen

    return FieldEditScreen(field)


@pytest.mark.asyncio
async def test_a_masked_field_opens_empty_rather_than_prefilled(tmp_path) -> None:
    """The dialog must not pre-fill the mask placeholder.

    Pre-filling would submit the dots back as the literal new value the
    moment the operator pressed save, silently overwriting the secret with
    a row of bullets.
    """
    from .....application.user_profile import MASKED_PLACEHOLDER, ProfileFieldView
    from .....entrypoints.tui.profile.editor import FieldEditScreen

    masked = ProfileFieldView(
        path="access.token",
        label="Token",
        value=MASKED_PLACEHOLDER,
        masked=True,
        required=False,
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Masked Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(_live_overview("Masked Subject"), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            app.push_screen(FieldEditScreen(masked))
            await pilot.pause()
            assert app.screen.query_one("#edit-input", Input).value == ""
            app.exit(None)


# ── actions ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aeat_progress_replaces_the_inherited_stderr_sink_with_the_pinned_header(tmp_path) -> None:
    """Cl@ve verification progress must be visible before the pull finishes."""
    from .....adapters.outbound.aeat import emit_operator_progress, operator_progress_sink
    from .....core import OperatorProgress
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    release = threading.Event()

    def _run() -> ManagerActionOutcome:
        emit_operator_progress(
            OperatorProgress(
                message="Cl@ve Movil: verify that code TUI-CODE matches in both places.",
                timeout_seconds=120,
            ),
        )
        release.wait(timeout=5)
        return ManagerActionOutcome(message="SYNC-COMPLETE")

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[
                ManagerAction(
                    key="sync",
                    label="Sync",
                    run=_run,
                    progress_sink=operator_progress_sink,
                ),
            ],
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            status = app.query_one("#manager-status", PinnedStatusBar)
            assert not status.display, "an idle operation channel must consume no persistent header space"

            await pilot.click("#action-sync")
            for _ in range(40):
                await pilot.pause()
                if "TUI-CODE" in status.message:
                    break

            assert "TUI-CODE" in status.message, "the actionable AEAT verification code never reached the TUI"
            assert "Time remaining" in status.message, "the typed countdown was not rendered"
            assert status.tone == "progress"
            assert status.display

            release.set()
            await wait_until_settled(app, pilot)
            assert status.message == "SYNC-COMPLETE"
            assert status.tone == "success"
            app.exit(None)


@pytest.mark.asyncio
async def test_a_returned_refusal_is_not_styled_as_a_success(tmp_path) -> None:
    """Handled command errors carry an explicit disposition into the header."""
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionDisposition, ManagerActionOutcome

    def _run() -> ManagerActionOutcome:
        return ManagerActionOutcome(
            message="AUTHENTICATION-REQUIRED",
            disposition=ManagerActionDisposition.REFUSED,
        )

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="refused", label="Refused", run=_run)],
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-refused")
            await wait_until_settled(app, pilot)
            status = app.query_one("#manager-status", PinnedStatusBar)
            assert status.message == "AUTHENTICATION-REQUIRED"
            assert status.tone == "error"
            app.exit(None)


@pytest.mark.asyncio
async def test_censal_apply_refuses_without_reading_or_writing(tmp_path) -> None:
    """The shipped manager action forecloses before any profile or AEAT access."""
    del tmp_path
    from .....entrypoints.cli._config._manager_actions import censal_pull_action
    from .. import ManagerActionDisposition

    outcome = censal_pull_action().run()
    assert outcome.disposition is ManagerActionDisposition.REFUSED
    assert outcome.message == tr("flows.manager.action.censal_pull_review_unavailable")
    assert outcome.overview is None


@pytest.mark.asyncio
async def test_an_action_runs_and_reports_what_it_did(tmp_path) -> None:
    """The bar renders one button per action and shows its message."""
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        ran: list[str] = []

        def _run() -> ManagerActionOutcome:
            ran.append("yes")
            return ManagerActionOutcome(message="DID-THE-THING")

        action = ManagerAction(key="probe", label="Probe", run=_run)
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[action])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-probe")
            await wait_until_settled(app, pilot)
            reported = _notice(app)
            assert ran == ["yes"]
            assert "DID-THE-THING" in reported
            app.exit(None)


@pytest.mark.asyncio
async def test_an_action_that_changed_the_record_redraws_the_page(tmp_path) -> None:
    """A returned overview replaces the page; withholding one leaves it alone.

    An export writes a file and changes nothing, so it must not redraw —
    a redraw from stale data is how a page starts lying about storage.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
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
            await wait_until_settled(refreshing, pilot)
            assert _rows(refreshing)[_EDITED_PATH][2] == "After"
            refreshing.exit(None)


@pytest.mark.asyncio
async def test_a_refusing_action_reports_it_instead_of_taking_the_screen_down(tmp_path) -> None:
    """A door that raises must leave the operator on their page.

    The censal pull reaches the network and the certificate action reads
    key material; both can refuse for ordinary reasons. Losing the whole
    screen mid-edit over one of them would be the worse failure.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    def _refuse() -> ManagerActionOutcome:
        raise RuntimeError("NO-CERTIFICATE-REGISTERED")

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="boom", label="Boom", run=_refuse)],
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-boom")
            await wait_until_settled(app, pilot)
            reported = _notice(app)
            assert app.is_running, "the screen must survive a refusing action"
            assert reported == tr("flows.manager.action.failed")
            assert "NO-CERTIFICATE-REGISTERED" not in reported
            app.exit(None)


@pytest.mark.asyncio
async def test_a_registered_worker_error_is_localised_before_it_reaches_the_header(tmp_path) -> None:
    """The TUI must not expose a translation key as its error message."""
    from .....core.errors import NoActiveProfileError
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    def _refuse() -> ManagerActionOutcome:
        raise NoActiveProfileError(translated_message="flows.manager.action.censal_pull_no_provider")

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        expected = tr("flows.manager.action.censal_pull_no_provider")
        app = ProfileManagerApp(
            _live_overview(),
            persist=_persist,
            actions=[ManagerAction(key="registered-error", label="Registered error", run=_refuse)],
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-registered-error")
            await wait_until_settled(app, pilot)
            status = app.query_one("#manager-status", PinnedStatusBar)
            assert status.message == expected
            assert status.message != "flows.manager.action.censal_pull_no_provider"
            assert status.tone == "error"
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
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    def _wordless() -> ManagerActionOutcome:
        raise raise_wordlessly

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
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
            await wait_until_settled(app, pilot)
            reported = _notice(app)
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
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(_live_overview(), persist=_persist_wordlessly)
        expected = tr("flows.manager.edit.write_failed")

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            reported = _notice(app)
            app.exit(None)

        assert reported == expected, (
            f"a write failing with no text of its own showed {reported!r} rather than naming itself"
        )


@pytest.mark.asyncio
async def test_a_page_with_no_actions_renders_no_action_bar(tmp_path) -> None:
    """Empty is a valid action set, and shows nothing rather than an empty box."""
    from textual.css.query import NoMatches

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            with pytest.raises(NoMatches):
                app.query_one("#manager-actions")
            app.exit(None)


@pytest.mark.asyncio
async def test_a_row_an_action_owns_opens_that_action_not_the_edit_box(tmp_path) -> None:
    """The second write door this closes.

    Every schema section renders as editable rows, so a field belonging to
    a compound operation was reachable through the generic single-fact
    door as well as through the action that owns it. That door writes one
    fact and does nothing else, which for the authentication rows meant
    recording a provider the workflow state was never activated for, and
    letting the Cl@ve identity drift from the fiscal one until a login
    refused over it.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        owned = "auth.provider"
        ran: list[str] = []

        def _run() -> ManagerActionOutcome:
            ran.append(owned)
            return ManagerActionOutcome(message="ACTION-OPENED")

        action = ManagerAction(key="owner", label="Owner", run=_run, owns_paths=(owned,))
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[action])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            assert owned in _rows(app), "the owned row must still be visible; routing is not hiding"
            settled = len(app.screen_stack)

            _select_row(app, owned)
            await wait_until_settled(app, pilot)

            assert ran == [owned], "selecting an owned row must run its owning action"
            assert len(app.screen_stack) == settled, "no single-field edit box may open for an owned row"
            app.exit(None)


@pytest.mark.asyncio
async def test_an_unowned_row_still_opens_the_edit_box(tmp_path) -> None:
    """The control: routing must not swallow every row.

    Were the owner lookup matching anything at all, the case above would
    pass while the manager had stopped being editable, and nothing else
    here would say so.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        ran: list[str] = []

        def _run() -> ManagerActionOutcome:
            ran.append("owner")
            return ManagerActionOutcome(message="ACTION-OPENED")

        action = ManagerAction(key="owner", label="Owner", run=_run, owns_paths=("auth.provider",))
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[action])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            settled = len(app.screen_stack)

            _select_row(app, _EDITED_PATH)
            await pilot.pause()

            assert ran == [], "an unowned row must not run any action"
            assert len(app.screen_stack) > settled, "an unowned row must still open its edit box"
            app.exit(None)


@pytest.mark.asyncio
async def test_an_action_owning_nothing_leaves_every_row_editable(tmp_path) -> None:
    """The default must stay "the table edits its own rows".

    ``owns_paths`` defaults to empty, so an action that declares no
    ownership — which is every action but one — cannot capture a row.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )

        action = ManagerAction(key="plain", label="Plain", run=lambda: ManagerActionOutcome(message="x"))
        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[action])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            settled = len(app.screen_stack)

            _select_row(app, "auth.provider")
            await pilot.pause()

            assert len(app.screen_stack) > settled, "no ownership declared means the row edits as usual"
            app.exit(None)


@pytest.mark.asyncio
async def test_the_action_row_never_paints_past_a_floor_terminal(tmp_path) -> None:
    """Several real-length action labels must stay reachable at 80 columns.

    The action row used to be a plain ``Horizontal``, which never wraps
    and never scrolls: a fifth or sixth action with a real AEAT-length
    label (``Rellenar con los datos censales de la AEAT``) painted past
    column 80 and was permanently unreachable regardless of terminal
    width -- even the widest fixture in this suite's sibling visual gates
    (200 columns) did not clear it. Stacking the actions vertically keeps
    every one of them, however many or however long, inside the surface's
    one sanctioned overflow mechanism: the page's own vertical scroll.
    """
    from .....entrypoints.tui.profile.tasks import ManagerAction, ManagerActionOutcome

    long_labels = [
        "Certificado digital",
        "Cambiar la contraseña",
        "Rellenar con los datos censales de la AEAT",
        "Traer historial de declaraciones de la AEAT",
        "Añadir una fila",
        "Exportar copia cifrada",
    ]
    actions = [
        ManagerAction(key=f"a{i}", label=label, run=lambda: ManagerActionOutcome(message="x"))
        for i, label in enumerate(long_labels)
    ]

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )

        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=actions)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            offenders = [
                f"{type(widget).__name__}{widget.region}"
                for widget in app.screen.walk_children(Widget)
                if widget.display and widget.region.right > 80
            ]
            assert not offenders, f"painted past the side edge of an 80-column terminal: {offenders}"
            app.exit(None)


@pytest.mark.asyncio
async def test_a_long_field_label_never_pushes_the_value_off_screen(tmp_path) -> None:
    """A real AEAT-length field name must not carry the value column past column 80.

    ``DataTable`` sums its columns' natural content width with no clamp
    against the container: on the IRPF section, whose declared labels run
    long (``irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur``
    alone is over fifty characters), the field-name column pushed the
    value column past the right edge, with the table's own horizontal
    scroll left at its default leftmost position and no visible
    affordance hinting a value sits further right. The geometry band used
    by the sibling action-row gate is blind to this: nothing here is
    painted PAST the edge, the value column is simply never scrolled into
    view.

    This reads the real compositor rather than widget geometry, because
    "the value is on screen" is a claim about painted cells, not about a
    coordinate: a wide DataTable can hold a cell inside its virtual
    content while that cell sits outside the visible viewport.
    """
    _long_label_field_path = "irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur"

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        _persist(_long_label_field_path, "12345.67")

        app = ProfileManagerApp(_live_overview(), persist=_persist)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # The IRPF section sits well below the fold on an 80x24
            # terminal; scroll the page (and, transitively, the section's
            # own table) to the edited row so what is checked is "does the
            # value column fit once the operator can see the row", not
            # "is the row above or below the fold" -- a separate, already
            # -covered question the vertical ContentScroll host answers.
            table = app._table_by_section["irpf"]
            table.scroll_visible(animate=False)
            await pilot.pause()
            rendered = app.export_screenshot()
            assert "12345.67" in rendered, (
                "the long IRPF field-name label pushed the value column out of the 80-column viewport"
            )
            app.exit(None)


@pytest.mark.asyncio
async def test_logout_closes_both_the_session_and_the_surface(tmp_path) -> None:
    """Logout must actually end the session AND close the manager -- verify both.

    Neither half alone is the fix. A logout that closed the session but
    left the screen up would keep rendering a now-locked profile's fields
    as though they were still live -- worse than no affordance, because
    the operator would be looking at data the application no longer
    considers current. A logout that closed the screen without actually
    calling the real teardown would look identical from the pilot's side
    while leaving the session artefacts on disk. So this asserts the
    session is gone (the real ``logout_active_profile`` door, not a
    stand-in) AND that the app is no longer running, not either alone.
    """
    from .....entrypoints.cli import logout_action

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Manager Subject",
            passphrase=_PASSWORD,
        )
        assert resolve_active_bucket_id() is not None, "the fixture must start logged in, or this proves nothing"

        app = ProfileManagerApp(_live_overview(), persist=_persist, actions=[logout_action()])
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-logout")
            for _ in range(200):
                if not app.is_running:
                    break
                await pilot.pause()

            # Checked INSIDE the pilot context deliberately: ``run_test``'s
            # own ``__aexit__`` force-stops the app when the block ends
            # regardless of what the code under test did, so asserting
            # ``is_running`` after the block would pass even if nothing
            # here ever called ``exit()`` -- it would just be observing the
            # harness's own teardown.
            assert not app.is_running, "the surface must actually close, not merely blank itself"
            assert resolve_active_bucket_id() is None, "the real session teardown must have run"
