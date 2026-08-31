"""The status page's auth panel projects the real profile session lifetime.

``ProfileLoginOutcome`` has always carried the idle and absolute deadlines
of a login, but nothing rendered them: an operator working full-screen had
no way to tell how long they had left before re-authenticating. These
tests drive the real chain — a real credential registration followed by the
canonical authenticated login door, the real in-process
:class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`, the real
:func:`~cadrumo.application.user_profile.status_projection.build_status_page_data`
builder, and the real :class:`~cadrumo.entrypoints.tui.profile.status.StatusScreen`
surface. No mock, stub, or hand-built session record.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ....application.user_profile.login_session import close_profile_session_artefacts, login_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....application.user_profile.status_projection import build_status_page_data
from ....tests.secure_sql import isolated_profile_storage_root
from ..components.host import ScreenHostApp
from ..profile.status import StatusScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "Status Session Deadline Subject"
_TEST_CREDENTIAL = "status-session-deadline-operator-secret"

_TERMINAL_SIZE = (140, 60)


def test_an_authenticated_registered_profile_carries_both_real_deadlines(tmp_path) -> None:
    """Only login creates the real session whose deadlines status projects."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        registered = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_LABEL,
            passphrase=_TEST_CREDENTIAL,
        )
        try:
            login_profile(name=registered.profile_id, passphrase_callback=lambda: _TEST_CREDENTIAL)
            data = build_status_page_data()

            assert data.auth.idle_deadline is not None
            assert data.auth.absolute_deadline is not None
            # The immutable cap can never be sooner than the sliding window.
            assert data.auth.absolute_deadline >= data.auth.idle_deadline
        finally:
            close_profile_session_artefacts(storage_root=storage_root, bucket_id=registered.profile_id)


def test_no_active_session_reports_no_deadlines(tmp_path) -> None:
    """No profile registered yet: the real reader finds nothing to report."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        data = build_status_page_data()

        assert data.auth.idle_deadline is None
        assert data.auth.absolute_deadline is None


@pytest.mark.asyncio
async def test_the_real_deadlines_paint_on_the_running_status_surface(tmp_path) -> None:
    """The last mile: what the real session carries is what the auth panel shows."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        registered = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_LABEL,
            passphrase=_TEST_CREDENTIAL,
        )
        try:
            login_profile(name=registered.profile_id, passphrase_callback=lambda: _TEST_CREDENTIAL)
            data = build_status_page_data()
            assert data.auth.idle_deadline is not None, "fixture premise: a live session must be open"
            assert data.auth.absolute_deadline is not None, "fixture premise: the immutable session cap must be present"
            expected_idle = data.auth.idle_deadline.isoformat(timespec="minutes")
            expected_absolute = data.auth.absolute_deadline.isoformat(timespec="minutes")

            app = StatusScreen(data)
            async with ScreenHostApp(app).run_test(size=_TERMINAL_SIZE):
                rendered = str(app.query_one("#auth-lines", Static).content)
                assert expected_idle in rendered
                assert expected_absolute in rendered
        finally:
            close_profile_session_artefacts(storage_root=storage_root, bucket_id=registered.profile_id)
