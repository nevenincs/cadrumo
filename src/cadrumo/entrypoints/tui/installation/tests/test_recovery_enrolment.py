"""Recovery enrolment from the installation area: the passphrase goes in, the code comes out and is typed back.

The runtime, the transport, the client and the custody service are the real
ones, over one real encrypted profile. Nothing is installed unless the person
proves they hold the code the screen showed them once.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from .....adapters.local_runtime.installation import runtime_installation
from .....adapters.local_runtime.installation_client import RuntimeInstallationClient
from .....adapters.local_runtime.tests.profile_worker_support import owner_id
from .....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from .....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.runtime.installation_requests import InstallationAct
from .....application.user_profile.custody_ports import (
    load_profile_custody_recovery_material,
    unlock_profile_custody_recovery,
)
from .....application.user_profile.recovery_custody import profile_recovery_status
from .....core.i18n.render import tr
from ....runtime.tests.installation_runtime import InstallationLogin, serving_installation_runtime
from ...components.host import ScreenHostApp
from ...components.status import PinnedStatusBar
from ...secret.registration import RecoveryCodeScreen
from ...tests.frame import screen_text
from ..act_screen import InstallationActScreen
from ..destination import InstallationScreen
from ..texts import yes_no
from .runtime_support import installation_client, until

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_SIZE = (120, 50)


@dataclass(frozen=True)
class _ServedProfile:
    endpoint: WindowsRuntimeEndpoint
    root: Path
    profile_id: UUID

    async def open_client(self) -> RuntimeInstallationClient:
        return await asyncio.to_thread(installation_client, self.endpoint)

    def enrolled(self) -> bool:
        return profile_recovery_status(profile_id=self.profile_id, root=self.root).enrolled


@contextmanager
def _serving_one_profile(tmp_path: Path) -> Iterator[_ServedProfile]:
    """Serve a storage root that holds one real encrypted profile with no recovery enrolled."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    try:
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        with administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject:
            close_active_bucket_session()
            with serving_installation_runtime(
                endpoint, root, InstallationLogin(owner=owner_id()), secret_store=lambda: subject.native
            ):
                yield _ServedProfile(endpoint, root, subject.store.binding.profile_id)
    finally:
        endpoint.close()


def _shown(app: App[None]) -> str:
    parts = [screen_text(app, *_SIZE)]
    for screen in app.screen_stack:
        for widget in screen.query("*"):
            if isinstance(widget, Input):
                parts.append(widget.value)
            elif isinstance(widget, PinnedStatusBar):
                parts.append(widget.message)
            elif isinstance(widget, Static):
                parts.append(str(widget.content))
            elif isinstance(widget, DataTable):
                parts.extend(str(cell) for index in range(widget.row_count) for cell in widget.get_row_at(index))
    return "\n".join(parts)


def _logged(caplog: pytest.LogCaptureFixture) -> str:
    return caplog.text + "".join(repr(record.__dict__) for record in caplog.records)


async def _enrolling(pilot: Pilot[None], area: InstallationScreen, served: _ServedProfile) -> InstallationActScreen:
    """Open the enrolment act, give it the profile and its passphrase, and run it."""
    area.open_act(InstallationAct.RECOVERY_ENROLL)
    await until(
        pilot,
        lambda: (
            isinstance(pilot.app.screen, InstallationActScreen)
            and bool(pilot.app.screen.query("#installation-act-result"))
        ),
    )
    screen = pilot.app.screen
    assert isinstance(screen, InstallationActScreen)
    screen.query_one("#installation-field-profile_id", Input).value = str(served.profile_id)
    screen.query_one("#installation-passphrase", Input).value = PROFILE_INPUT
    screen.query_one("#installation-act-run", Button).press()
    return screen


async def _code_screen(pilot: Pilot[None]) -> RecoveryCodeScreen:
    await until(
        pilot,
        lambda: (
            isinstance(pilot.app.screen, RecoveryCodeScreen)
            and bool(pilot.app.screen.query("#field-recovery-verification"))
        ),
        seconds=40,
    )
    screen = pilot.app.screen
    assert isinstance(screen, RecoveryCodeScreen)
    return screen


