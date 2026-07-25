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

import pytest
from textual.widgets import DataTable, Input, Static

from .....application.user_profile import (
    ProfileRepository,
    build_profile_overview,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
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
            await pilot.pause()
            assert ran == ["yes"]
            assert "DID-THE-THING" in str(app.query_one("#manager-action-result", Static).content)
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
            await pilot.pause()
            assert app.is_running, "the screen must survive a refusing action"
            assert "NO-CERTIFICATE-REGISTERED" in str(app.query_one("#manager-action-result", Static).content)
            app.exit(None)


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
