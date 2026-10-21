"""The installation area opens from the sign-in screen and from first registration, with no session at all.

Neither screen has a profile session to offer, and the area asks for none: the
profile opener is never called. Once an act may have changed which profiles
exist, the screen that opened the area closes so its owner reads them again.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Select, Static

from cadrumo.application.user_profile.login_interaction import ProfileLoginChoice
from cadrumo.core.credentials import assess_profile_password
from cadrumo.core.i18n.render import output_language, tr
from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.installation.act_screen import InstallationActScreen
from cadrumo.entrypoints.tui.installation.area_factory import InstallationAreaFactory
from cadrumo.entrypoints.tui.installation.destination import InstallationScreen
from cadrumo.entrypoints.tui.installation.door import InstallationClientOpener
from cadrumo.entrypoints.tui.secret.registration import RegistrationAttempt, RegistrationScreen
from cadrumo.tests.async_condition import until
from cadrumo_client.contracts.installation_requests import InstallationAct
from cadrumo_client.transport.frontend_client import FrontendClient

from ........frontend.tui.secret.runtime_login import RuntimeLoginScreen
from .runtime_support import ServedRuntime, serving_test_acts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
]

_SIZE = (140, 60)


class _Owner[ResultT](App[None]):
    """Hold one sign-in or registration screen and record how it was dismissed."""

    def __init__(self, screen: Screen[ResultT]) -> None:
        super().__init__()
        self._hosted = screen
        self.dismissals: list[ResultT | None] = []

    async def on_mount(self) -> None:
        await self.push_screen(self._hosted, self.dismissals.append)


class _ProfileOpener:
    """The opener a session would use; opening the installation area must never call it."""

    def __init__(self) -> None:
        self.opened: list[UUID] = []

    async def __call__(self, profile_id: UUID) -> FrontendClient:
        self.opened.append(profile_id)
        raise AssertionError("the installation area needs no profile connection")


def _area_factory(open_client: InstallationClientOpener) -> InstallationAreaFactory:
    def build(report_change: Callable[[], None], /, *, locale: str | None = None) -> Screen[None]:
        return InstallationScreen(open_client=open_client, on_records_changed=report_change, locale=locale)

    return build


def _login(open_profile: _ProfileOpener, served: ServedRuntime) -> RuntimeLoginScreen:
    return RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(uuid4()), label="Synthetic profile"),),
        open_client=open_profile,
        accept_handoff=lambda _handoff: False,
        installation_factory=_area_factory(served.open_client),
    )


def _never_registers(label: str, candidate: str, language: str) -> RegistrationAttempt:
    raise AssertionError("opening the installation area must not create a profile")


async def _area(pilot: Pilot[None], entry: str) -> InstallationScreen:
    """Press the entry on the screen in front and return the composed installation area."""
    await until(pilot, lambda: bool(pilot.app.screen.query(entry)))
    pilot.app.screen.query_one(entry, Button).press()
    await until(
        pilot,
        lambda: isinstance(pilot.app.screen, InstallationScreen) and bool(pilot.app.screen.query("#installation-hint")),
    )
    area = pilot.app.screen
    assert isinstance(area, InstallationScreen)
    listed = area.query_one("#installation-acts", DataTable)
    await until(pilot, lambda: len(listed.columns) == 3 and listed.row_count == len(area.offered_acts))
    return area


async def _act(pilot: Pilot[None], area: InstallationScreen, act: InstallationAct) -> InstallationActScreen:
    area.open_act(act)
    await until(
        pilot,
        lambda: (
            isinstance(pilot.app.screen, InstallationActScreen)
            and bool(pilot.app.screen.query("#installation-act-result"))
        ),
    )
    screen = pilot.app.screen
    assert isinstance(screen, InstallationActScreen)
    return screen


async def _settled(pilot: Pilot[None], screen: InstallationActScreen) -> None:
    def done() -> bool:
        worker = screen._act_worker
        return worker is not None and worker.is_finished and not screen._busy

    await until(pilot, done)


async def _clear_the_active_profile_setting(pilot: Pilot[None], area: InstallationScreen) -> None:
    """Run one confirmed act that changes records, then return to the area's list."""
    repair = await _act(pilot, area, InstallationAct.REPAIR_PROFILE)
    repair.query_one("#installation-field-clear_active", Checkbox).value = True
    repair.query_one("#installation-act-run", Button).press()
    await until(
        pilot,
        lambda: isinstance(pilot.app.screen, ConfirmScreen) and bool(pilot.app.screen.query("#btn-confirm-accept")),
    )
    pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
    await _settled(pilot, repair)
    repair.action_close()
    await until(pilot, lambda: pilot.app.screen is area)


