"""The installation area sends each act through the real client to a real runtime and shows how it settled."""

from __future__ import annotations

import asyncio
import logging
import sys
from importlib.metadata import version
from pathlib import Path
from typing import override
from uuid import uuid4

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.i18n.render import tr
from cadrumo.core.storage_taxonomy import StorageArea
from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.installation.act_screen import InstallationActScreen
from cadrumo.entrypoints.tui.installation.destination import InstallationScreen
from cadrumo.entrypoints.tui.installation.door import InstallationClientOpener
from cadrumo.entrypoints.tui.installation.texts import act_label, yes_no
from cadrumo.entrypoints.tui.tests.frame import screen_text
from cadrumo.entrypoints.tui.tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActRequest,
    InstallationCompleted,
    InstallationFailed,
    InstallationRefused,
    installation_act_of,
    installation_request_facts,
)
from cadrumo_client.transport.installation_client import InstallationClient, InstallationSecretHolder
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.host.tests.installation_runtime import FAULT_TEXT, InstallationLogin, serving_installation_runtime

from .installation_act_settling import act_settled
from .runtime_support import RECLAIMABLE_ENTRIES, serving_test_acts, source_digest_of

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
]

_SIZE = (120, 50)
_TYPED = "synthetic-archive-wording-7f3a"
"""What the person types into the masked field; it must appear nowhere but the secret frame."""


def _shown(app: App[None]) -> str:
    """Everything the screens on the stack hold or paint."""
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


async def _open(pilot: Pilot[None], area: InstallationScreen, act: InstallationAct) -> InstallationActScreen:
    area.open_act(act)
    # The screen is on the stack before it has composed; wait for its last control.
    await settle_until(
        pilot,
        lambda: (
            isinstance(pilot.app.screen, InstallationActScreen)
            and bool(pilot.app.screen.query("#installation-act-result"))
        ),
        "( isinstance(pilot.app.screen, InstallationActScreen) and bool(pilo...",
        workers=False,
    )
    screen = pilot.app.screen
    assert isinstance(screen, InstallationActScreen)
    return screen


async def _asked(pilot: Pilot[None]) -> ConfirmScreen:
    """Wait for the one confirmation question and return its composed dialog."""
    await settle_until(
        pilot,
        lambda: isinstance(pilot.app.screen, ConfirmScreen) and bool(pilot.app.screen.query("#btn-confirm-accept")),
        "isinstance(pilot.app.screen, ConfirmScreen) and bool(pilot.app.scre...",
        workers=False,
    )
    dialog = pilot.app.screen
    assert isinstance(dialog, ConfirmScreen)
    return dialog


def _status(screen: InstallationActScreen) -> PinnedStatusBar:
    return screen.query_one("#installation-act-status", PinnedStatusBar)


def _result(screen: InstallationActScreen) -> str:
    return str(screen.query_one("#installation-act-result", Static).content)


def _fact(lines: str, name: str) -> str:
    """The value printed beside one member's name."""
    for line in lines.splitlines():
        label, _, value = line.strip().partition("  ")
        if label == name:
            return value.strip()
    raise AssertionError(f"{name} is not among the printed members")


async def _run(pilot: Pilot[None], screen: InstallationActScreen) -> None:
    """Press Run and wait until that press, and no earlier one, has started an act."""
    before = screen._act_worker
    screen.query_one("#installation-act-run", Button).press()
    await settle_until(
        pilot, lambda: screen._act_worker is not before, "screen._act_worker is not before", workers=False
    )


class _GatedOpener:
    """Hold the act at its connection until the test has looked at what the screen holds."""

    def __init__(self, open_client: InstallationClientOpener | None) -> None:
        self._open_client = open_client
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self) -> InstallationClient:
        self.reached.set()
        await self.release.wait()
        if self._open_client is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return await self._open_client()


