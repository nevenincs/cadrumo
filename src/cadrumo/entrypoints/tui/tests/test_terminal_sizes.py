"""Responsive-layout proofs for every full-screen surface, at three widths.

Each surface is the production composition, driven through Textual's
headless Pilot at a narrow, a normal, and a wide terminal. The property
asserted is horizontal containment: every interactive control the operator
must be able to reach is mounted with a real size and lies wholly inside
the terminal's width. Horizontal overflow is the failure a fixed-width
layout produces on a small terminal, and it is unrecoverable for the
operator; vertical extent is deliberately not asserted, because content
taller than the viewport is what the surfaces' scroll containers exist to
carry.

Nothing here asserts rendered prose. Prose is locale data, and reading it
from the same catalogue the surface reads would be tautological.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from textual.app import App
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Select

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.storage import SecureObjectRepository
from ....application.auth.apoderado_flow import build_apoderado_flow_definition
from ....application.modelo.operation_definitions import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    build_modelo_work_verify_definition,
    build_modelo_work_verify_registration,
)
from ....application.operations.composition import OperationComposedServices, compose_operation_services
from ....application.operations.interactions import OperationActorReference
from ....application.operations.models import OperationRequest
from ....application.operations.registry import OperationRegistry
from ....application.user_profile.custody_ports import profile_custody_secure_object_repository
from ....application.user_profile.login_interaction import ProfileLoginChoice, attempt_profile_login
from ....application.user_profile.login_session import login_profile, logout_active_profile
from ....application.user_profile.overview import ProfileOverview, build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....core.flows import FlowMode
from ....core.time import now
from ....domain.auth import load_default_catalogue
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..components.host import ScreenHostApp
from ..flows.app import FlowTuiApp
from ..operations.controller import OperationController
from ..operations.modal import OperationModal
from ..profile.overview import ProfileManagerScreen
from ..secret.credentials import CredentialHostApp
from ..secret.login import LoginScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSWORD = "terminal-sizes-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Terminal Sizes Subject"
_ACTOR: OperationActorReference = "operator:terminal-sizes"

_NARROW = (80, 24)
"""The smallest terminal this application undertakes to render into.

Eighty by twenty-four is the floor every terminal emulator still honours,
so a surface that overflows it overflows the worst case an operator can
realistically present."""

_NORMAL = (120, 40)
_WIDE = (200, 60)
_SIZES = (_NARROW, _NORMAL, _WIDE)

_INTERACTIVE = (Button, Input, Select, DataTable)
"""The widget classes an operator must be able to see in order to act.

A control pushed off the right edge is unreachable: there is no horizontal
scroll affordance on these surfaces, so the operator cannot recover."""


def _reachable_controls(app: App[object]) -> list[Widget]:
    """Every displayed interactive control currently mounted on the screen."""
    return [
        widget
        for widget in app.screen.query(Widget)
        if isinstance(widget, _INTERACTIVE) and widget.display and widget.region.width > 0
    ]


def _assert_horizontally_contained(app: App[object], size: tuple[int, int], surface: str) -> None:
    """Assert every reachable control fits inside the terminal's width."""
    width, _height = size
    controls = _reachable_controls(app)
    assert controls, f"{surface} rendered no reachable control at {size}, so this check would prove nothing"
    overflowing = [
        (type(widget).__name__, widget.id, widget.region.x, widget.region.right)
        for widget in controls
        if widget.region.x < 0 or widget.region.right > width
    ]
    assert not overflowing, f"{surface} overflows a {width}-column terminal: {overflowing}"
    degenerate = [(type(widget).__name__, widget.id) for widget in controls if widget.region.height <= 0]
    assert not degenerate, f"{surface} rendered a zero-height control at {size}: {degenerate}"


