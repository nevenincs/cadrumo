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

import threading

import pytest
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.overview import build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....core.i18n import tr
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..components.host import ScreenHostApp
from ..components.status import PinnedStatusBar
from ..profile.overview import ProfileManagerScreen
from .manager_pilot import wait_until_settled

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
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
    record = apply_manager_profile_field_mutation(
        profile_id=require_active_bucket_id(),
        path=path,
        value=value,
    )
    return build_profile_overview(record, label="Manager Subject")


def _notice(app: ProfileManagerScreen) -> str:
    """Whatever the page's one diagnostic channel currently holds.

    Read only after :func:`wait_until_settled`, never polled for an expected wording.
    A poll for the text it hopes to see cannot fail on the text that is
    really there, and the press writes a progress line synchronously — so
    such a poll is satisfied before the work it is waiting on has run.
    """
    return app.query_one("#manager-status", PinnedStatusBar).message


def _select_row(app: ProfileManagerScreen, path: str) -> None:
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


def _rows(app: ProfileManagerScreen) -> dict[str, list[str]]:
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

        app = ProfileManagerScreen(overview, persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            rendered = _rows(app)
            assert len(rendered) == overview.total_count
            assert overview.total_count > overview.present_count, (
                "the fixture must have blanks, or this test proves nothing"
            )
            pilot.app.exit(None)


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

        app = ProfileManagerScreen(overview, persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
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
            pilot.app.exit(None)


@pytest.mark.asyncio
async def test_profile_body_renders_the_envelopes_typed_advisories(tmp_path) -> None:
    """The manager consumes Notice in scrollable context, not permanent chrome."""
    from ....core.json_contract import Notice, NoticeSeverity

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

        app = ProfileManagerScreen(overview, persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
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
            pilot.app.exit(None)


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

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            pilot.app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            pilot.app.exit(None)

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

        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            before = _rows(app)
            assert before[_EDITED_PATH][2] == "", "the fixture must start blank, or the glyph cannot flip"
            tables = list(app.query(DataTable))
            required_context = str(app.query_one("#manager-requirements", Static).content)
            untouched = {path: cells for path, cells in before.items() if path != _EDITED_PATH}

            field = app._field_by_key[_EDITED_PATH]
            pilot.app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
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
            pilot.app.exit(None)


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

        app = ProfileManagerScreen(_live_overview(), persist=_gated)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            pilot.app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await pilot.pause()
            assert app._pending_write is not None, "the first write must still be in flight to prove anything"

            settled = len(app.app.screen_stack)
            table = next(candidate for candidate in app.query(DataTable) if candidate.row_count)
            row_key = next(iter(table.rows))
            app.on_data_table_row_selected(DataTable.RowSelected(table, 0, row_key))
            await pilot.pause()

            assert len(app.app.screen_stack) == settled, (
                "no edit box may open while a write is in flight; opening one is how typed input gets discarded"
            )
            assert _notice(app), "the operator must be told why the row did not open"

            release.set()
            await wait_until_settled(app, pilot)
            pilot.app.exit(None)

        reloaded = load_test_profile_record(require_active_bucket_id())
        assert {fact.path: fact.value for fact in reloaded.facts}.get(_EDITED_PATH) == "Ada Lovelace", (
            "the gated door must be the real one, or this test proves nothing about production"
        )


def _edit_screen(field):
    from ..profile.overview import FieldEditScreen

    return FieldEditScreen(field)


@pytest.mark.asyncio
async def test_a_masked_field_opens_empty_rather_than_prefilled(tmp_path) -> None:
    """The dialog must not pre-fill the mask placeholder.

    Pre-filling would submit the dots back as the literal new value the
    moment the operator pressed save, silently overwriting the secret with
    a row of bullets.
    """
    from ....application.user_profile.overview import MASKED_PLACEHOLDER, ProfileFieldView
    from ..profile.overview import FieldEditScreen

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
        app = ProfileManagerScreen(_live_overview("Masked Subject"), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            pilot.app.push_screen(FieldEditScreen(masked))
            await pilot.pause()
            assert app.app.screen.query_one("#edit-input", Input).value == ""
            pilot.app.exit(None)


# ── actions ─────────────────────────────────────────────────────────────


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
        app = ProfileManagerScreen(_live_overview(), persist=_persist_wordlessly)
        expected = tr("flows.manager.edit.write_failed")

        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            field = app._field_by_key[_EDITED_PATH]
            pilot.app.push_screen(_edit_screen(field), app._apply_edit_for(field))
            await pilot.pause()
            app.app.screen.query_one("#edit-input", Input).value = "Ada Lovelace"
            await pilot.click("#btn-edit-save")
            await wait_until_settled(app, pilot)
            reported = _notice(app)
            pilot.app.exit(None)

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
        app = ProfileManagerScreen(_live_overview(), persist=_persist)
        async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            with pytest.raises(NoMatches):
                app.query_one("#manager-actions")
            pilot.app.exit(None)


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
        _live_overview()
        written = _persist(_long_label_field_path, "12345.67")

        app = ProfileManagerScreen(written, persist=_persist)
        async with ScreenHostApp(app).run_test(size=(80, 24)) as pilot:
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
            rendered = pilot.app.export_screenshot()
            assert "12345.67" in rendered, (
                "the long IRPF field-name label pushed the value column out of the 80-column viewport"
            )
            pilot.app.exit(None)
