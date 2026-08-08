"""The status page's auth panel projects the real profile session lifetime.

``ProfileLoginOutcome`` has always carried the idle and absolute deadlines
of a login, but nothing rendered them: an operator working full-screen had
no way to tell how long they had left before re-authenticating. These
tests drive the real chain — a real registration (which unlocks through
the canonical login door), the real in-process
:class:`~cadrumo.adapters.persistence.storage.BucketSession`, the real
:func:`~cadrumo.entrypoints.cli._config._status_frontend.build_status_page_data`
builder, and the real :class:`~cadrumo.adapters.inbound.tui.StatusApp`
surface. No mock, stub, or hand-built session record.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from .....adapters.inbound.tui import StatusApp
from .....application.user_profile import register_profile_with_credentials
from .....tests.secure_sql import isolated_profile_storage_root
from .._status_frontend import build_status_page_data

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "Status Session Deadline Subject"
_PASSWORD = "status-session-deadline-operator-secret"  # noqa: S105 - synthetic test fixture

_TERMINAL_SIZE = (140, 60)


def test_a_freshly_registered_profile_carries_both_real_deadlines(tmp_path) -> None:
    """Registration unlocks through the real login door, so both deadlines are set."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)

        data = build_status_page_data()

        assert data.auth.idle_deadline is not None
        assert data.auth.absolute_deadline is not None
        # The immutable cap can never be sooner than the sliding window.
        assert data.auth.absolute_deadline >= data.auth.idle_deadline


def test_no_active_session_reports_no_deadlines(tmp_path) -> None:
    """No profile registered yet: the real reader finds nothing to report."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        data = build_status_page_data()

        assert data.auth.idle_deadline is None
        assert data.auth.absolute_deadline is None


@pytest.mark.asyncio
async def test_the_real_deadlines_paint_on_the_running_status_surface(tmp_path) -> None:
    """The last mile: what the real session carries is what the auth panel shows."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        data = build_status_page_data()
        assert data.auth.idle_deadline is not None, "fixture premise: a live session must be open"
        expected_idle = data.auth.idle_deadline.isoformat(timespec="minutes")
        expected_absolute = data.auth.absolute_deadline.isoformat(timespec="minutes")

        app = StatusApp(data)
        async with app.run_test(size=_TERMINAL_SIZE):
            rendered = str(app.query_one("#auth-lines", Static).content)
            assert expected_idle in rendered
            assert expected_absolute in rendered