@pytest.mark.asyncio
async def test_the_sign_in_screen_opens_the_area_with_no_session_and_stays_when_nothing_changed(
    tmp_path: Path,
) -> None:
    open_profile = _ProfileOpener()
    with serving_test_acts(tmp_path) as served:
        login = _login(open_profile, served)
        owner = _Owner(login)
        async with owner.run_test(size=_SIZE) as pilot:
            area = await _area(pilot, "#runtime-login-installation")
            assert area.query_one(".cadrumo-banner", Static).content == tr("tui.installation.title")

            check = await _act(pilot, area, InstallationAct.STORAGE_CHECK)
            await _settled(pilot, check)
            assert served.root.name in str(check.query_one("#installation-act-result", Static).content)

            check.action_close()
            await until(pilot, lambda: owner.screen is area)
            area.action_close()
            await until(pilot, lambda: owner.screen is login)
            await pilot.pause()

            # A read changed nothing, so the profile list on screen is still the installation's.
            assert login.is_mounted and owner.dismissals == []
    assert open_profile.opened == []


@pytest.mark.asyncio
async def test_the_sign_in_screen_closes_for_a_fresh_profile_list_after_an_act_changed_records(
    tmp_path: Path,
) -> None:
    open_profile = _ProfileOpener()
    with serving_test_acts(tmp_path) as served:
        login = _login(open_profile, served)
        owner = _Owner(login)
        async with owner.run_test(size=_SIZE) as pilot:
            area = await _area(pilot, "#runtime-login-installation")
            await _clear_the_active_profile_setting(pilot, area)
            assert owner.dismissals == []

            area.action_close()
            await until(pilot, lambda: owner.dismissals == [None])
        assert served.acts.repairs[-1] == (None, True, True)
    assert open_profile.opened == []


@pytest.mark.asyncio
async def test_first_registration_opens_the_same_area_and_closes_once_the_profile_set_may_have_changed(
    tmp_path: Path,
) -> None:
    with serving_test_acts(tmp_path) as served:
        registration = RegistrationScreen(
            assess=assess_profile_password,
            register=_never_registers,
            installation_factory=_area_factory(served.open_client),
        )
        owner = _Owner(registration)
        async with owner.run_test(size=_SIZE) as pilot:
            area = await _area(pilot, "#btn-installation")
            area.action_close()
            await until(pilot, lambda: owner.screen is registration)
            await pilot.pause()
            assert registration.is_mounted and owner.dismissals == []

            area = await _area(pilot, "#btn-installation")
            await _clear_the_active_profile_setting(pilot, area)
            area.action_close()
            await until(pilot, lambda: owner.dismissals == [None])


@pytest.mark.asyncio
async def test_the_area_opened_from_registration_is_worded_in_the_language_chosen_on_that_page(
    tmp_path: Path,
) -> None:
    chosen = next(language for language in ("hu", "ca") if language != output_language())
    for key in ("tui.installation.title", "tui.installation.column.act", "tui.installation.status.completed"):
        assert tr(key, locale=chosen) != tr(key)
    with serving_test_acts(tmp_path) as served:
        registration = RegistrationScreen(
            assess=assess_profile_password,
            register=_never_registers,
            installation_factory=_area_factory(served.open_client),
        )
        owner = _Owner(registration)
        async with owner.run_test(size=_SIZE) as pilot:
            await until(pilot, lambda: bool(registration.query("#btn-installation")))
            entry = registration.query_one("#btn-installation", Button)
            registration.query_one("#field-output-language", Select).value = chosen
            await until(pilot, lambda: str(entry.label) == tr("tui.installation.title", locale=chosen))

            area = await _area(pilot, "#btn-installation")
            assert area.query_one(".cadrumo-banner", Static).content == tr("tui.installation.title", locale=chosen)
            assert area.query_one("#installation-intro", Static).content == tr("tui.installation.intro", locale=chosen)
            listed = area.query_one("#installation-acts", DataTable)
            labels = [str(column.label) for column in listed.columns.values()]
            assert labels == [
                tr("tui.installation.column.family", locale=chosen),
                tr("tui.installation.column.act", locale=chosen),
                tr("tui.installation.column.effect", locale=chosen),
            ], f"chosen={chosen}, area_locale={area._locale}, labels={labels!r}"

            check = await _act(pilot, area, InstallationAct.STORAGE_CHECK)
            await _settled(pilot, check)
            assert str(check.query_one("#installation-act-close", Button).label) == tr(
                "tui.installation.action.close", locale=chosen
            )
            assert check.query_one("#installation-act-status", PinnedStatusBar).message == tr(
                "tui.installation.status.completed", locale=chosen
            )

            # The page's choice is its own: the language around it is the one it was.
            assert tr("tui.installation.title") != tr("tui.installation.title", locale=chosen)


@pytest.mark.asyncio
async def test_screens_given_no_area_offer_no_entry() -> None:
    login = RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(uuid4()), label="Synthetic profile"),),
        open_client=_ProfileOpener(),
        accept_handoff=lambda _handoff: False,
    )
    owner = _Owner(login)
    async with owner.run_test(size=_SIZE) as pilot:
        await until(pilot, lambda: bool(login.query("#runtime-login-submit")))
        assert not login.query("#runtime-login-installation")