@contextmanager
def _registered_profile(tmp_path: Path) -> Iterator[Path]:
    """One real profile created through the real registration door."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_LABEL,
            passphrase=_PASSWORD,
        )
        yield root


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.asyncio
async def test_the_profile_surface_fits_every_terminal_width(tmp_path: Path, size: tuple[int, int]) -> None:
    """The profile manager keeps its whole field table inside the terminal."""
    with _registered_profile(tmp_path):
        login_profile(name=_LABEL, passphrase_callback=lambda: _PASSWORD)
        record = load_test_profile_record(require_active_bucket_id())
        overview = build_profile_overview(record, label=_LABEL)

        def _refuse_write(path: str, value: str) -> ProfileOverview:
            # This proof measures layout, never storage. A write door that
            # raises makes an accidental mutation a failure rather than a
            # silent side effect on the fixture profile.
            del path, value
            message = "the terminal-size proof never writes"
            raise AssertionError(message)

        app = ProfileManagerScreen(overview, persist=_refuse_write)
        async with ScreenHostApp(app).run_test(size=size) as pilot:
            await pilot.pause()
            await pilot.pause()
            _assert_horizontally_contained(cast(App[object], app), size, "profile manager")
            app.exit(None)


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.asyncio
async def test_the_secret_surface_fits_every_terminal_width(tmp_path: Path, size: tuple[int, int]) -> None:
    """The login screen keeps both credential fields inside the terminal."""
    with _registered_profile(tmp_path):
        bucket_id = require_active_bucket_id()
        logout_active_profile()
        screen = LoginScreen(
            choices=[ProfileLoginChoice(profile_id=bucket_id, label=_LABEL)],
            authenticate=lambda profile_id, secret: attempt_profile_login(profile_id=profile_id, passphrase=secret),
        )
        app = CredentialHostApp(screen)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await pilot.pause()
            _assert_horizontally_contained(cast(App[object], app), size, "login screen")
            app.exit(None)


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.asyncio
async def test_the_flow_surface_fits_every_terminal_width(size: tuple[int, int]) -> None:
    """The guided-flow surface keeps its answer controls inside the terminal."""
    definition = build_apoderado_flow_definition(load_default_catalogue())
    app = FlowTuiApp(definition, mode=FlowMode.CREATE, registered_values={})
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        await pilot.pause()
        _assert_horizontally_contained(cast(App[object], app), size, "guided flow")
        app.exit(None)


@contextmanager
def _operation_runtime(tmp_path: Path) -> Generator[tuple[OperationComposedServices, OperationRegistry, UUID]]:
    """The production operation platform, composed exactly as the TUI composes it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_LABEL,
            passphrase=_PASSWORD,
        )
        profile_id = UUID(enrolled.profile_id)
        # Custody resolves the session's real data key; registration closes
        # its own session, so the profile must be unlocked again first.
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSWORD)
        verify_definition = build_modelo_work_verify_definition()
        registry = OperationRegistry(
            definitions=(verify_definition,),
            public_registrations=(build_modelo_work_verify_registration(verify_definition),),
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            services = compose_operation_services(
                registry=registry,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=timedelta(hours=1),
                cleanup_timeout=timedelta(minutes=2),
            )
            try:
                yield services, registry, profile_id
            finally:
                asyncio.run(services.shutdown())


@pytest.mark.parametrize("size", _SIZES)
def test_the_operation_surface_fits_every_terminal_width(tmp_path: Path, size: tuple[int, int]) -> None:
    """The generic operation modal keeps its control row inside the terminal."""
    with _operation_runtime(tmp_path) as (services, registry, profile_id):

        async def run() -> None:
            definition = registry.lookup(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID)
            payload = definition.request_type.model_validate(
                {"calculation_revision_id": "revision-under-layout-proof", "actor": _ACTOR},
                strict=True,
            )
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=payload,
                ),
                actor_ref=_ACTOR,
            )
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)

            class _Host(App[None]):
                def on_mount(self) -> None:
                    self.run_worker(self.push_screen_wait(OperationModal(controller)))

            host = _Host()
            async with host.run_test(size=size) as pilot:
                for _ in range(200):
                    await pilot.pause()
                    if isinstance(host.screen, OperationModal):
                        break
                assert isinstance(host.screen, OperationModal)
                await pilot.pause()
                _assert_horizontally_contained(cast(App[object], host), size, "operation modal")
                await host.action_quit()

        asyncio.run(run())
