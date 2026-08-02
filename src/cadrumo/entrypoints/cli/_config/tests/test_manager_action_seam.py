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

import warnings

import pytest
from textual.widgets import Static

from .....adapters.inbound.tui import FormScreen, ProfileManagerApp
from .....application.user_profile import (
    ProfileRepository,
    build_profile_overview,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
from .....tests.secure_sql import isolated_profile_storage_root
from .._manager_actions import manager_actions
from .._manager_frontend import persist_active_profile_field

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (160, 60)
_PASSWORD = "manager-action-seam-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Action Seam Subject"

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


def _result_line(app: ProfileManagerApp) -> str:
    return str(app.query_one("#manager-action-result", Static).content)


def _open_form(app: ProfileManagerApp) -> FormScreen | None:
    return next((screen for screen in reversed(app.screen_stack) if isinstance(screen, FormScreen)), None)


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
    from .....adapters.inbound.tui import ManagerAction, ManagerActionOutcome

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
                if _result_line(app) and _LOOP_CRASH not in _result_line(app):
                    break
            reported = _result_line(app)
            app.exit(None)

    assert reported == "read-completed", (
        f"an action owning a loop must run to completion through the seam, but reported {reported!r}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action_key", [action.key for action in manager_actions()])
async def test_pressing_a_real_action_never_reports_a_loop_crash(tmp_path, action_key: str) -> None:
    """Every shipped action must survive the press that reaches it.

    Parametrised over the live action list rather than a hand-written one
    so an action added later is covered without anyone remembering to
    enrol it here.

    The assertion is deliberately about the loop crash alone. What each
    action goes on to do — refuse for want of a certificate, open a page,
    report a summary — is those actions' own tests; this pins only that
    pressing the button reaches them at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        app = _manager()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            async with app.run_test(size=_TERMINAL_SIZE) as pilot:
                await pilot.pause()
                await pilot.click(f"#action-{action_key}")

                # An action that opens a page is not finished until the
                # operator answers it, so leave it the same way they would.
                for _ in range(80):
                    await pilot.pause()
                    if _open_form(app) is not None:
                        await pilot.click("#btn-form-cancel")
                        break
                    if _result_line(app):
                        break
                for _ in range(40):
                    await pilot.pause()
                    if _result_line(app):
                        break

                reported = _result_line(app)
                app.exit(None)

        assert _LOOP_CRASH not in reported, f"the {action_key} action still owns a loop on the UI task: {reported!r}"
        assert reported, f"the {action_key} action reported nothing at all, so the operator saw no result"

        never_awaited = [item for item in caught if "never awaited" in str(item.message)]
        assert not never_awaited, (
            f"the {action_key} action left a coroutine unawaited, which is the loop crash's signature: "
            f"{[str(item.message) for item in never_awaited]}"
        )
