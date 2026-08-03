"""Pilot-driven proof that a manager action survives being pressed.

Every other test of these actions calls them as functions, or hands them a
presenter of the test's own. That leaves the seam between the button and
the action — the one place an action actually runs in production —
uncovered, and it was broken: each action tried to own an event loop while
Textual's was already running, so pressing any button reported
``asyncio.run() cannot be called from a running event loop`` into a muted
label and did nothing.

These tests press the REAL actions from
:func:`cadrumo.entrypoints.cli._config._manager_actions.manager_actions`
inside a running application, because a stub action cannot reproduce the
defect: what failed was owning a loop, and a stub owns none.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest
from textual.widgets import DataTable, Input, Static

from .....adapters.inbound.tui import (
    FormField,
    FormPage,
    FormScreen,
    ManagerAction,
    ManagerActionOutcome,
    ProfileManagerApp,
)
from .....application.user_profile import (
    ProfileRepository,
    build_profile_overview,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
from .....core.i18n import tr
from .....tests.secure_sql import isolated_profile_storage_root
from .._manager_actions import manager_actions
from .._manager_frontend import persist_active_profile_field, present_form

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-action-seam-operator-secret"  # noqa: S105 - synthetic test fixture
_EXPORT_PASSPHRASE = "manager-action-seam-bundle-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Action Seam Subject"

_EXPECTED_KEY = {
    "censal-pull": "flows.manager.action.censal_pull_no_provider",
    "certificate": "flows.manager.action.abandoned",
    "export": "flows.manager.action.abandoned",
}
"""What each action concludes on a freshly registered profile.

The censal pull refuses before reading because nothing can authenticate
yet; the two form doors are abandoned because the test closes their page.
Stated per action rather than as a shape, so a door that silently stops
reaching its own conclusion fails here.

Held as catalogue KEYS and resolved beside the assertion, inside the
profile context that produced the message: the page resolves its wording
under whatever language the profile carries, so a value read at import —
or after that context is torn down — would be compared against a sentence
produced under different settings."""

_THREAD_SETTLE_SECONDS = 10.0
"""How long a test waits for an action's thread to finish after the app is gone.

Generous because it bounds a failure, not a success: the thread answers
within one liveness poll when the seam is right, and hangs forever when it
is not, so this only decides how long a broken seam takes to say so."""

_A_PAGE = FormPage(
    title="Manager form",
    section="Manager form",
    fields=(FormField(key="value", label="Value"),),
)
"""The smallest page an action can ask for.

Its content is irrelevant to the tests that use it: what they watch is
whether asking for a page at all can leave the asking thread stuck."""

_LOOP_CRASH = "asyncio.run() cannot be called from a running event loop"
"""The exact text the broken seam reported to the operator.

