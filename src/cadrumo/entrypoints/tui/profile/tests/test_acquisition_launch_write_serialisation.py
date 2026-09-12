"""An acquisition source cannot start while a field write is still landing.

Four mutation entry points on this screen refuse while ``_pending_write`` is
set, and each carries the same reason: the door merges into the profile record
as it loads it, so a second mutation started before the first landed merges
into the pre-edit facts and drops that field. An acquisition source is the same
shape -- it rewrites profile facts from a live capture -- and its button press
was the one entry point without the guard.

The omission is currently masked rather than harmless. The installed launcher
supplies no ``launch_source``, so every source button is disabled and the
handler returns before reaching the hazard; the day that door is wired, the
guard has to already be there. Driving the screen with a real launch door is
what makes the guarded path reachable here.
"""

from __future__ import annotations

import threading
from pathlib import Path
from uuid import UUID

import pytest
from textual.widgets import Button

from .....application.user_profile.acquisition_sources import (
    AcquisitionSourceCredentialPostureV1,
    ProfileAcquisitionSourceKey,
    ProfileAcquisitionSourceV1,
)
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.overview import ProfileOverview, build_profile_overview
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...components.host import ScreenHostApp
from ..overview import ProfileManagerScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "acquisition-serialisation-passphrase"  # noqa: S105 - isolated integration fixture


class _LaunchRecord:
    """Counts launches so the refusal can be told from a silent no-op."""

    def __init__(self) -> None:
        self.launched: list[ProfileAcquisitionSourceV1] = []

    async def __call__(self, source: ProfileAcquisitionSourceV1) -> None:
        self.launched.append(source)


def _persist_not_exercised(path: str, value: str) -> ProfileOverview:
    raise AssertionError("no field edit is exercised by this test")


def _build_overview() -> ProfileOverview:
    enrolled = register_profile_with_credentials(
        label="Acquisition serialisation subject",
        passphrase=_PASSPHRASE,
        facts=(),
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
    record = ProfileRecordRepository.for_current_session(UUID(enrolled.profile_id)).load(UUID(enrolled.profile_id))
    return build_profile_overview(record)


def _screen(launch: _LaunchRecord) -> ProfileManagerScreen:
    """A screen whose source buttons are enabled: door present, credential held."""
    return ProfileManagerScreen(
        _build_overview(),
        persist=_persist_not_exercised,
        launch_source=launch,
        credential_postures=(
            AcquisitionSourceCredentialPostureV1(
                source=ProfileAcquisitionSourceKey.CENSAL_REVIEW,
                requires_aeat_authentication=True,
                credential_held=True,
                provider_id="certificate",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_a_source_launches_when_no_write_is_in_flight(tmp_path: Path) -> None:
    """Positive control: without it, a guard that refuses everything would pass.

    This also pins that the guard did not simply disable the capability -- the
    press still reaches the door on the ordinary path.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        launch = _LaunchRecord()
        screen = _screen(launch)
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            button = screen.query_one("#source-censal_review").query_one(Button)
            button.press()
            await pilot.pause()

            assert len(launch.launched) == 1


@pytest.mark.asyncio
async def test_a_source_is_refused_while_a_field_write_is_still_landing(tmp_path: Path) -> None:
    """The guard: the capture must not merge into pre-edit facts."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        launch = _LaunchRecord()
        screen = _screen(launch)
        overview = screen.overview
        release = threading.Event()
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # A REAL worker, parked until released, so the screen holds exactly
            # the handle an operator's unlanded edit leaves behind rather than a
            # stand-in the type checker has to be talked past.
            screen._pending_write = screen.run_worker(
                lambda: (release.wait(timeout=5), overview)[1],
                thread=True,
                exit_on_error=False,
            )

            screen.query_one("#source-censal_review").query_one(Button).press()
            await pilot.pause()

            assert launch.launched == []
            release.set()
