"""Responsive-layout proofs for profile and credential screens at three widths.

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

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Select

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.login_interaction import ProfileLoginChoice
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.overview import ProfileOverview, build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..components.host import ScreenHostApp
from ..profile.overview import ProfileManagerScreen
from ..secret.runtime_login import RuntimeLoginScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREDENTIAL_INPUT = "terminal-sizes-operator-secret"
_LABEL = "Terminal Sizes Subject"

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


def _reachable_controls[T](app: App[T]) -> list[Widget]:
    """Every displayed interactive control currently mounted on the screen."""
    return [
        widget
        for widget in app.app.screen.query(Widget)
        if isinstance(widget, _INTERACTIVE) and widget.display and widget.region.width > 0
    ]


def _assert_horizontally_contained[T](app: App[T], size: tuple[int, int], surface: str) -> None:
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
def _registered_profile(tmp_path: Path) -> Generator[tuple[Path, PinnedAuthorityOperation]]:
    """One real profile created through the real registration door."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as root,
        bundled_indexed_authority().operation() as authority_operation,
    ):
        register_profile_with_credentials(
            label=_LABEL,
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=authority_operation.profile_create_context(),
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        login_profile(
            name=_LABEL,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        yield root, authority_operation


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.asyncio
async def test_the_profile_surface_fits_every_terminal_width(tmp_path: Path, size: tuple[int, int]) -> None:
    """The profile manager keeps its whole field table inside the terminal."""
    with _registered_profile(tmp_path) as (_root, _authority_operation):
        record = load_test_profile_record(require_active_bucket_id())
        overview = build_profile_overview(record, label=_LABEL, schema=_authority_operation.profile_schema())

        def _refuse_write(
            path: str, value: str, expected_revision: int, expected_content_digest: str
        ) -> ProfileOverview:
            # This proof measures layout, never storage. A write door that
            # raises makes an accidental mutation a failure rather than a
            # silent side effect on the fixture profile.
            del path, value, expected_revision, expected_content_digest
            message = "the terminal-size proof never writes"
            raise AssertionError(message)

        app = ProfileManagerScreen(overview, persist=_refuse_write)
        async with ScreenHostApp(app).run_test(size=size) as pilot:
            await pilot.pause()
            await pilot.pause()
            _assert_horizontally_contained(app.app, size, "profile manager")
            pilot.app.exit(None)


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.asyncio
async def test_the_secret_surface_fits_every_terminal_width(size: tuple[int, int]) -> None:
    """The runtime login controls fit without acquiring any profile authority."""

    async def must_not_open(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("the terminal-size proof never opens a runtime connection")

    screen = RuntimeLoginScreen(
        choices=[ProfileLoginChoice(profile_id=str(uuid4()), label=_LABEL)],
        open_client=must_not_open,
        accept_handoff=lambda _: False,
    )
    app = ScreenHostApp(screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        await pilot.pause()
        _assert_horizontally_contained(app, size, "runtime login screen")
        app.exit(None)