Asserted verbatim rather than by exception type because the screen caught
the failure and rendered it, so this string is what the defect actually
looked like from the outside.
"""


def _manager() -> ProfileManagerApp:
    """The manager as production builds it, on a freshly registered profile."""
    aggregate = ProfileRepository().load(require_active_bucket_id())
    return ProfileManagerApp(
        build_profile_overview(aggregate.record, label=_LABEL),
        persist=lambda path, value: persist_active_profile_field(path, value, label=_LABEL),
        actions=manager_actions(),
    )


def _manager_offering(action: ManagerAction) -> ProfileManagerApp:
    """The production manager, carrying one action written for a test."""
    aggregate = ProfileRepository().load(require_active_bucket_id())
    return ProfileManagerApp(
        build_profile_overview(aggregate.record, label=_LABEL),
        persist=lambda path, value: persist_active_profile_field(path, value, label=_LABEL),
        actions=(action,),
    )


def _notice(app: ProfileManagerApp) -> str:
    return str(app.query_one("#manager-notice", Static).content)


def _open_form(app: ProfileManagerApp) -> FormScreen | None:
    return next((screen for screen in reversed(app.screen_stack) if isinstance(screen, FormScreen)), None)


async def _wait_for_form(pilot, app: ProfileManagerApp) -> FormScreen | None:
    """Wait for an action to put a page on screen, if it is going to."""
    for _ in range(80):
        await pilot.pause()
        form = _open_form(app)
        if form is not None:
            return form
        if app._pending_action is None:
            return None
    return _open_form(app)


async def _wait_for_action(pilot, app: ProfileManagerApp) -> None:
    """Wait until the action has settled, so the line read is its own.

    Reading before this returns the progress line the press wrote
    synchronously, which is how a dead action passed for a working one.
    """
    for _ in range(120):
        await pilot.pause()
        if app._pending_action is None:
            return


@pytest.mark.asyncio
async def test_an_action_that_starts_its_own_loop_is_carried_by_the_seam(tmp_path) -> None:
    """The censal pull's shape, which the live action cannot reach here.

    ``_run_censal_pull`` calls ``asyncio.run`` directly, but only after
    ``_censal_pull_unavailable`` clears — and on a profile with no
    authentication configured it never does, so the test above exercises
    that action's refusal and never its loop. Configuring authentication
    to reach the real call would drive a live browser session, which is
    not something a test may do.

    So the loop-owning shape is pinned here instead. The action is written
    for the test, but the seam it is pressed through is the production one
    and is the only thing being tested: what failed was owning a loop, and
    this owns one exactly as the censal pull does.
    """

    async def _reads_something() -> str:
        return "read-completed"

    def _run() -> ManagerActionOutcome:
        import asyncio

        return ManagerActionOutcome(message=asyncio.run(_reads_something()))

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        aggregate = ProfileRepository().load(require_active_bucket_id())
        app = ProfileManagerApp(
            build_profile_overview(aggregate.record, label=_LABEL),
            persist=lambda path, value: persist_active_profile_field(path, value, label=_LABEL),
            actions=(ManagerAction(key="loop-owner", label="Loop owner", run=_run),),
        )
        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-loop-owner")
            for _ in range(80):
                await pilot.pause()
                if _notice(app) and _LOOP_CRASH not in _notice(app):
                    break
            reported = _notice(app)
            app.exit(None)

    assert reported == "read-completed", (
        f"an action owning a loop must run to completion through the seam, but reported {reported!r}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action_key", [action.key for action in manager_actions()])
async def test_pressing_a_real_action_reports_the_outcome_it_actually_reached(tmp_path, action_key: str) -> None:
    """Every shipped action must run to its own conclusion when pressed.

    The assertion is an EQUALITY against the outcome each action produces
    on this profile, and that strictness is the whole point. An earlier
    version asserted only that one known error string was absent, which a
    different exception satisfied — and the page writes a progress line
    synchronously when the button is pressed, so "something is displayed"
    was satisfied before the action had run at all. Between them those two
    weak checks stayed green while the certificate and export doors were
    dying on a second, unrelated exception and discarding everything the
    operator typed.

    A form is abandoned rather than filled here because what is under test
    is that the press reaches the action and its answer reaches the page.
    That the answer carries the operator's values is proved separately, by
    committing one.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        app = _manager()

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click(f"#action-{action_key}")

            form = await _wait_for_form(pilot, app)
            if form is not None:
                await pilot.click("#btn-form-cancel")
            await _wait_for_action(pilot, app)

            reported = _notice(app)
            app.exit(None)

        assert reported == tr(_EXPECTED_KEY[action_key]), (
            f"the {action_key} action reported {reported!r}, not the outcome it should have reached"
        )


@pytest.mark.asyncio
async def test_a_form_the_operator_commits_reaches_the_action(tmp_path) -> None:
    """What is typed into a manager form must arrive at the action.

    This is the guarantee the seam exists for, and the one that was
    silently broken: the page was pushed, the operator could type into it
    and press save, and the action had already died — so every value was
    discarded with nothing said.

    Proved on export because its success is observable without standing up
    an authentication registry: the destination typed into the form is the
    path a bundle must appear at. Asserting the file exists is what makes
    this un-fakeable — no failure mode of the seam writes it, and unlike a
    message it cannot be satisfied by an exception that merely differs
    from the abandonment text. That weaker form of this assertion passed
    on the broken mechanism, which is why it is not used here.
    """
    destination = tmp_path / "profile-bundle.cadrumo"

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        app = _manager()

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-export")

            form = await _wait_for_form(pilot, app)
            assert form is not None, "the export action must open a form to fill in"

            await _type_into(pilot, app, "destination", str(destination))
            await _type_into(pilot, app, "passphrase", _EXPORT_PASSPHRASE)
            await pilot.click("#btn-form-save")
            await _wait_for_action(pilot, app)

            reported = _notice(app)
            app.exit(None)

        assert destination.exists(), (
            f"the values committed on the form never reached the action: it reported {reported!r} "
            f"and wrote nothing to {destination}"
        )
        assert reported == tr("flows.manager.action.export_done", destination=str(destination)), (
            f"the export reported {reported!r} rather than naming what it wrote"
        )