@pytest.mark.asyncio
async def test_the_area_lists_every_act_of_the_runtime_table_and_opens_the_one_chosen() -> None:
    area = InstallationScreen(open_client=_GatedOpener(None))
    app = ScreenHostApp(area)
    async with app.run_test(size=_SIZE) as pilot:
        await settle(pilot)
        table = area.query_one("#installation-acts", DataTable)
        listed = {str(row.key.value) for row in table.ordered_rows}

        assert listed == {act.value for act in INSTALLATION_ACT_CONTRACTS}
        assert table.row_count == len(INSTALLATION_ACT_CONTRACTS) == len(area.offered_acts)
        painted = screen_text(app, *_SIZE)
        for act in InstallationAct:
            assert act_label(act) in painted

        await pilot.press("enter")
        await settle_until(
            pilot,
            lambda: isinstance(app.screen, InstallationActScreen),
            "isinstance(app.screen, InstallationActScreen)",
            workers=False,
        )
        opened = app.screen
        assert isinstance(opened, InstallationActScreen)
        await settle_until(
            pilot,
            lambda: act_label(area.offered_acts[0]) in screen_text(app, *_SIZE),
            "act_label(area.offered_acts[0]) in screen_text(app, *_SIZE)",
            workers=False,
        )


@pytest.mark.asyncio
async def test_a_read_act_runs_at_once_and_shows_its_typed_reply(tmp_path: Path) -> None:
    changed: list[bool] = []
    with serving_test_acts(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            check = await _open(pilot, area, InstallationAct.STORAGE_CHECK)
            await act_settled(pilot, check)

            assert _status(check).tone == "success"
            assert _status(check).message == tr("tui.installation.status.completed")
            result = _result(check)
            assert _fact(result, "healthy") == yes_no(True)
            assert _fact(result, "storage_root") == str(served.root) and _fact(result, "checked_areas") == "4"
            # The reply's correlation coordinates say nothing about the act.
            assert "request_id" not in result and "connection_id" not in result

            check.action_close()
            await settle_until(pilot, lambda: app.screen is area, "app.screen is area", workers=False)
            inventory = await _open(pilot, area, InstallationAct.STORAGE_INVENTORY)
            await act_settled(pilot, inventory)
            # Its one member is optional, so the read answers as its command does with no argument.
            assert served.acts.inventories == [None]
            table = inventory.query_one("#installation-act-table", DataTable)
            assert table.display and table.row_count == 1
            assert [str(cell) for cell in table.get_row_at(0)] == [
                "cache",
                "reclaimable",
                "populated",
                str(RECLAIMABLE_ENTRIES),
                "4096 B",
                yes_no(True),
            ]
            assert "footprint_bytes" in _result(inventory)

            inventory.query_one("#installation-field-area", Select).value = "cache"
            await _run(pilot, inventory)
            await act_settled(pilot, inventory)
            assert served.acts.inventories == [None, StorageArea.CACHE] and table.row_count == 1
    assert changed == []


@pytest.mark.asyncio
async def test_a_changing_act_is_previewed_unconfirmed_then_asked_once_then_run_confirmed(tmp_path: Path) -> None:
    changed: list[bool] = []
    refusal = get_registered_error_code(StorageReclaimUnconfirmedError).code
    with serving_test_acts(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            reclaim = await _open(pilot, area, InstallationAct.STORAGE_RECLAIM)
            assert served.acts.reclaims == []
            reclaim.query_one("#installation-field-area", Select).value = "cache"
            await _run(pilot, reclaim)

            dialog = await _asked(pilot)
            assert served.acts.reclaims == [(StorageArea.CACHE, False)]
            assert changed == []
            assert _status(reclaim).tone == "warning" and refusal in _status(reclaim).message
            asked = str(dialog.query_one("#confirm-message", Static).content)
            assert _fact(asked, "entry_count") == str(RECLAIMABLE_ENTRIES)
            assert tr("tui.installation.confirm.question") in asked

            dialog.query_one("#btn-confirm-cancel", Button).press()
            await act_settled(pilot, reclaim)
            assert app.screen is reclaim
            assert served.acts.reclaims == [(StorageArea.CACHE, False)] and changed == []

            await _run(pilot, reclaim)
            dialog = await _asked(pilot)
            dialog.query_one("#btn-confirm-accept", Button).press()
            await act_settled(pilot, reclaim)

            assert served.acts.reclaims == [
                (StorageArea.CACHE, False),
                (StorageArea.CACHE, False),
                (StorageArea.CACHE, True),
            ]
            assert _status(reclaim).tone == "success"
            assert _fact(_result(reclaim), "removed_entries") == str(RECLAIMABLE_ENTRIES)
    assert changed == [True]


@pytest.mark.asyncio
async def test_confirmation_is_asked_only_when_the_confirmed_act_would_change_records(tmp_path: Path) -> None:
    with serving_test_acts(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client)
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            repair = await _open(pilot, area, InstallationAct.REPAIR_PROFILE)
            await _run(pilot, repair)
            await act_settled(pilot, repair)

            # Assessing the pointer changes nothing whether confirmed or not, so nobody is asked.
            assert app.screen is repair and served.acts.repairs == [(None, False, False)]
            assert _status(repair).tone == "success"

            repair.query_one("#installation-field-clear_active", Checkbox).value = True
            await _run(pilot, repair)
            dialog = await _asked(pilot)
            assert served.acts.repairs[-1] == (None, True, False)
            assert _status(repair).message == tr("tui.installation.status.preview")
            asked = str(dialog.query_one("#confirm-message", Static).content)
            assert _fact(asked, "dry_run") == yes_no(True)
            dialog.query_one("#btn-confirm-accept", Button).press()
            await act_settled(pilot, repair)

            assert served.acts.repairs == [(None, False, False), (None, True, False), (None, True, True)]
            assert _fact(_result(repair), "cleared_pointer") == yes_no(True)


@pytest.mark.asyncio
async def test_archive_import_reads_the_source_first_and_its_passphrase_travels_only_as_the_secret_frame(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    changed: list[bool] = []
    source = str(tmp_path / "synthetic.cadrumo-bucket.tar.gz")
    with serving_test_acts(tmp_path) as served:
        served.acts.release_import.clear()
        opener = _GatedOpener(served.open_client)
        area = InstallationScreen(open_client=opener, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            importing = await _open(pilot, area, InstallationAct.ARCHIVE_IMPORT)
            masked = importing.query_one("#installation-passphrase", Input)
            assert masked.password
            importing.query_one("#installation-field-label", Input).value = "Restored profile"
            importing.query_one("#installation-field-path", Input).value = source
            masked.value = _TYPED
            await _run(pilot, importing)

            await asyncio.wait_for(opener.reached.wait(), SETTLE_TIMEOUT_SECONDS)
            held = importing._pending_passphrase
            assert held is not None and bytes(held) == _TYPED.encode()
            assert masked.value == ""
            assert _TYPED not in _shown(app)
            opener.release.set()

            await settle_until(
                pilot, served.acts.import_reached.is_set, "served.acts.import_reached.is_set", workers=False
            )
            # The secret frame has been sent, so the buffer it was built from is already empty.
            assert not any(held)
            assert _TYPED not in _shown(app)
            served.acts.release_import.set()
            await act_settled(pilot, importing)

            assert _status(importing).tone == "success"
            assert served.acts.prepared == [("Restored profile", source)]
            assert served.acts.imported == [("Restored profile", source, source_digest_of(source))]
            assert served.acts.passphrases == [_TYPED]
            assert importing._pending_passphrase is None and not any(held)
            assert _fact(_result(importing), "label") == "Restored profile"
            assert _fact(_result(importing), "recovery_enrolled") == yes_no(False)
            assert _TYPED not in _shown(app)
    assert changed == [True]
    assert _TYPED not in _logged(caplog)


@pytest.mark.asyncio
async def test_a_passphrase_is_wiped_when_the_runtime_cannot_be_reached_and_the_remedy_is_shown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    changed: list[bool] = []
    opener = _GatedOpener(None)
    area = InstallationScreen(open_client=opener, on_records_changed=lambda: changed.append(True))
    app = ScreenHostApp(area)
    async with app.run_test(size=_SIZE) as pilot:
        enrolling = await _open(pilot, area, InstallationAct.RECOVERY_ENROLL)
        enrolling.query_one("#installation-field-profile_id", Input).value = str(uuid4())
        enrolling.query_one("#installation-passphrase", Input).value = _TYPED
        await _run(pilot, enrolling)

        await asyncio.wait_for(opener.reached.wait(), SETTLE_TIMEOUT_SECONDS)
        held = enrolling._pending_passphrase
        assert held is not None and bytes(held) == _TYPED.encode()
        opener.release.set()
        await act_settled(pilot, enrolling)

        assert _status(enrolling).tone == "error"
        assert RefusalCode.UNAVAILABLE.value in _status(enrolling).message
        assert _result(enrolling) == tr("common.runtime.manager_unavailable_remedy", product="Cadrumo")
        assert not any(held) and enrolling._pending_passphrase is None
        assert _TYPED not in _shown(app)
    assert changed == []
    assert _TYPED not in _logged(caplog)


@pytest.mark.asyncio
async def test_an_incomplete_form_names_its_fields_and_sends_nothing(tmp_path: Path) -> None:
    with serving_test_acts(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client)
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            reclaim = await _open(pilot, area, InstallationAct.STORAGE_RECLAIM)
            await _run(pilot, reclaim)
            await act_settled(pilot, reclaim)

            assert _status(reclaim).tone == "error"
            assert _status(reclaim).message == tr(
                "tui.installation.status.invalid_fields", fields=tr("tui.installation.field.area")
            )
            assert served.acts.reclaims == []

            reclaim.action_close()
            await settle_until(pilot, lambda: app.screen is area, "app.screen is area", workers=False)
            importing = await _open(pilot, area, InstallationAct.ARCHIVE_IMPORT)
            importing.query_one("#installation-act-run", Button).press()
            await settle_until(
                pilot, lambda: _status(importing).tone == "error", "_status(importing).tone == 'error'", workers=False
            )
            # Without a passphrase nothing is started at all, not even the read of the source.
            assert _status(importing).message == tr("tui.installation.passphrase.required")
            assert importing._act_worker is None
            assert served.acts.prepared == [] and served.acts.imported == []


@pytest.mark.asyncio
async def test_a_fault_and_an_unserved_act_are_shown_with_the_runtime_code_and_never_the_fault(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    changed: list[bool] = []
    with serving_test_acts(tmp_path) as served:
        area = InstallationScreen(open_client=served.open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            creating = await _open(pilot, area, InstallationAct.STORAGE_INIT)
            # It changes records, so it waits to be asked for even though it needs no input.
            assert creating._act_worker is None
            await _run(pilot, creating)
            await act_settled(pilot, creating)

            # An act that changes records may have changed some before it stopped.
            assert _status(creating).tone == "error"
            assert _status(creating).message == tr("tui.installation.status.failed_unknown", act="storage_init")
            assert FAULT_TEXT not in _shown(app)
            assert changed == [True]

            creating.action_close()
            await settle_until(pilot, lambda: app.screen is area, "app.screen is area", workers=False)
            report = await _open(pilot, area, InstallationAct.REPAIR_REPORT)
            await act_settled(pilot, report)
            assert _status(report).tone == "error"
            assert _status(report).message == tr("tui.installation.status.unreachable", code="operation_unavailable")
    assert changed == [True]
    assert FAULT_TEXT not in _logged(caplog)


class _WaitRunsOut(InstallationClient):
    """Explicit fault port: the wait for an act that changes records ends before its answer arrives.

    Everything else is sent on the real connection it wraps.
    """

    def __init__(self, real: InstallationClient) -> None:
        self._real = real
        self.unanswered: list[InstallationAct] = []

    @override
    def perform[ReplyT: InstallationCompleted](
        self,
        request: InstallationActRequest,
        reply_type: type[ReplyT],
        *,
        secret: bytearray | None = None,
        hold_secret: InstallationSecretHolder | None = None,
        timeout: float | None = None,
    ) -> ReplyT | InstallationRefused | InstallationFailed:
        if installation_request_facts(request).changes_records:
            self.unanswered.append(installation_act_of(request))
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
        return self._real.perform(request, reply_type, secret=secret, hold_secret=hold_secret, timeout=timeout)

    @override
    def close(self) -> None:
        self._real.close()


@pytest.mark.asyncio
async def test_an_act_whose_answer_never_arrived_is_shown_as_unknown_and_its_outcome_read_is_offered(
    tmp_path: Path,
) -> None:
    changed: list[bool] = []
    lost: list[_WaitRunsOut] = []
    with serving_test_acts(tmp_path) as served:

        async def open_client() -> InstallationClient:
            lost.append(_WaitRunsOut(await served.open_client()))
            return lost[-1]

        area = InstallationScreen(open_client=open_client, on_records_changed=lambda: changed.append(True))
        app = ScreenHostApp(area)
        async with app.run_test(size=_SIZE) as pilot:
            reset = await _open(pilot, area, InstallationAct.RESET_START)
            offer = reset.query_one("#installation-act-outcome", Button)
            assert not offer.display
            await _run(pilot, reset)
            dialog = await _asked(pilot)
            # The unconfirmed act reached the runtime and was refused there, as the command is.
            assert served.acts.resets == [False] and not offer.display
            dialog.query_one("#btn-confirm-accept", Button).press()
            await act_settled(pilot, reset)

            # Not failed and not sent again: nobody knows how it ended, and the profiles may be gone.
            assert _status(reset).tone == "warning"
            assert _status(reset).message == tr(
                "tui.installation.status.effect_unknown", code=RefusalCode.DEADLINE_EXCEEDED.value
            )
            assert [client.unanswered for client in lost] == [[], [InstallationAct.RESET_START]]
            assert served.acts.resets == [False] and changed == [True]
            assert offer.display
            assert str(offer.label) == tr(
                "tui.installation.action.read_outcome", act=act_label(InstallationAct.RESET_STATUS)
            )

            offer.press()
            await settle_until(
                pilot,
                lambda: (
                    isinstance(app.screen, InstallationActScreen)
                    and app.screen is not reset
                    and bool(app.screen.query("#installation-act-result"))
                ),
                "( isinstance(app.screen, InstallationActScreen) and app.screen is n...",
                workers=False,
            )
            status = app.screen
            assert isinstance(status, InstallationActScreen)
            await act_settled(pilot, status)
            assert served.acts.reset_status_reads == 1 and _status(status).tone == "success"
            assert served.acts.resets == [False]


@pytest.mark.asyncio
async def test_the_installed_opener_reaches_the_running_runtime_with_no_profile_and_reports_an_absent_one(
    tmp_path: Path,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        endpoint = WindowsEndpoint(storage_root=root)
        try:
            with serving_installation_runtime(
                endpoint, root, InstallationLogin(owner=owner_id()), product_version=version("cadrumo")
            ):
                area = InstallationScreen()
                app = ScreenHostApp(area)
                async with app.run_test(size=_SIZE) as pilot:
                    check = await _open(pilot, area, InstallationAct.STORAGE_CHECK)
                    await act_settled(pilot, check)
                    assert _status(check).tone == "success"
                    assert _fact(_result(check), "storage_root") == str(root)

                    check.action_close()
                    await settle_until(pilot, lambda: app.screen is area, "app.screen is area", workers=False)
                    reclaim = await _open(pilot, area, InstallationAct.STORAGE_RECLAIM)
                    reclaim.query_one("#installation-field-area", Select).value = "logs"
                    await _run(pilot, reclaim)
                    dialog = await _asked(pilot)
                    dialog.query_one("#btn-confirm-accept", Button).press()
                    await act_settled(pilot, reclaim)
                    # This runtime's handler refuses the confirmed act too: a refusal, with its code.
                    assert _status(reclaim).tone == "error"
                    assert get_registered_error_code(StorageReclaimUnconfirmedError).code in _status(reclaim).message
        finally:
            endpoint.close()

        absent = InstallationScreen()
        app = ScreenHostApp(absent)
        async with app.run_test(size=_SIZE) as pilot:
            check = await _open(pilot, absent, InstallationAct.STORAGE_CHECK)
            await settle_until(
                pilot, lambda: _status(check).tone == "error", "_status(check).tone == 'error'", workers=False
            )
            assert any(
                code.value in _status(check).message
                for code in (RefusalCode.UNAVAILABLE, RefusalCode.DEADLINE_EXCEEDED)
            )