async def _settled(pilot: Pilot[None], screen: InstallationActScreen) -> None:
    def done() -> bool:
        worker = screen._act_worker
        return worker is not None and worker.is_finished and not screen._busy

    await until(pilot, done, seconds=40)


def _status(screen: InstallationActScreen) -> PinnedStatusBar:
    return screen.query_one("#installation-act-status", PinnedStatusBar)


@pytest.mark.asyncio
async def test_the_code_is_shown_once_typed_back_and_only_then_installed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    changed: list[bool] = []
    with _serving_one_profile(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            enrolling = await _enrolling(pilot, area, served)
            handover = await _code_screen(pilot)

            code = str(handover.query_one("#code-value", Static).content)
            assert code
            await until(pilot, lambda: code in screen_text(app, *_SIZE))
            # The passphrase is already gone from the form, and nothing is installed while the code waits.
            assert enrolling.query_one("#installation-passphrase", Input).value == ""
            assert PROFILE_INPUT not in _shown(app)
            assert not served.enrolled()

            typed = handover.query_one("#field-recovery-verification", Input)
            typed.value = "not the code that was shown"
            handover.query_one("#btn-confirm-code", Button).press()
            await until(pilot, lambda: typed.value == "")
            assert app.screen is handover and not served.enrolled()

            typed.value = code.lower()
            handover.query_one("#btn-confirm-code", Button).press()
            await _settled(pilot, enrolling)

            assert app.screen is enrolling
            assert _status(enrolling).tone == "success"
            result = str(enrolling.query_one("#installation-act-result", Static).content)
            assert f"enrolled    {yes_no(True)}" in result and f"changed     {yes_no(True)}" in result
            assert served.enrolled()
            # The code the person copied down is the one the installed wrapper opens under.
            unlock_profile_custody_recovery(
                load_profile_custody_recovery_material(served.profile_id, root=served.root), recovery_secret=code
            )
            shown = _shown(app)
            assert code not in shown and PROFILE_INPUT not in shown
            assert enrolling._pending_passphrase is None and enrolling._pending_handovers == set()
    assert changed == [True]
    logged = _logged(caplog)
    assert code not in logged and PROFILE_INPUT not in logged


@pytest.mark.asyncio
async def test_closing_the_code_screen_installs_nothing_and_says_so(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    changed: list[bool] = []
    with _serving_one_profile(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            enrolling = await _enrolling(pilot, area, served)
            handover = await _code_screen(pilot)
            code = str(handover.query_one("#code-value", Static).content)

            handover.query_one("#btn-cancel-code", Button).press()
            await _settled(pilot, enrolling)

            assert app.screen is enrolling
            assert _status(enrolling).tone == "warning"
            assert _status(enrolling).message == tr("tui.installation.status.recovery_declined")
            assert not served.enrolled()
            assert code not in _shown(app)
    assert changed == []
    assert code not in _logged(caplog) and PROFILE_INPUT not in _logged(caplog)


@pytest.mark.asyncio
async def test_a_wrong_passphrase_is_refused_before_any_code_is_shown(tmp_path: Path) -> None:
    with _serving_one_profile(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client)
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            area.open_act(InstallationAct.RECOVERY_ENROLL)
            await until(
                pilot,
                lambda: (
                    isinstance(app.screen, InstallationActScreen) and bool(app.screen.query("#installation-act-result"))
                ),
            )
            enrolling = app.screen
            assert isinstance(enrolling, InstallationActScreen)
            enrolling.query_one("#installation-field-profile_id", Input).value = str(served.profile_id)
            enrolling.query_one("#installation-passphrase", Input).value = "not-the-profile-wording"
            enrolling.query_one("#installation-act-run", Button).press()
            await until(pilot, lambda: enrolling._act_worker is not None)
            await _settled(pilot, enrolling)

            assert app.screen is enrolling and _status(enrolling).tone == "error"
            assert tr("tui.installation.status.refused", code="").split("(")[0] in _status(enrolling).message
            assert not served.enrolled()
            assert "not-the-profile-wording" not in _shown(app)