@pytest.mark.asyncio
async def test_quitting_with_a_page_open_answers_the_action_that_asked_for_it(tmp_path) -> None:
    """Leaving with a form still on screen must release the action's thread.

    Every action that shows a page blocks a worker thread on the answer.
    If quitting simply took the application away, that thread would be
    left holding a question nothing can ever answer — encrypted storage
    still open behind it, and the process unable to end.

    So the abandonment has to reach the action, and it is the action's
    answer that is read here rather than the notice line: by the time the
    application is gone there is no line left to read, which is exactly
    why nothing covered this before.
    """
    answers: list[Mapping[str, str] | None] = []
    settled = threading.Event()

    def _run() -> ManagerActionOutcome:
        answers.append(present_form(_A_PAGE))
        settled.set()
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        app = _manager_offering(ManagerAction(key="asks", label="Asks", run=_run))

        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#action-asks")
            assert await _wait_for_form(pilot, app) is not None, "the action must put its page on screen first"
            app.exit(None)

        assert settled.wait(timeout=_THREAD_SETTLE_SECONDS), (
            "quitting with a page open stranded the action's thread on an answer that can never come"
        )
        assert answers == [None], f"the abandoned page must read as no answer, but the action was handed {answers!r}"


@pytest.mark.asyncio
async def test_a_page_asked_for_after_the_application_stops_reads_as_abandonment(tmp_path) -> None:
    """An action outliving the application must not report Textual's refusal.

    A thread-backed action cannot be cancelled, so it can still be running
    after the application it was started from has gone — and then reach
    the point where it wants to show a page. Textual refuses that outright
    once its loop is down, and left alone that refusal is an untranslated
    internal string, which the settling handler renders verbatim into the
    operator's notice line.

    The window is narrow in production and impossible to hit under the
    pilot harness, which leaves the loop standing after the app stops. So
    the application is run the way production runs it, and the action is
    held until it has fully returned.
    """
    proceed = threading.Event()
    answers: list[Mapping[str, str] | None] = []
    settled = threading.Event()

    def _run() -> ManagerActionOutcome:
        proceed.wait(timeout=_THREAD_SETTLE_SECONDS)
        answers.append(present_form(_A_PAGE))
        settled.set()
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        app = _manager_offering(ManagerAction(key="outlives", label="Outlives", run=_run))

        async def _press_then_leave(pilot) -> None:
            await pilot.pause()
            await pilot.click("#action-outlives")
            await pilot.pause()
            app.exit(None)

        await app.run_async(headless=True, size=_TERMINAL_SIZE, auto_pilot=_press_then_leave)

        assert not app.is_running, "the application must be down before the action asks for its page"
        proceed.set()

        assert settled.wait(timeout=_THREAD_SETTLE_SECONDS), (
            "asking for a page after the application stopped never returned to the action: "
            "the refusal either escaped it or stranded its thread"
        )
        assert answers == [None], (
            f"a page that cannot be shown must read as no answer, but the action was handed {answers!r}"
        )


async def _type_into(pilot, app: ProfileManagerApp, key: str, value: str) -> None:
    """Fill one row of the open form the way an operator would.

    Through the row's own edit dialog rather than by writing the value
    into the page's state, so the path from a keystroke to a committed
    value is the one under test.
    """
    form = _open_form(app)
    assert form is not None, "no form is open to type into"
    table = form.query_one("#form-table", DataTable)
    table.move_cursor(row=[str(row.value) for row in table.rows].index(key))
    table.action_select_cursor()
    await pilot.pause()
    app.screen.query_one("#edit-input", Input).value = value
    await pilot.click("#btn-edit-save")
    await pilot.pause()
