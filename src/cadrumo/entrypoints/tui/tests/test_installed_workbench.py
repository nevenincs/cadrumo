"""What ``aeat --tui`` actually composes, proven against the production seam.

The sibling module- and console-execution suites prove a session STARTS. They
cannot say what it contains, because a started session holding the terminal is
opaque from outside. This one composes the same production root in-process and
interrogates it: which destinations are admitted, whether every admitted one
mounts and returns, and whether the process that does all of that ever reaches
the CLI.

The composition is real. A real encrypted profile is registered and unlocked,
the real operation platform is composed, and the destination catalogue is the
one the root shell receives. What is deliberately NOT asserted is rendered
prose: it is locale data read from the catalogue the app reads, so asserting it
would prove only that one file was consulted twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ..launcher import main
from ..navigation import TUI_DESTINATION_CATALOGUE, TuiScreenContextV1
from .workbench_session import WORKBENCH_PROFILE_LABEL, installed_workbench_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_PACKAGE = "cadrumo.entrypoints.cli"
_PRIMARY_DESTINATIONS = ("workbench.home", "workbench.ledger", "workbench.declarations", "workbench.aeat_sync")


@pytest.mark.asyncio
async def test_the_installed_root_admits_the_whole_closed_destination_catalogue(tmp_path: Path) -> None:
    """Every declared destination is routed, and each carries an explicit state."""
    async with installed_workbench_root(tmp_path) as root:
        routed = tuple(route.descriptor.destination for route in root.destination_catalogue.routes)

        assert routed == tuple(descriptor.destination for descriptor in TUI_DESTINATION_CATALOGUE)
        for route in root.destination_catalogue.routes:
            assert route.admission.state in set(WorkbenchDestinationAdmissionState), route.descriptor.destination


@pytest.mark.asyncio
async def test_a_fresh_profile_admits_home_profile_and_every_principal_workspace(tmp_path: Path) -> None:
    """An empty profile is a usable workbench, not an unavailable one.

    This is the state a new operator meets. Ledger, Declarations and AEAT Sync
    hold nothing yet, and holding nothing is a truthful empty workspace rather
    than a destination that refuses to open.
    """
    async with installed_workbench_root(tmp_path) as root:
        for destination in (*_PRIMARY_DESTINATIONS, "workbench.profile"):
            route = root.destination_catalogue.resolve(destination)
            assert route.admission.state is WorkbenchDestinationAdmissionState.AVAILABLE, destination
            assert route.factory is not None, destination


@pytest.mark.asyncio
async def test_every_admitted_destination_builds_its_own_screen(tmp_path: Path) -> None:
    """An admitted destination mounts a real screen, not a placeholder."""
    async with installed_workbench_root(tmp_path) as root:
        built = []
        for destination in (*_PRIMARY_DESTINATIONS, "workbench.profile"):
            route = root.destination_catalogue.resolve(destination)
            assert route.factory is not None, destination
            built.append(route.factory(TuiScreenContextV1(destination=destination)))

        assert len({id(screen) for screen in built}) == len(built)


@pytest.mark.asyncio
async def test_an_unavailable_destination_never_carries_a_mountable_factory(tmp_path: Path) -> None:
    """Availability and mountability agree, so nothing can look openable and refuse."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            available = route.admission.state is WorkbenchDestinationAdmissionState.AVAILABLE
            assert available == (route.factory is not None), route.descriptor.destination


@pytest.mark.asyncio
async def test_the_home_refresh_door_rebuilds_the_projection_for_the_live_profile(tmp_path: Path) -> None:
    """Returning from a journey re-reads Home rather than replaying a snapshot."""
    async with installed_workbench_root(tmp_path) as root:
        first = root.refresh_home()
        second = root.refresh_home()

        assert first is not second
        assert first.account.profile_label == WORKBENCH_PROFILE_LABEL
        assert second.account.profile_label == WORKBENCH_PROFILE_LABEL


@pytest.mark.asyncio
async def test_search_and_navigation_report_the_same_admissions(tmp_path: Path) -> None:
    """The palette cannot offer a destination the mounted catalogue refuses."""
    async with installed_workbench_root(tmp_path) as root:
        search_inputs = root.search_inputs
        assert search_inputs is not None

        assert search_inputs.ledger_admission == root.admissions["workbench.ledger"]
        assert search_inputs.declarations_admission == root.admissions["workbench.declarations"]
        assert search_inputs.aeat_sync_admission == root.admissions["workbench.aeat_sync"]


def test_the_installed_session_never_pulls_the_cli_into_the_child_process() -> None:
    """Composing the whole workbench must not import the sibling entrypoint.

    The boundary is out-of-process by decision, and an import is exactly how
    it would stop being one. This checks the modules actually loaded rather
    than a source-level grep, so an import reached through a function body is
    still caught.
    """
    from .. import installed_session  # noqa: F401 - importing it is the subject

    assert not [name for name in sys.modules if name.startswith(_CLI_PACKAGE)]


def test_an_empty_profile_store_ends_the_headless_session_without_creating_one(tmp_path: Path) -> None:
    """The artifact proves it starts without inventing an operator's profile.

    ``--self-test`` exists to show the installed surface composes. It must not
    register a profile as a side effect of that proof, and it must not sit
    waiting for credentials nobody is there to type.
    """
    from ....tests.secure_sql import isolated_profile_storage_root
    from ..installed_session import SESSION_COMPLETED

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        assert main(headless=True) == SESSION_COMPLETED
        assert not list(Path(storage_root).glob("**/*.capsule"))
